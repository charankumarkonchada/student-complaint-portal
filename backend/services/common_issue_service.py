"""
IntelliHostel — Common Issue Management & Scalability Service.
Handles grouping of multiple student complaints into master common issues,
single-action admin propagation, shared notifications, and audit tracking.
"""
from __future__ import annotations

import re
import math
import logging
from collections import Counter
from typing import Any, Optional
from backend.database.db import get_db_connection

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

HOSTEL_SYNONYMS = {
    "filter": "purifier",
    "filters": "purifier",
    "purifiers": "purifier",
    "purify": "purifier",
    "tap": "faucet",
    "taps": "faucet",
    "faucets": "faucet",
    "leak": "leaking",
    "leakage": "leaking",
    "leaks": "leaking",
    "broken": "damaged",
    "faulty": "damaged",
    "damage": "damaged",
    "damages": "damaged",
    "wifi": "internet",
    "wi-fi": "internet",
    "lan": "internet",
    "fan": "fan",
    "fans": "fan",
    "tubelight": "light",
    "bulb": "light",
    "bulbs": "light",
    "lights": "light",
    "washroom": "washroom",
    "bathroom": "washroom",
    "bathrooms": "washroom",
    "toilet": "washroom",
    "toilets": "washroom",
    "restroom": "washroom",
    "cooler": "cooler",
    "tank": "tank",
}

ACTIVE_COMMON_ISSUE_STATUSES = frozenset({"Pending", "In Progress"})
INACTIVE_COMMON_ISSUE_STATUSES = frozenset({"Resolved", "Closed", "Rejected"})

CATEGORY_EQUIVALENCE: dict[str, str] = {
    "water": "plumbing",
    "plumbing": "plumbing",
    "electrical": "electrical",
    "furniture": "carpentry",
    "carpentry": "carpentry",
    "cleaning": "cleanliness",
    "cleanliness": "cleanliness",
    "internet": "internet / wi-fi",
    "wi-fi": "internet / wi-fi",
    "wifi": "internet / wi-fi",
    "internet / wi-fi": "internet / wi-fi",
    "mess": "mess",
    "food": "mess",
    "other": "other",
    "others": "other",
}


def is_category_compatible(cat1: Optional[str], cat2: Optional[str]) -> bool:
    """
    Checks if two category strings are compatible, supporting standard aliases between
    student submission forms (e.g. Water, Cleaning, Furniture, Internet) and
    admin master issue forms (e.g. Plumbing, Cleanliness, Carpentry, Internet / Wi-Fi).
    """
    if not cat1 or not cat2:
        return False
    c1 = str(cat1).strip().lower()
    c2 = str(cat2).strip().lower()
    if c1 == c2:
        return True
    return CATEGORY_EQUIVALENCE.get(c1, c1) == CATEGORY_EQUIVALENCE.get(c2, c2)


