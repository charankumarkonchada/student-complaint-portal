import os
import sys
import subprocess
from flask import session
from database.db import get_db_connection
import config

def init_database():
    """Initializes the database schema and default admin user."""
    try:
        from database.create_db import main as run_create_db
        run_create_db()
    except Exception:
        script = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "database",
            "create_db.py"
        )
        subprocess.run([sys.executable, script], check=True)

def complaint_for_student(conn, complaint_id):
    """Fetches a complaint belonging to the currently logged in student."""
    return conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE id=?
        AND student_id=?
        """,
        (complaint_id, session.get("student_id"))
    ).fetchone()

def unread_count():
    """Calculates unread notifications count for the active student session (both individual and common)."""
    if "student_id" not in session:
        return 0

    try:
        conn = get_db_connection()
        sid = session["student_id"]
        
        # Count unread individual notifications (excluding archived)
        ind_row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM notifications
            WHERE student_id=?
            AND is_read=0
            AND (is_archived=0 OR is_archived IS NULL)
            """,
            (sid,)
        ).fetchone()
        ind_count = ind_row["total"] if ind_row else 0

        # Count unread common issue notifications (excluding archived/read)
        common_row = conn.execute(
            """
            SELECT COUNT(DISTINCT cin.id) AS total
            FROM common_issue_notifications cin
            JOIN complaints c ON c.common_issue_id = cin.common_issue_id
            LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
            WHERE c.student_id = ? AND nr.id IS NULL
            """,
            (sid, sid)
        ).fetchone()
        common_count = common_row["total"] if common_row else 0

        conn.close()
        return ind_count + common_count
    except Exception:
        return 0
