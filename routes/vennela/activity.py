from flask import Blueprint, render_template, redirect, url_for, session
from database.db import get_db_connection
from services.auth_service import student_required

activity_bp = Blueprint("activity", __name__)

@activity_bp.route("/activity")
def activity():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()

    complaints_rows = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC LIMIT 10",
        (sid,)
    ).fetchall()

    ind_history = conn.execute(
        """
        SELECT h.id, h.complaint_id, h.status, h.date, c.title,
               COALESCE(c.remarks, '') AS remarks,
               'Hostel Staff' AS updated_by
        FROM complaint_history h
        JOIN complaints c ON c.id=h.complaint_id
        WHERE c.student_id=?
        ORDER BY h.date DESC
        LIMIT 30
        """,
        (sid,)
    ).fetchall()

    common_history = conn.execute(
        """
        SELECT DISTINCT cih.id, c.id AS complaint_id, cih.status, cih.date,
               ci.title, COALESCE(cih.remarks, '') AS remarks, cih.updated_by
        FROM common_issue_history cih
        JOIN common_issues ci ON ci.id=cih.common_issue_id
        JOIN complaints c ON c.common_issue_id=cih.common_issue_id
        WHERE c.student_id=?
        ORDER BY cih.date DESC
        LIMIT 30
        """,
        (sid,)
    ).fetchall()

    combined_history = [dict(h) for h in ind_history] + [dict(h) for h in common_history]
    combined_history.sort(key=lambda x: str(x.get("date", "")), reverse=True)

    conn.close()

    return render_template(
        "vennela/activity.html",
        complaints=complaints_rows,
        history=combined_history[:30]
    )
