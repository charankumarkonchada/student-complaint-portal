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
    """Calculates unread notifications count for the active student session."""
    if "student_id" not in session:
        return 0

    try:
        conn = get_db_connection()
        value = conn.execute(
            """
            SELECT COUNT(*)
            FROM notifications
            WHERE student_id=?
            AND is_read=0
            """,
            (session["student_id"],)
        ).fetchone()[0]
        conn.close()
        return value
    except Exception:
        return 0
