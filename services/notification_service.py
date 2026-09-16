from datetime import datetime, timedelta, timezone
import logging
import config
from typing import Optional, Dict, Any, List
from database.db import get_db_connection

logger = logging.getLogger(__name__)

DEFAULT_AUTO_ARCHIVE_DAYS = config.NOTIFICATION_RETENTION_DAYS
MAX_ACTIVE_READ_NOTIFICATIONS = config.MAX_ACTIVE_READ_NOTIFICATIONS


def auto_archive_notifications(
    student_id: Optional[int] = None,
    conn=None,
    days_retention: int = DEFAULT_AUTO_ARCHIVE_DAYS,
    max_active_read: int = MAX_ACTIVE_READ_NOTIFICATIONS
) -> int:
    """
    Automated lifecycle transition from READ to ARCHIVED.
    
    Rules applied:
    1. Time-based: Read notifications older than days_retention are auto-archived.
    2. Capacity cap: Excess read notifications beyond max_active_read are auto-archived.
    
    Returns total count of notifications transitioned to archived.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        archived_count = 0
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days_retention)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Time-based auto-archiving for individual notifications
        if student_id is not None:
            cur1 = conn.execute(
                """
                UPDATE notifications
                SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
                  AND is_read = 1
                  AND (is_archived = 0 OR is_archived IS NULL)
                  AND created_at <= ?
                """,
                (student_id, cutoff_str)
            )
            archived_count += cur1.rowcount if hasattr(cur1, "rowcount") and cur1.rowcount is not None and cur1.rowcount > 0 else 0

            # Time-based auto-archiving for common issue reads
            cur2 = conn.execute(
                """
                UPDATE notification_reads
                SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
                  AND (is_archived = 0 OR is_archived IS NULL)
                  AND common_issue_notification_id IN (
                      SELECT id FROM common_issue_notifications WHERE created_at <= ?
                  )
                """,
                (student_id, cutoff_str)
            )
            archived_count += cur2.rowcount if hasattr(cur2, "rowcount") and cur2.rowcount is not None and cur2.rowcount > 0 else 0

            # 2. Capacity cap for individual read notifications
            excess_rows = conn.execute(
                """
                SELECT id FROM notifications
                WHERE student_id = ?
                  AND is_read = 1
                  AND (is_archived = 0 OR is_archived IS NULL)
                ORDER BY created_at DESC
                """,
                (student_id,)
            ).fetchall()

            if len(excess_rows) > max_active_read:
                excess_ids = [r["id"] for r in excess_rows[max_active_read:]]
                for eid in excess_ids:
                    conn.execute(
                        "UPDATE notifications SET is_archived = 1, archived_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (eid,)
                    )
                    archived_count += 1
        else:
            # System-wide time-based auto-archiving
            cur1 = conn.execute(
                """
                UPDATE notifications
                SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
                WHERE is_read = 1
                  AND (is_archived = 0 OR is_archived IS NULL)
                  AND created_at <= ?
                """,
                (cutoff_str,)
            )
            archived_count += cur1.rowcount if hasattr(cur1, "rowcount") and cur1.rowcount is not None and cur1.rowcount > 0 else 0

            cur2 = conn.execute(
                """
                UPDATE notification_reads
                SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
                WHERE (is_archived = 0 OR is_archived IS NULL)
                  AND common_issue_notification_id IN (
                      SELECT id FROM common_issue_notifications WHERE created_at <= ?
                  )
                """,
                (cutoff_str,)
            )
            archived_count += cur2.rowcount if hasattr(cur2, "rowcount") and cur2.rowcount is not None and cur2.rowcount > 0 else 0

        conn.commit()
        return archived_count
    except Exception as e:
        logger.exception("Error during auto_archive_notifications: %s", e)
        return 0
    finally:
        if close_conn:
            conn.close()


def archive_single_notification(
    student_id: int,
    notif_id: int,
    notif_type: str = "individual",
    conn=None
) -> bool:
    """
    Manually transitions a single notification to ARCHIVED.
    Automatically marks it as read if it was unread.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        norm_type = notif_type.strip().lower() if notif_type else ""

        if norm_type == "common":
            cin = conn.execute(
                """
                SELECT cin.id
                FROM common_issue_notifications cin
                JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                WHERE cin.id = ? AND c.student_id = ?
                """,
                (notif_id, student_id)
            ).fetchone()
            if cin:
                conn.execute(
                    """
                    INSERT INTO notification_reads (common_issue_notification_id, student_id, is_archived, archived_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (common_issue_notification_id, student_id)
                    DO UPDATE SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
                    """,
                    (notif_id, student_id)
                )
                conn.commit()
                return True
            return False

        elif norm_type == "individual":
            conn.execute(
                """
                UPDATE notifications
                SET is_archived = 1, archived_at = CURRENT_TIMESTAMP, is_read = 1
                WHERE id = ? AND student_id = ?
                """,
                (notif_id, student_id)
            )
            conn.commit()
            return True

        else:
            # Fallback auto-detection
            notif = conn.execute(
                "SELECT id FROM notifications WHERE id = ? AND student_id = ?",
                (notif_id, student_id)
            ).fetchone()
            if notif:
                conn.execute(
                    """
                    UPDATE notifications
                    SET is_archived = 1, archived_at = CURRENT_TIMESTAMP, is_read = 1
                    WHERE id = ? AND student_id = ?
                    """,
                    (notif_id, student_id)
                )
                conn.commit()
                return True

            cin = conn.execute(
                """
                SELECT cin.id
                FROM common_issue_notifications cin
                JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                WHERE cin.id = ? AND c.student_id = ?
                """,
                (notif_id, student_id)
            ).fetchone()
            if cin:
                conn.execute(
                    """
                    INSERT INTO notification_reads (common_issue_notification_id, student_id, is_archived, archived_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (common_issue_notification_id, student_id)
                    DO UPDATE SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
                    """,
                    (notif_id, student_id)
                )
                conn.commit()
                return True

            return False
    finally:
        if close_conn:
            conn.close()


