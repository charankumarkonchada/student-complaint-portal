from flask import Blueprint, render_template, redirect, url_for, session
from database.db import get_db_connection
from services.auth_service import student_required

activity_bp = Blueprint("activity", __name__)

@activity_bp.route("/activity")
def activity():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaints_rows = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC LIMIT 10",
        (session["student_id"],)
    ).fetchall()

    history = conn.execute(
        """
        SELECT h.*, c.title
        FROM complaint_history h
        JOIN complaints c ON c.id=h.complaint_id
        WHERE c.student_id=?
        ORDER BY h.date DESC
        LIMIT 30
        """,
        (session["student_id"],)
    ).fetchall()
    conn.close()

    return render_template(
        "vennela/activity.html",
        complaints=complaints_rows,
        history=history
    )
