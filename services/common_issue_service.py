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
from database.db import get_db_connection

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
    conn: Optional[Any] = None,
    threshold: float = 0.50,
    active_only: bool = True
) -> Optional[dict[str, Any]]:
    """
    Finds a common issue matching the exact hostel/location and category,
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
            WHERE LOWER(TRIM(hostel)) = LOWER(TRIM(?))
              AND LOWER(TRIM(category)) = LOWER(TRIM(?))
            ORDER BY id DESC
            """,
            (hostel, category)
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

            issue_text = f"{issue['title']} {issue['description'] or ''}"
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
        cur = conn.execute(
            """
            INSERT INTO common_issues (
                title, category, hostel, location_details, description,
                priority, status, assigned_to, admin_remarks
            )
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
            """,
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

        issue_id = cur.lastrowid
        # In PostgreSQL ConnectionAdapter, lastrowid may be None, so fetch id
        if not issue_id:
            row = conn.execute("SELECT id FROM common_issues ORDER BY id DESC LIMIT 1").fetchone()
            issue_id = row["id"] if row else None

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
            "SELECT status, assigned_to, admin_remarks FROM common_issues WHERE id = ?",
            (common_issue_id,)
        ).fetchone()

        if not issue:
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
            from services.email_service import send_common_issue_broadcast_emails
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
    conn: Optional[Any] = None
) -> bool:
    """Detaches an individual complaint from a common issue if misclassified."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        conn.execute(
            "UPDATE complaints SET common_issue_id = NULL WHERE id = ?",
            (complaint_id,)
        )
        conn.commit()
        return True
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
            "SELECT COUNT(*) AS total FROM complaints WHERE common_issue_id = ?",
            (common_issue_id,)
        ).fetchone()
        issue_dict["affected_count"] = count_row["total"] if count_row else 0

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
                   COUNT(c.id) AS affected_count
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
            SELECT c.*, s.hostel
            FROM complaints c
            JOIN students s ON s.id = c.student_id
            WHERE LOWER(TRIM(s.hostel)) = LOWER(TRIM(?))
              AND LOWER(TRIM(c.category)) = LOWER(TRIM(?))
        """
        params = [hostel, category]
        if exclude_id:
            query += " AND c.id != ?"
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

            existing_text = f"{row['title']} {row['description'] or ''}"
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
        # Step 1: Check existing ACTIVE Common Issue
        matched_issue = find_matching_common_issue(
            category=category,
            hostel=hostel,
            title=title,
            description=description,
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
            hostel=hostel,
            title=title,
            description=description,
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
            hostel=hostel,
            title=title,
            description=description,
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
            hostel=hostel,
            title=title,
            description=description,
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