def unarchive_single_notification(
    student_id: int,
    notif_id: int,
    notif_type: str = "individual",
    conn=None
) -> bool:
    """
    Restores an archived notification back to the active notification inbox.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        norm_type = notif_type.strip().lower() if notif_type else ""

        if norm_type == "common":
            conn.execute(
                """
                UPDATE notification_reads
                SET is_archived = 0, archived_at = NULL
                WHERE common_issue_notification_id = ? AND student_id = ?
                """,
                (notif_id, student_id)
            )
            conn.commit()
            return True

        elif norm_type == "individual":
            conn.execute(
                """
                UPDATE notifications
                SET is_archived = 0, archived_at = NULL
                WHERE id = ? AND student_id = ?
                """,
                (notif_id, student_id)
            )
            conn.commit()
            return True

        else:
            notif = conn.execute(
                "SELECT id FROM notifications WHERE id = ? AND student_id = ?",
                (notif_id, student_id)
            ).fetchone()
            if notif:
                conn.execute(
                    """
                    UPDATE notifications
                    SET is_archived = 0, archived_at = NULL
                    WHERE id = ? AND student_id = ?
                    """,
                    (notif_id, student_id)
                )
                conn.commit()
                return True

            conn.execute(
                """
                UPDATE notification_reads
                SET is_archived = 0, archived_at = NULL
                WHERE common_issue_notification_id = ? AND student_id = ?
                """,
                (notif_id, student_id)
            )
            conn.commit()
            return True
    finally:
        if close_conn:
            conn.close()


def archive_all_read_notifications(
    student_id: int,
    conn=None
) -> int:
    """
    Bulk archives all active READ notifications for this student.
    Leaves unread notifications in the active inbox.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        cur1 = conn.execute(
            """
            UPDATE notifications
            SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
            WHERE student_id = ?
              AND is_read = 1
              AND (is_archived = 0 OR is_archived IS NULL)
            """,
            (student_id,)
        )
        count = cur1.rowcount if hasattr(cur1, "rowcount") and cur1.rowcount is not None and cur1.rowcount > 0 else 0

        cur2 = conn.execute(
            """
            UPDATE notification_reads
            SET is_archived = 1, archived_at = CURRENT_TIMESTAMP
            WHERE student_id = ?
              AND (is_archived = 0 OR is_archived IS NULL)
            """,
            (student_id,)
        )
        count += cur2.rowcount if hasattr(cur2, "rowcount") and cur2.rowcount is not None and cur2.rowcount > 0 else 0

        conn.commit()
        return count
    finally:
        if close_conn:
            conn.close()


