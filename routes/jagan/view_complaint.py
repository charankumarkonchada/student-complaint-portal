from flask import Blueprint, render_template, redirect, url_for, flash
from database.db import get_db_connection
from database.queries import complaint_for_student
from services.auth_service import student_required
from services.common_issue_service import get_common_issue_with_stats

view_complaint_bp = Blueprint("view_complaint", __name__)

@view_complaint_bp.route("/complaint/<int:id>")
def view_complaint(id):
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaint = complaint_for_student(conn, id)

    if not complaint:
        conn.close()
        flash("Complaint Not Found.", "danger")
        return redirect(url_for("complaints"))

    history_rows = conn.execute(
        "SELECT * FROM complaint_history WHERE complaint_id=? ORDER BY date ASC",
        (id,)
    ).fetchall()
    history = [dict(h) for h in history_rows]

    duplicate = None
    if complaint["ai_duplicate_id"]:
        duplicate = conn.execute(
            "SELECT id, title, status FROM complaints WHERE id=?",
            (complaint["ai_duplicate_id"],)
        ).fetchone()

    common_issue = None
    cid = complaint["common_issue_id"] if "common_issue_id" in complaint.keys() else None
    if cid:
        common_issue = get_common_issue_with_stats(cid, conn)
        # Merge master common issue history entries into the timeline
        common_history_rows = conn.execute(
            "SELECT status, remarks, updated_by, date FROM common_issue_history WHERE common_issue_id=? ORDER BY date ASC",
            (cid,)
        ).fetchall()
        for ch in common_history_rows:
            history.append({
                "status": ch["status"],
                "remarks": ch["remarks"],
                "updated_by": ch["updated_by"],
                "date": ch["date"],
                "is_common": True
            })
        history.sort(key=lambda x: str(x.get("date", "")))

    conn.close()

    return render_template(
        "jagan/view_complaint.html",
        complaint=complaint,
        history=history,
        duplicate=duplicate,
        common_issue=common_issue
    )
