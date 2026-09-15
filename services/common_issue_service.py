"""
IntelliHostel — Common Issue Management & Scalability Service.
Handles grouping of multiple student complaints into master common issues,
single-action admin propagation, shared notifications, and audit tracking.
"""
from __future__ import annotations

import re
import math
from collections import Counter
from typing import Any, Optional
from database.db import get_db_connection

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


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    filtered = [w for w in words if w not in STOP_WORDS and len(w) > 1]
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
    threshold: float = 0.50
) -> Optional[dict[str, Any]]:
    """
    Finds an active common issue matching the exact hostel/location and category,
    with title/description similarity meeting the safe threshold.
    Strictly prevents merging complaints across different hostels.
    """
    if not hostel or not category:
        return None

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        # Only search active/unresolved issues in the SAME hostel and SAME category
        issues = conn.execute(
            """
            SELECT * FROM common_issues
            WHERE status != 'Resolved'
              AND LOWER(TRIM(hostel)) = LOWER(TRIM(?))
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
            issue_text = f"{issue['title']} {issue['description'] or ''}"
            sim = calculate_text_similarity(complaint_text, issue_text)
            if sim >= threshold and sim > best_similarity:
                best_similarity = sim
                best_match = dict(issue)
                best_match["similarity"] = round(sim * 100, 1)

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

        conn.commit()
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