def get_student_notifications(
    student_id: int,
    view: str = "active",
    conn=None,
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """
    Fetches student notifications segmented by view ('active' or 'archived')
    along with comprehensive lifecycle metrics.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        norm_view = view.strip().lower() if view else "active"

        if norm_view == "archived":
            # Archived individual notifications
            ind_rows = conn.execute(
                """
                SELECT id, student_id, message, is_read, is_archived, archived_at, created_at, 'individual' AS notif_type
                FROM notifications
                WHERE student_id = ? AND is_archived = 1
                ORDER BY COALESCE(archived_at, created_at) DESC
                """,
                (student_id,)
            ).fetchall()

            # Archived shared common issue notifications
            common_rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT DISTINCT cin.id, ? AS student_id, cin.message,
                           1 AS is_read,
                           1 AS is_archived,
                           nr.archived_at,
                           cin.created_at, 'common' AS notif_type
                    FROM common_issue_notifications cin
                    JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                    JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
                    WHERE c.student_id = ? AND nr.is_archived = 1
                ) sub
                ORDER BY COALESCE(archived_at, created_at) DESC
                """,
                (student_id, student_id, student_id)
            ).fetchall()

        else:
            # Active individual notifications
            ind_rows = conn.execute(
                """
                SELECT id, student_id, message, is_read, is_archived, archived_at, created_at, 'individual' AS notif_type
                FROM notifications
                WHERE student_id = ? AND (is_archived = 0 OR is_archived IS NULL)
                ORDER BY created_at DESC
                """,
                (student_id,)
            ).fetchall()

            # Active shared common issue notifications
            common_rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT DISTINCT cin.id, ? AS student_id, cin.message,
                           CASE WHEN nr.id IS NOT NULL THEN 1 ELSE 0 END AS is_read,
                           COALESCE(nr.is_archived, 0) AS is_archived,
                           nr.archived_at,
                           cin.created_at, 'common' AS notif_type
                    FROM common_issue_notifications cin
                    JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                    LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
                    WHERE c.student_id = ? AND (nr.is_archived = 0 OR nr.is_archived IS NULL)
                ) sub
                ORDER BY created_at DESC
                """,
                (student_id, student_id, student_id)
            ).fetchall()

        items = [dict(r) for r in ind_rows] + [dict(r) for r in common_rows]
        if norm_view == "archived":
            items.sort(key=lambda x: str(x.get("archived_at") or x.get("created_at") or ""), reverse=True)
        else:
            items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

        # Compute accurate counts for stats bar and tabs
        # 1. Active unread count
        ind_unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE student_id = ? AND is_read = 0 AND (is_archived = 0 OR is_archived IS NULL)",
            (student_id,)
        ).fetchone()[0]

        common_unread = conn.execute(
            """
            SELECT COUNT(DISTINCT cin.id)
            FROM common_issue_notifications cin
            JOIN complaints c ON c.common_issue_id = cin.common_issue_id
            LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
            WHERE c.student_id = ? AND nr.id IS NULL
            """,
            (student_id, student_id)
        ).fetchone()[0]
        unread_total = ind_unread + common_unread

        # 2. Active total count
        ind_active = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE student_id = ? AND (is_archived = 0 OR is_archived IS NULL)",
            (student_id,)
        ).fetchone()[0]

        common_active = conn.execute(
            """
            SELECT COUNT(DISTINCT cin.id)
            FROM common_issue_notifications cin
            JOIN complaints c ON c.common_issue_id = cin.common_issue_id
            LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
            WHERE c.student_id = ? AND (nr.is_archived = 0 OR nr.is_archived IS NULL)
            """,
            (student_id, student_id)
        ).fetchone()[0]
        active_total = ind_active + common_active

        # 3. Archived total count
        ind_archived = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE student_id = ? AND is_archived = 1",
            (student_id,)
        ).fetchone()[0]

        common_archived = conn.execute(
            """
            SELECT COUNT(DISTINCT cin.id)
            FROM common_issue_notifications cin
            JOIN complaints c ON c.common_issue_id = cin.common_issue_id
            JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
            WHERE c.student_id = ? AND nr.is_archived = 1
            """,
            (student_id, student_id)
        ).fetchone()[0]
        archived_total = ind_archived + common_archived

        active_read_total = max(0, active_total - unread_total)

        page = max(1, int(page or 1))
        per_page = min(50, max(1, int(per_page or 20)))
        total_items = len(items)
        start = (page - 1) * per_page
        paged_items = items[start:start + per_page]
        total_pages = max(1, (total_items + per_page - 1) // per_page)

        return {
            "items": paged_items,
            "view": norm_view,
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages,
            "active_total": active_total,
            "unread_total": unread_total,
            "active_read_total": active_read_total,
            "archived_total": archived_total
        }
    finally:
        if close_conn:
            conn.close()