def _clean_str(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _extract_hostel_tokens(text: Optional[str]) -> list[str]:
    text_lower = (text or "").lower()
    words = re.findall(r"[a-z0-9]+", text_lower)
    meaningful = [w for w in words if w not in {"hostel", "bhavan", "block", "hall", "residence", "room"}]
    return meaningful


def is_location_compatible(
    issue_hostel: Optional[str],
    issue_location_details: Optional[str],
    student_hostel: Optional[str],
    student_room_no: Optional[str]
) -> bool:
    """
    Strictly verifies location compatibility between a master issue and student complaint.
    - Preserves hostel boundaries: Complaints from different hostels (e.g. Hostel Block A vs Hostel Block C)
      are NEVER merged or associated.
    - Supports room-level locations: If an admin specifies a room (e.g. 'I108', 'Room I108'), matches
      against student_room_no while verifying block compatibility.
    - Supports combined hostel + room locations.
    """
    if not issue_hostel:
        return False

    ih = issue_hostel.strip().lower()
    sh = (student_hostel or "").strip().lower()
    sr = (student_room_no or "").strip().lower()
    ild = (issue_location_details or "").strip().lower()

    # Exact string match (ignoring whitespace and case)
    if sh and ih == sh:
        return True

    clean_sr = _clean_str(sr)
    clean_ih = _clean_str(ih)
    clean_sh = _clean_str(sh)

    # Direct room match (e.g. issue_hostel is 'I108' or 'Room I108' and student_room_no is 'I108')
    if clean_sr and (clean_ih == clean_sr or clean_ih == f"room{clean_sr}"):
        return True

    # If issue_hostel contains both hostel and room (e.g. 'Hostel Block A - 201' or 'Boys I block I108')
    if clean_sr and clean_sh and clean_sr in clean_ih and clean_sh in clean_ih:
        return True

    # Token comparison between hostel names
    ih_tokens = _extract_hostel_tokens(ih)
    sh_tokens = _extract_hostel_tokens(sh)

    # Disallow mismatch if both have distinct hostel identifiers (e.g. ['a'] vs ['b'] or ['c'])
    if ih_tokens and sh_tokens and not any(c.isdigit() for c in ih):
        if set(ih_tokens) == set(sh_tokens) or (len(ih_tokens) == 1 and ih_tokens[0] in sh_tokens):
            return True
        return False

    return False


DOMAIN_GENERIC_WORDS = {
    "working", "work", "works", "worked",
    "broken", "damage", "damaged", "damages",
    "stopped", "stop", "stops",
    "issue", "issues",
    "problem", "problems",
    "properly", "proper",
    "urgent", "urgently", "urgency",
    "immediate", "immediately", "attention",
    "needed", "need", "needs",
    "please", "check", "fix", "repair", "repairs", "repaired",
    "requiring", "require", "requires", "support", "help",
    "affecting", "affected", "affects",
    "several", "many", "all", "students", "student", "residents", "resident",
    "reported", "report", "reports",
    "since", "yesterday", "today", "days", "time", "hours",
    "completely", "very", "extremely", "totally", "often", "frequently",
    "bad", "faulty", "failure", "fail", "failed",
    "service", "services", "request", "requests", "maintenance",
    "complaint", "complaints"
}

SPECIFIC_LOCATIONS = {
    "washroom": {"washroom", "washrooms", "bathroom", "bathrooms", "toilet", "toilets", "restroom", "restrooms", "latrine", "lavatory"},
    "room": {"room", "rooms", "bedroom", "hostel room"},
    "corridor": {"corridor", "corridors", "hallway", "hallways", "passage", "passages", "gallery", "lobby"},
    "mess": {"mess", "dining", "canteen", "cafeteria", "kitchen"},
    "drinking_area": {"drinking", "water cooler", "water filter", "purifier area", "dispenser"},
    "balcony": {"balcony", "terrace", "veranda"},
    "staircase": {"staircase", "stairs", "stairway"},
}

TARGET_ASSETS = {
    # Electrical
    "fan": {"fan", "fans", "ceiling fan", "exhaust fan", "regulator"},
    "light": {"light", "lights", "tube light", "tubelight", "bulb", "bulbs", "lamp", "lamps", "led"},
    "socket": {"socket", "sockets", "plug", "plugs", "switch", "switches", "switchboard", "board", "outlet", "outlets"},
    "wiring": {"wire", "wires", "wiring", "short circuit", "spark", "sparking"},
    "power": {"power cut", "power outage", "electricity cut", "current cut", "no power", "blackout", "tripping", "mcb"},
    "ac": {"ac", "air conditioner", "air conditioning", "cooler"},
    "geyser": {"geyser", "water heater", "heater"},

    # Plumbing
    "drinking_water": {"drinking water", "drinking", "purifier", "filter water", "ro water", "water cooler"},
    "washroom_water": {"washroom water", "bathroom water", "bathing water", "water for bathing", "flush water", "toilet water"},
    "tap": {"tap", "taps", "faucet", "faucets"},
    "pipe": {"pipe", "pipes", "pipeline", "piping", "drain", "drainage", "sewer"},
    "shower": {"shower", "showers"},
    "flush": {"flush", "cistern", "commode"},
    "basin": {"basin", "sink", "washbasin"},
    "tank": {"tank", "overhead tank", "water tank"},

    # Internet / Wi-Fi
    "wifi_router": {"wifi", "wi-fi", "router", "lan", "ethernet", "hotspot", "access point", "network", "internet"},

    # Carpentry / Furniture
    "door": {"door", "doors", "door handle", "door latch", "door lock", "hinge", "hinges"},
    "window": {"window", "windows", "window pane", "glass pane"},
    "table": {"table", "tables", "study table", "desk", "desks"},
    "chair": {"chair", "chairs", "study chair", "stool", "benches", "bench"},
    "bed": {"bed", "beds", "cot", "cots", "mattress"},
    "cupboard": {"cupboard", "cupboards", "almirah", "wardrobe", "closet", "shelf", "shelves", "drawer", "drawers"},

    # Cleanliness
    "waste": {"garbage", "trash", "waste", "dustbin", "litter", "rubbish"},
    "pest": {"cockroach", "cockroaches", "insect", "insects", "mosquito", "mosquitoes", "bedbug", "bedbugs", "rat", "rats", "rodent"},
    "dust": {"dust", "dusty", "cobweb", "cobwebs", "dirty floor", "sweeping", "mopping"},

    # Mess / Food
    "food_quality": {"food quality", "taste", "undercooked", "raw", "burnt", "cold food"},
    "food_shortage": {"shortage", "finished", "ran out", "insufficient food", "no food left"},
    "food_hygiene": {"foreign object", "insect in food", "hair in food", "dirty utensils", "dirty plates"}
}

PROBLEM_ASPECTS = {
    # Network
    "speed_degradation": {"slow", "speed", "buffering", "lag", "latency", "high ping", "bandwidth", "low speed", "extremely slow"},
    "outage": {"unavailable", "down", "disconnected", "no connection", "not connecting", "offline", "outage", "cuts", "no signal", "cannot connect", "no wifi", "no internet", "no electricity", "power cut", "power outage", "blackout"},

    # Water / Plumbing
    "leakage": {"leak", "leaking", "leakage", "dripping", "overflow", "overflowing", "seepage"},
    "shortage": {"no water", "unavailable", "empty", "scarcity", "not coming", "stopped coming", "dry", "no supply"},
    "pressure": {"low pressure", "pressure", "slow flow"},
    "clogging": {"block", "blocked", "clog", "clogged", "overflowing drain", "choked"},

    # General
    "cleanliness": {"clean", "cleaned", "cleaning", "dirty", "stink", "smell", "unhygienic", "sweep", "mop"},
    "damage": {"broken", "break", "cracked", "damage", "damaged", "loose", "fell", "bent"}
}


def analyze_complaint_intent(text: str, category: Optional[str] = None) -> dict[str, Any]:
    """
    Decomposes complaint text and category into structured semantic dimensions:
    - locations: detected specific locations (room, washroom, corridor, etc.)
    - assets: target assets / physical objects (fan, light, pipe, etc.)
    - aspects: failure mode / problem aspect (outage, speed_degradation, leakage, etc.)
    - focal_tokens: tokens excluding domain generic maintenance action words
    """
    raw = (text or "").lower()
    raw = re.sub(r"\bwi[- ]?fi\b", "internet", raw)
    text_lower = " " + re.sub(r"[^a-z0-9\s]", " ", raw) + " "

    # 1. Detect specific locations
    detected_locations = set()
    for loc_key, terms in SPECIFIC_LOCATIONS.items():
        for term in terms:
            if f" {term} " in text_lower:
                detected_locations.add(loc_key)
                break

    # 2. Detect target assets
    detected_assets = set()
    for asset_key, terms in TARGET_ASSETS.items():
        for term in terms:
            if f" {term} " in text_lower:
                detected_assets.add(asset_key)
                break

    # Disambiguation / refinement
    if "drinking water" in text_lower or ("drinking" in text_lower and "water" in text_lower):
        detected_assets.add("drinking_water")
        detected_assets.discard("washroom_water")
    elif "washroom" in text_lower and "water" in text_lower:
        detected_assets.add("washroom_water")
        detected_assets.discard("drinking_water")
    elif "bathing" in text_lower or "bath" in text_lower:
        detected_assets.add("washroom_water")
        detected_assets.discard("drinking_water")

    # 3. Detect problem aspects
    detected_aspects = set()
    for aspect_key, terms in PROBLEM_ASPECTS.items():
        for term in terms:
            if f" {term} " in text_lower:
                detected_aspects.add(aspect_key)
                break

    # 4. Extract distinctive focal tokens
    raw_words = re.findall(r"[a-z0-9]+", text_lower)
    focal_tokens = [
        HOSTEL_SYNONYMS.get(w, w)
        for w in raw_words
        if w not in STOP_WORDS and w not in DOMAIN_GENERIC_WORDS and len(w) > 1
    ]

    return {
        "text": text,
        "category": CATEGORY_EQUIVALENCE.get(category.lower().strip(), category) if category else None,
        "locations": detected_locations,
        "assets": detected_assets,
        "aspects": detected_aspects,
        "focal_tokens": focal_tokens,
    }


def are_underlying_problems_compatible(intent1: dict[str, Any], intent2: dict[str, Any]) -> tuple[bool, str]:
    """
    Evaluates whether two complaint intents represent the same underlying maintenance problem.
    Returns (is_compatible, reason).
    """
    # 1. Target Asset Compatibility Check
    assets1 = intent1["assets"]
    assets2 = intent2["assets"]
    if assets1 and assets2:
        # Drinking water vs Domestic plumbing separation:
        # Drinking water (purifier, drinking water cooler) is NEVER compatible with washroom/shower/tap/toilet/pipeline plumbing.
        if "drinking_water" in assets1 and not ("drinking_water" in assets2):
            return False, "Conflicting assets: drinking water vs domestic plumbing"
        if "drinking_water" in assets2 and not ("drinking_water" in assets1):
            return False, "Conflicting assets: domestic plumbing vs drinking water"

        # Electrical appliance conflict (fan vs light vs socket vs ac vs geyser)
        electrical_assets = {"fan", "light", "socket", "ac", "geyser", "wiring", "power"}
        e1 = assets1.intersection(electrical_assets)
        e2 = assets2.intersection(electrical_assets)
        if e1 and e2 and e1.isdisjoint(e2):
            return False, f"Electrical asset conflict: {e1} vs {e2}"

        # Carpentry furniture conflict (door vs window vs table vs chair vs bed vs cupboard)
        carpentry_assets = {"door", "window", "table", "chair", "bed", "cupboard"}
        c1 = assets1.intersection(carpentry_assets)
        c2 = assets2.intersection(carpentry_assets)
        if c1 and c2 and c1.isdisjoint(c2):
            return False, f"Carpentry asset conflict: {c1} vs {c2}"

        # Distinct plumbing fixture conflict (e.g. pipe vs tap vs shower)
        plumbing_fixtures = {"tap", "pipe", "shower", "flush"}
        p1 = assets1.intersection(plumbing_fixtures)
        p2 = assets2.intersection(plumbing_fixtures)
        if p1 and p2 and p1.isdisjoint(p2):
            return False, f"Plumbing fixture conflict: {p1} vs {p2}"

    # 2. Specific Location Context Conflict:
    # If both specify specific locations and they are disjoint,
    # they cannot represent the same physical maintenance issue.
    locs1 = intent1["locations"]
    locs2 = intent2["locations"]
    if locs1 and locs2:
        if locs1.isdisjoint(locs2):
            return False, f"Location conflict: {locs1} vs {locs2}"

    # 3. Problem Aspect Conflict:
    aspects1 = intent1["aspects"]
    aspects2 = intent2["aspects"]
    if ("outage" in aspects1 and "speed_degradation" in aspects2) or ("speed_degradation" in aspects1 and "outage" in aspects2):
        return False, "Aspect conflict: outage vs speed degradation"
    if ("leakage" in aspects1 and "shortage" in aspects2) or ("shortage" in aspects1 and "leakage" in aspects2):
        return False, "Aspect conflict: leakage vs shortage"

    # 4. Focal Semantic Similarity Check:
    focal1 = intent1["focal_tokens"]
    focal2 = intent2["focal_tokens"]
    if focal1 and focal2:
        c1 = Counter(focal1)
        c2 = Counter(focal2)
        dot = sum(c1[k] * c2[k] for k in c1 if k in c2)
        mag1 = math.sqrt(sum(v**2 for v in c1.values()))
        mag2 = math.sqrt(sum(v**2 for v in c2.values()))
        focal_sim = dot / (mag1 * mag2) if (mag1 and mag2) else 0.0

        if focal_sim == 0.0 and len(focal1) >= 1 and len(focal2) >= 1:
            return False, "Zero focal similarity on distinctive terms"

    return True, "Compatible underlying problem"


def is_active_status(status: Optional[str]) -> bool:
    """
    Determines whether a status represents an active, ongoing issue.
    Active statuses: 'Pending', 'In Progress'.
    Inactive / terminal statuses: 'Resolved', 'Closed', 'Rejected'.
    Case-insensitive and whitespace-tolerant.
    """
    if not status:
        return False
    return status.strip().lower() in {s.lower() for s in ACTIVE_COMMON_ISSUE_STATUSES}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    filtered = []
    for w in words:
        if w not in STOP_WORDS and len(w) > 1:
            filtered.append(HOSTEL_SYNONYMS.get(w, w))
    return filtered or words


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculates vector cosine similarity between two texts using token frequencies."""
    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    c1 = Counter(tokens1)
    c2 = Counter(tokens2)

    dot = sum(c1[k] * c2[k] for k in c1 if k in c2)
    mag1 = math.sqrt(sum(v**2 for v in c1.values()))
    mag2 = math.sqrt(sum(v**2 for v in c2.values()))

    if not mag1 or not mag2:
        return 0.0

    cosine = dot / (mag1 * mag2)
    return round(float(cosine), 3)


def find_matching_common_issue(
    category: str,
    hostel: str,
    title: str,
    description: str,
    student_room_no: Optional[str] = None,
    conn: Optional[Any] = None,
    threshold: float = 0.50,
    active_only: bool = True
) -> Optional[dict[str, Any]]:
    """
    Finds a common issue matching the hostel/location and category,
    with title/description similarity meeting the safe threshold.
    If active_only is True, filters to only active issues ('Pending', 'In Progress').
    If active_only is False, matches across all issues (both active and historical/closed).
    Strictly prevents merging complaints across different hostels.
    """
    if not hostel or not category:
        return None

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        issues = conn.execute(
            """
            SELECT * FROM common_issues
            ORDER BY id DESC
            """
        ).fetchall()

        if not issues:
            return None

        complaint_text = f"{title} {description}"
        best_match = None
        best_similarity = 0.0

        for issue in issues:
            issue_active = is_active_status(issue["status"])
            if active_only and not issue_active:
                continue

            if not is_category_compatible(category, issue["category"]):
                continue

            loc_details = issue["location_details"] if "location_details" in issue.keys() else ""
            if not is_location_compatible(issue["hostel"], loc_details, hostel, student_room_no):
                continue

            issue_text = f"{issue['title']} {issue['description'] or ''}"

            # Underlying problem intent compatibility check
            comp_intent = analyze_complaint_intent(complaint_text, category)
            issue_intent = analyze_complaint_intent(issue_text, issue["category"])
            is_compat, _ = are_underlying_problems_compatible(comp_intent, issue_intent)
            if not is_compat:
                continue

            sim = calculate_text_similarity(complaint_text, issue_text)
            if sim >= threshold and sim > best_similarity:
                best_similarity = sim
                best_match = dict(issue)
                best_match["similarity"] = round(sim * 100, 1)
                best_match["is_active"] = issue_active

        return best_match
    finally:
        if close_conn:
            conn.close()


def create_common_issue(
    title: str,
    category: str,
    hostel: str,
    location_details: str = "",
    description: str = "",
    priority: str = "Medium",
    assigned_to: str = "",
    admin_remarks: str = "",
    created_by: str = "System/Admin",
    conn: Optional[Any] = None
) -> int:
    """Creates a new master common issue record and initial audit history."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        from backend.database.db import ConnectionAdapter
        insert_sql = """
            INSERT INTO common_issues (
                title, category, hostel, location_details, description,
                priority, status, assigned_to, admin_remarks
            )
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        """
        if isinstance(conn, ConnectionAdapter):
            insert_sql += " RETURNING id"
        cur = conn.execute(insert_sql,
            (
                title.strip(),
                category.strip(),
                hostel.strip(),
                location_details.strip() if location_details else None,
                description.strip() if description else None,
                priority.strip() if priority else "Medium",
                assigned_to.strip() if assigned_to else None,
                admin_remarks.strip() if admin_remarks else None
            )
        )

        if isinstance(conn, ConnectionAdapter):
            row = cur.fetchone()
            issue_id = row["id"] if row else None
        else:
            issue_id = cur.lastrowid

        # Ensure issue_code is set (e.g. CI-001)
        issue_code = f"CI-{issue_id:03d}"
        try:
            conn.execute("UPDATE common_issues SET issue_code = ? WHERE id = ?", (issue_code, issue_id))
        except Exception:
            pass

        # Insert initial master history entry
        conn.execute(
            """
            INSERT INTO common_issue_history (common_issue_id, status, remarks, updated_by)
            VALUES (?, 'Pending', 'Common issue created and queued for campus resolution.', ?)
            """,
            (issue_id, created_by)
        )
        conn.commit()
        return issue_id
    finally:
        if close_conn:
            conn.close()


def associate_complaint_to_common_issue(
    complaint_id: int,
    common_issue_id: int,
    conn: Optional[Any] = None
) -> bool:
    """
    Links a student complaint to a common issue and synchronizes current master status.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        issue = conn.execute(
            "SELECT status, assigned_to, admin_remarks, hostel, location_details, category FROM common_issues WHERE id = ?",
            (common_issue_id,)
        ).fetchone()
        complaint = conn.execute(
            "SELECT c.id, c.category, s.hostel, s.room_no FROM complaints c JOIN students s ON s.id=c.student_id WHERE c.id=?",
            (complaint_id,)
        ).fetchone()

        if not issue or not complaint:
            return False
        if not is_active_status(issue["status"]):
            return False
        loc_details = issue["location_details"] if "location_details" in issue.keys() else ""
        if not is_location_compatible(issue["hostel"], loc_details, complaint["hostel"], complaint["room_no"]):
            return False
        if not is_category_compatible(issue["category"], complaint["category"]):
            return False

        # Link complaint and synchronize state
        conn.execute(
            """
            UPDATE complaints
            SET common_issue_id = ?,
                status = ?,
                assigned_to = COALESCE(?, assigned_to),
                remarks = COALESCE(?, remarks)
            WHERE id = ?
            """,
            (
                common_issue_id,
                issue["status"],
                issue["assigned_to"],
                issue["admin_remarks"],
                complaint_id
            )
        )
        conn.commit()
        return True
    finally:
        if close_conn:
            conn.close()


def update_common_issue_once(
    common_issue_id: int,
    status: str,
    remarks: str = "",
    assigned_to: str = "",
    updated_by: str = "Hostel Administration",
    conn: Optional[Any] = None
) -> int:
    """
    THE SCALABILITY ENGINE:
    Admin updates the common issue ONCE.
    Automatically propagates new status, remarks, and assignment to ALL associated
    student complaints in a single efficient SQL query.
    Writes exactly 1 audit history record and 1 shared notification record.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        # 1. Update Common Issue master row
        conn.execute(
            """
            UPDATE common_issues
            SET status = ?,
                admin_remarks = ?,
                assigned_to = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, remarks.strip() if remarks else None, assigned_to.strip() if assigned_to else None, common_issue_id)
        )

        # 2. Propagate to ALL associated complaints in a single set-based SQL query
        cur = conn.execute(
            """
            UPDATE complaints
            SET status = ?,
                remarks = ?,
                assigned_to = ?
            WHERE common_issue_id = ?
            """,
            (status, remarks.strip() if remarks else None, assigned_to.strip() if assigned_to else None, common_issue_id)
        )
        affected_count = cur.rowcount if hasattr(cur, "rowcount") and cur.rowcount != -1 else 0

        # If rowcount wasn't reported by cursor adapter, query affected count
        if affected_count <= 0:
            count_row = conn.execute(
                "SELECT COUNT(*) AS total FROM complaints WHERE common_issue_id = ?",
                (common_issue_id,)
            ).fetchone()
            affected_count = count_row["total"] if count_row else 0

        # 3. Record ONE single audit history entry for the master issue
        history_remark = remarks.strip() if remarks else f"Status transitioned to {status}."
        conn.execute(
            """
            INSERT INTO common_issue_history (common_issue_id, status, remarks, updated_by)
            VALUES (?, ?, ?, ?)
            """,
            (common_issue_id, status, history_remark, updated_by)
        )

        # 4. Record ONE shared notification broadcast for all affected students
        issue_row = conn.execute("SELECT title, hostel FROM common_issues WHERE id = ?", (common_issue_id,)).fetchone()
        issue_title = issue_row["title"] if issue_row else f"Common Issue #{common_issue_id}"
        hostel_name = issue_row["hostel"] if issue_row else "Hostel"

        notification_msg = f"Update on {issue_title} ({hostel_name}): Status marked as '{status}'."
        if remarks:
            notification_msg += f" Note: {remarks.strip()}"

        conn.execute(
            """
            INSERT INTO common_issue_notifications (common_issue_id, message)
            VALUES (?, ?)
            """,
            (common_issue_id, notification_msg)
        )

        # 5. Record individual complaint history entry for each linked complaint
        try:
            linked_complaints = conn.execute(
                "SELECT id FROM complaints WHERE common_issue_id = ?",
                (common_issue_id,)
            ).fetchall()
            for lc in linked_complaints:
                conn.execute(
                    "INSERT INTO complaint_history (complaint_id, status) VALUES (?, ?)",
                    (lc["id"], status)
                )
        except Exception:
            pass

        conn.commit()

        # 6. Broadcast Email Notifications to all distinct affected students
        try:
            from backend.services.email_service import send_common_issue_broadcast_emails
            send_common_issue_broadcast_emails(
                common_issue_id=common_issue_id,
                status=status,
                remarks=remarks,
                assigned_to=assigned_to,
                conn=conn
            )
        except Exception as e:
            logger.exception("Failed to broadcast common issue emails for issue %s: %s", common_issue_id, e)

        return affected_count
    finally:
        if close_conn:
            conn.close()


def unlink_complaint_from_common_issue(
    complaint_id: int,
    common_issue_id: Optional[int] = None,
    conn: Optional[Any] = None
) -> bool:
    """Detaches an individual complaint from a common issue if misclassified."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        if common_issue_id is None:
            cur = conn.execute("UPDATE complaints SET common_issue_id = NULL WHERE id = ?", (complaint_id,))
        else:
            cur = conn.execute("UPDATE complaints SET common_issue_id = NULL WHERE id = ? AND common_issue_id = ?", (complaint_id, common_issue_id))
        conn.commit()
        return cur.rowcount != 0
    finally:
        if close_conn:
            conn.close()


def get_common_issue_with_stats(
    common_issue_id: int,
    conn: Optional[Any] = None
) -> Optional[dict[str, Any]]:
    """Returns a common issue with total affected student count."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        issue = conn.execute(
            "SELECT * FROM common_issues WHERE id = ?",
            (common_issue_id,)
        ).fetchone()

        if not issue:
            return None

        issue_dict = dict(issue)
        count_row = conn.execute(
            "SELECT COUNT(*) AS total_complaints, COUNT(DISTINCT student_id) AS unique_students FROM complaints WHERE common_issue_id = ?",
            (common_issue_id,)
        ).fetchone()
        issue_dict["linked_complaints"] = count_row["total_complaints"] if count_row else 0
        issue_dict["affected_count"] = count_row["unique_students"] if count_row else 0
        issue_dict["affected_students"] = issue_dict["affected_count"]

        # Fetch history
        history = conn.execute(
            "SELECT * FROM common_issue_history WHERE common_issue_id = ? ORDER BY date DESC",
            (common_issue_id,)
        ).fetchall()
        issue_dict["history"] = [dict(h) for h in history]

        return issue_dict
    finally:
        if close_conn:
            conn.close()


def get_all_common_issues(
    conn: Optional[Any] = None,
    status_filter: Optional[str] = None,
    hostel_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    search: Optional[str] = None
) -> list[dict[str, Any]]:
    """Fetches all common issues with calculated affected student counts."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        query = """
            SELECT ci.*,
                   COUNT(c.id) AS linked_complaints, COUNT(DISTINCT c.student_id) AS affected_count, COUNT(DISTINCT c.student_id) AS affected_students
            FROM common_issues ci
            LEFT JOIN complaints c ON c.common_issue_id = ci.id
        """
        where = []
        params = []

        if status_filter:
            where.append("ci.status = ?")
            params.append(status_filter)

        if hostel_filter:
            where.append("LOWER(ci.hostel) = LOWER(?)")
            params.append(hostel_filter)

        if category_filter:
            where.append("LOWER(ci.category) = LOWER(?)")
            params.append(category_filter)

        if search:
            where.append("(ci.title LIKE ? OR ci.description LIKE ? OR ci.hostel LIKE ?)")
            q = f"%{search}%"
            params.extend([q, q, q])

        if where:
            query += " WHERE " + " AND ".join(where)

        query += " GROUP BY ci.id ORDER BY ci.created_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        if close_conn:
            conn.close()


def get_common_issue_complaints(
    common_issue_id: int,
    conn: Optional[Any] = None
) -> list[dict[str, Any]]:
    """Returns complaints associated with a common issue for the admin view."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        rows = conn.execute(
            """
            SELECT c.*, s.name AS student_name, s.id_no AS student_id_no,
                   s.room_no AS student_room_no, s.phone AS student_phone
            FROM complaints c
            JOIN students s ON s.id = c.student_id
            WHERE c.common_issue_id = ?
            ORDER BY c.created_at ASC
            """,
            (common_issue_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if close_conn:
            conn.close()
def find_matching_complaint_for_common_issue(
    category: str,
    hostel: str,
    title: str,
    description: str,
    student_room_no: Optional[str] = None,
    exclude_id: Optional[int] = None,
    conn: Optional[Any] = None,
    threshold: float = 0.50,
    active_only: bool = True
) -> Optional[dict[str, Any]]:
    """
    Searches for an existing complaint in the same hostel and category
    whose text description is semantically similar (>= threshold).
    If active_only is True, filters to only active complaints ('Pending', 'In Progress').
    If active_only is False, matches across both active and historical/closed complaints.
    Strictly checks hostel location and category.
    """
    if not hostel or not category:
        return None

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        query = """
            SELECT c.*, s.hostel, s.room_no
            FROM complaints c
            JOIN students s ON s.id = c.student_id
        """
        params = []
        if exclude_id:
            query += " WHERE c.id != ?"
            params.append(exclude_id)
        query += " ORDER BY c.id DESC"

        complaints = conn.execute(query, params).fetchall()
        if not complaints:
            return None

        complaint_text = f"{title} {description}"
        best_match = None
        best_similarity = 0.0

        for row in complaints:
            comp_active = is_active_status(row["status"])
            if active_only and not comp_active:
                continue

            if not is_category_compatible(category, row["category"]):
                continue

            if not is_location_compatible(hostel, None, row["hostel"], row["room_no"] if "room_no" in row.keys() else None):
                continue

            existing_text = f"{row['title']} {row['description'] or ''}"

            # Underlying problem intent compatibility check
            comp_intent = analyze_complaint_intent(complaint_text, category)
            existing_intent = analyze_complaint_intent(existing_text, row["category"])
            is_compat, _ = are_underlying_problems_compatible(comp_intent, existing_intent)
            if not is_compat:
                continue

            sim = calculate_text_similarity(complaint_text, existing_text)
            if sim >= threshold and sim > best_similarity:
                best_similarity = sim
                best_match = dict(row)
                best_match["similarity"] = round(sim * 100, 1)
                best_match["is_active"] = comp_active

        return best_match
    finally:
        if close_conn:
            conn.close()


def process_complaint_common_issue(
    complaint_id: int,
    category: str,
    hostel: str,
    title: str,
    description: str,
    priority: str = "Medium",
    conn: Optional[Any] = None
) -> tuple[Optional[int], Optional[int], Optional[float]]:
    """
    Core status-aware AI grouping engine:
    1. Checks if an ACTIVE Common Issue exists in the same hostel/category.
       If yes, links complaint to it.
    2. If no active Common Issue, checks if an ACTIVE existing complaint matches:
       - If that complaint already belongs to an active Common Issue, links to it.
       - If its Common Issue is inactive/resolved, creates a NEW Common Issue for the new complaint.
       - If it has no Common Issue, creates a NEW Common Issue and links BOTH active complaints.
    3. If no active match exists, checks if a HISTORICAL (Resolved / Closed / Inactive)
       Common Issue or complaint matches:
       - The matching issue/complaint is NOT currently active (was resolved in the past).
       - Automatically creates a NEW Common Issue with status 'Pending' for this new occurrence!
       - Links the new complaint to this new Common Issue.
    4. If neither matches, returns (None, None, None).
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        # Fetch student details for room-level location matching
        st_row = conn.execute(
            "SELECT s.hostel, s.room_no FROM complaints c JOIN students s ON s.id=c.student_id WHERE c.id = ?",
            (complaint_id,)
        ).fetchone()
        student_room_no = st_row["room_no"] if st_row else None
        effective_hostel = (st_row["hostel"] if st_row and st_row["hostel"] else hostel).strip()

        # Step 1: Check existing ACTIVE Common Issue
        matched_issue = find_matching_common_issue(
            category=category,
            hostel=effective_hostel,
            title=title,
            description=description,
            student_room_no=student_room_no,
            conn=conn,
            threshold=0.50,
            active_only=True
        )
        if matched_issue:
            issue_id = matched_issue["id"]
            associate_complaint_to_common_issue(complaint_id, issue_id, conn)
            conn.execute(
                "UPDATE complaints SET ai_duplicate_id = NULL, ai_duplicate_similarity = ? WHERE id = ?",
                (matched_issue.get("similarity"), complaint_id)
            )
            conn.commit()
            return (issue_id, None, matched_issue.get("similarity"))

        # Step 2: Check ACTIVE existing complaints in same hostel & category
        matched_comp = find_matching_complaint_for_common_issue(
            category=category,
            hostel=effective_hostel,
            title=title,
            description=description,
            student_room_no=student_room_no,
            exclude_id=complaint_id,
            conn=conn,
            threshold=0.50,
            active_only=True
        )
        if matched_comp:
            target_issue_id = matched_comp.get("common_issue_id")
            if target_issue_id:
                target_issue = conn.execute(
                    "SELECT id, status FROM common_issues WHERE id = ?",
                    (target_issue_id,)
                ).fetchone()
                if target_issue and is_active_status(target_issue["status"]):
                    associate_complaint_to_common_issue(complaint_id, target_issue_id, conn)
                    conn.execute(
                        "UPDATE complaints SET ai_duplicate_id = ?, ai_duplicate_similarity = ? WHERE id = ?",
                        (matched_comp["id"], matched_comp["similarity"], complaint_id)
                    )
                    conn.commit()
                    return (target_issue_id, matched_comp["id"], matched_comp["similarity"])
                else:
                    # Associated Common Issue is inactive/resolved: create a NEW Common Issue!
                    base_title = title.strip()
                    issue_title = f"{hostel} - {base_title}" if hostel.lower() not in base_title.lower() else base_title
                    new_issue_id = create_common_issue(
                        title=issue_title,
                        category=category,
                        hostel=hostel,
                        location_details=f"{hostel} Common Area",
                        description=f"Auto-grouped master issue for {base_title} in {hostel}.",
                        priority=priority,
                        created_by="IntelliHostel AI Grouping Engine",
                        conn=conn
                    )
                    associate_complaint_to_common_issue(complaint_id, new_issue_id, conn)
                    conn.execute(
                        "UPDATE complaints SET ai_duplicate_id = ?, ai_duplicate_similarity = ? WHERE id = ?",
                        (matched_comp["id"], matched_comp["similarity"], complaint_id)
                    )
                    conn.commit()
                    return (new_issue_id, matched_comp["id"], matched_comp["similarity"])
            else:
                base_title = matched_comp["title"]
                issue_title = f"{hostel} - {base_title}" if hostel.lower() not in base_title.lower() else base_title
                priorities = [priority.lower(), (matched_comp.get("priority") or "").lower()]
                chosen_priority = "High" if any("high" in p or "critical" in p for p in priorities) else "Medium"

                new_issue_id = create_common_issue(
                    title=issue_title,
                    category=category,
                    hostel=hostel,
                    location_details=f"{hostel} Common Area",
                    description=f"Auto-grouped master issue for {base_title} affecting multiple students in {hostel}.",
                    priority=chosen_priority,
                    created_by="IntelliHostel AI Grouping Engine",
                    conn=conn
                )

                associate_complaint_to_common_issue(matched_comp["id"], new_issue_id, conn)
                associate_complaint_to_common_issue(complaint_id, new_issue_id, conn)

                conn.execute(
                    "UPDATE complaints SET ai_duplicate_id = ?, ai_duplicate_similarity = ? WHERE id = ?",
                    (matched_comp["id"], matched_comp["similarity"], complaint_id)
                )
                conn.commit()
                return (new_issue_id, matched_comp["id"], matched_comp["similarity"])

        # Step 3: Check HISTORICAL matches (Common Issue or Complaint)
        # When an inactive/resolved issue matches, create a NEW Common Issue
        matched_hist_issue = find_matching_common_issue(
            category=category,
            hostel=effective_hostel,
            title=title,
            description=description,
            student_room_no=student_room_no,
            conn=conn,
            threshold=0.50,
            active_only=False
        )
        if matched_hist_issue:
            base_title = title.strip()
            issue_title = f"{hostel} - {base_title}" if hostel.lower() not in base_title.lower() else base_title
            new_issue_id = create_common_issue(
                title=issue_title,
                category=category,
                hostel=hostel,
                location_details=matched_hist_issue.get("location_details") or f"{hostel} Common Area",
                description=f"Auto-grouped master issue for {base_title} in {hostel} (recurrence after previous issue #{matched_hist_issue['id']} was {matched_hist_issue['status']}).",
                priority=priority,
                created_by="IntelliHostel AI Grouping Engine",
                conn=conn
            )
            associate_complaint_to_common_issue(complaint_id, new_issue_id, conn)
            conn.execute(
                "UPDATE complaints SET ai_duplicate_id = NULL, ai_duplicate_similarity = ? WHERE id = ?",
                (matched_hist_issue.get("similarity"), complaint_id)
            )
            conn.commit()
            return (new_issue_id, None, matched_hist_issue.get("similarity"))

        matched_hist_comp = find_matching_complaint_for_common_issue(
            category=category,
            hostel=effective_hostel,
            title=title,
            description=description,
            student_room_no=student_room_no,
            exclude_id=complaint_id,
            conn=conn,
            threshold=0.50,
            active_only=False
        )
        if matched_hist_comp:
            base_title = title.strip()
            issue_title = f"{hostel} - {base_title}" if hostel.lower() not in base_title.lower() else base_title
            new_issue_id = create_common_issue(
                title=issue_title,
                category=category,
                hostel=hostel,
                location_details=f"{hostel} Common Area",
                description=f"Auto-grouped master issue for {base_title} in {hostel}.",
                priority=priority,
                created_by="IntelliHostel AI Grouping Engine",
                conn=conn
            )
            associate_complaint_to_common_issue(complaint_id, new_issue_id, conn)
            conn.execute(
                "UPDATE complaints SET ai_duplicate_id = ?, ai_duplicate_similarity = ? WHERE id = ?",
                (matched_hist_comp["id"], matched_hist_comp["similarity"], complaint_id)
            )
            conn.commit()
            return (new_issue_id, matched_hist_comp["id"], matched_hist_comp["similarity"])

        # Step 4: No match at all
        return (None, None, None)
    finally:
        if close_conn:
            conn.close()


def group_existing_duplicate_complaints(conn: Optional[Any] = None) -> int:
    """
    Scans existing unlinked active complaints in the database,
    identifies pairs or clusters of similar complaints in the same hostel and category,
    and groups them into Common Issues.
    Returns the count of complaints successfully grouped.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        raw_unlinked = conn.execute(
            """
            SELECT c.id, c.title, c.description, c.category, c.priority, c.status, s.hostel
            FROM complaints c
            JOIN students s ON s.id = c.student_id
            WHERE (c.common_issue_id IS NULL OR c.common_issue_id = 0)
            ORDER BY c.id ASC
            """
        ).fetchall()

        unlinked = [c for c in raw_unlinked if is_active_status(c["status"])]

        if len(unlinked) < 2:
            return 0

        grouped_count = 0
        visited = set()

        for i, c1 in enumerate(unlinked):
            if c1["id"] in visited:
                continue

            cluster = [c1]
            text1 = f"{c1['title']} {c1['description'] or ''}"

            for j in range(i + 1, len(unlinked)):
                c2 = unlinked[j]
                if c2["id"] in visited:
                    continue

                if (c1["hostel"] or "").strip().lower() != (c2["hostel"] or "").strip().lower():
                    continue
                if (c1["category"] or "").strip().lower() != (c2["category"] or "").strip().lower():
                    continue

                text2 = f"{c2['title']} {c2['description'] or ''}"
                sim = calculate_text_similarity(text1, text2)

                if sim >= 0.50:
                    cluster.append(c2)
                    visited.add(c2["id"])

            if len(cluster) > 1:
                visited.add(c1["id"])
                hostel = (c1["hostel"] or "Hostel").strip()
                category = (c1["category"] or "General").strip()

                existing_issue = find_matching_common_issue(
                    category=category,
                    hostel=hostel,
                    title=c1["title"],
                    description=c1["description"] or "",
                    conn=conn,
                    threshold=0.50,
                    active_only=True
                )
                if existing_issue:
                    issue_id = existing_issue["id"]
                else:
                    base_title = c1["title"]
                    issue_title = f"{hostel} - {base_title}" if hostel.lower() not in base_title.lower() else base_title
                    has_high = any("high" in (c.get("priority") or "").lower() for c in cluster)
                    issue_id = create_common_issue(
                        title=issue_title,
                        category=category,
                        hostel=hostel,
                        location_details=f"{hostel} Common Area",
                        description=f"Consolidated master issue tracking {base_title} affecting multiple students in {hostel}.",
                        priority="High" if has_high else "Medium",
                        created_by="IntelliHostel AI Grouping Engine",
                        conn=conn
                    )

                first_id = cluster[0]["id"]
                for k, comp in enumerate(cluster):
                    associate_complaint_to_common_issue(comp["id"], issue_id, conn)
                    grouped_count += 1
                    if k > 0:
                        sim_val = round(calculate_text_similarity(text1, f"{comp['title']} {comp['description'] or ''}") * 100, 1)
                        conn.execute(
                            "UPDATE complaints SET ai_duplicate_id = ?, ai_duplicate_similarity = ? WHERE id = ?",
                            (first_id, sim_val, comp["id"])
                        )
                conn.commit()

        return grouped_count
    finally:
        if close_conn:
            conn.close()


def associate_matching_complaints_to_master_issue(
    master_issue_id: int,
    conn: Optional[Any] = None,
    threshold: float = 0.50
) -> int:
    """
    Identifies eligible existing student complaints that match the newly created
    or existing Master Issue according to the project's common issue matching rules:
    - Active statuses: Pending, In Progress
    - Category compatibility (including standard aliases)
    - Location compatibility (respecting hostel boundaries, supporting room numbers)
    - Cosine text similarity >= threshold (default 0.50)
    - Considers unlinked complaints OR complaints in auto-created common issues
    - Synchronizes status, assigned staff, and remarks
    - Cleans up empty orphaned auto-created common issues
    Returns the count of complaints associated.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        issue = conn.execute(
            "SELECT * FROM common_issues WHERE id = ?",
            (master_issue_id,)
        ).fetchone()

        if not issue or not is_active_status(issue["status"]):
            return 0

        issue_text = f"{issue['title']} {issue['description'] or ''}"
        issue_hostel = issue["hostel"]
        issue_location_details = issue["location_details"] if "location_details" in issue.keys() else ""
        issue_category = issue["category"]
        issue_intent = analyze_complaint_intent(issue_text, issue_category)

        # Fetch all active complaints with student details
        raw_complaints = conn.execute(
            """
            SELECT c.id, c.title, c.description, c.category, c.status, c.common_issue_id,
                   s.hostel, s.room_no
            FROM complaints c
            JOIN students s ON s.id = c.student_id
            WHERE LOWER(TRIM(c.status)) IN ('pending', 'in progress')
            ORDER BY c.id ASC
            """
        ).fetchall()

        associated_count = 0
        superseded_issue_ids = set()

        for c in raw_complaints:
            cid = c["id"]
            current_issue_id = c["common_issue_id"]

            # Skip if already linked to this master issue
            if current_issue_id == master_issue_id:
                continue

            # Check category compatibility
            if not is_category_compatible(issue_category, c["category"]):
                continue

            # Check location compatibility
            if not is_location_compatible(issue_hostel, issue_location_details, c["hostel"], c["room_no"]):
                continue

            comp_text = f"{c['title']} {c['description'] or ''}".strip()

            # Underlying problem intent compatibility check
            c_intent = analyze_complaint_intent(comp_text, c["category"])
            is_compat, _ = are_underlying_problems_compatible(issue_intent, c_intent)
            if not is_compat:
                continue

            # Check text similarity across full text and title pairs to avoid penalizing varying description lengths
            sim = max(
                calculate_text_similarity(issue_text, comp_text),
                calculate_text_similarity(issue["title"], c["title"]),
                calculate_text_similarity(issue["title"], comp_text),
                calculate_text_similarity(issue_text, c["title"])
            )
            if sim < threshold:
                continue

            # Check existing relationship:
            # Eligible if unlinked, OR if current issue is an auto-created issue
            is_eligible = False
            if current_issue_id is None or current_issue_id == 0:
                is_eligible = True
            else:
                curr_ci = conn.execute(
                    "SELECT id, assigned_to FROM common_issues WHERE id = ?",
                    (current_issue_id,)
                ).fetchone()
                if curr_ci:
                    hist = conn.execute(
                        "SELECT updated_by FROM common_issue_history WHERE common_issue_id = ? ORDER BY id ASC LIMIT 1",
                        (current_issue_id,)
                    ).fetchone()
                    created_by_ai = hist and "ai grouping engine" in str(hist["updated_by"]).lower()
                    if created_by_ai or not curr_ci["assigned_to"]:
                        is_eligible = True
                        superseded_issue_ids.add(current_issue_id)

            if is_eligible:
                if associate_complaint_to_common_issue(cid, master_issue_id, conn):
                    associated_count += 1

        # Clean up any superseded auto-issues that now have zero linked complaints
        for old_id in superseded_issue_ids:
            remaining = conn.execute(
                "SELECT COUNT(*) AS total FROM complaints WHERE common_issue_id = ?",
                (old_id,)
            ).fetchone()["total"]
            if remaining == 0:
                try:
                    conn.execute("DELETE FROM common_issue_notifications WHERE common_issue_id = ?", (old_id,))
                    conn.execute("DELETE FROM common_issue_history WHERE common_issue_id = ?", (old_id,))
                    conn.execute("DELETE FROM common_issues WHERE id = ?", (old_id,))
                except Exception:
                    pass

        conn.commit()
        return associated_count
    finally:
        if close_conn:
            conn.close()
