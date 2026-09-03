from flask import Blueprint, render_template, redirect, url_for, flash
from database.db import get_db_connection
from database.queries import complaint_for_student
from services.auth_service import student_required

view_complaint_bp = Blueprint("view_complaint", __name__)

@view_complaint_bp.route("/complaint/<int:id>")
def view_complaint(id):
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaint = complaint_for_student(conn, id)

    history = (
        conn.execute(
            "SELECT * FROM complaint_history WHERE complaint_id=? ORDER BY date ASC",
            (id,)
        ).fetchall()
        if complaint
        else []
    )

    duplicate = None
    if complaint and complaint["ai_duplicate_id"]:
        duplicate = conn.execute(
            "SELECT id, title, status FROM complaints WHERE id=?",
            (complaint["ai_duplicate_id"],)
        ).fetchone()

    conn.close()

    if not complaint:
        flash("Complaint Not Found.", "danger")
        return redirect(url_for("complaints"))

    return render_template(
        "jagan/view_complaint.html",
        complaint=complaint,
        history=history,
        duplicate=duplicate
    )
