from flask import Blueprint, render_template, redirect, url_for, session
from database.db import get_db_connection
from services.auth_service import student_required

student_dashboard_bp = Blueprint("student_dashboard", __name__)

@student_dashboard_bp.route("/dashboard")
def dashboard():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()

    if not session.get("id_no") or not session.get("student_name"):
        student = conn.execute(
            "SELECT name, id_no, email, hostel, room_no FROM students WHERE id=?",
            (sid,)
        ).fetchone()
        if student:
            session["student_name"] = student["name"]
            session["id_no"] = student["id_no"]
            session["email"] = student["email"]
            session["hostel"] = student["hostel"]
            session["room_no"] = student["room_no"]

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=?",
        (sid,)
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='Pending'",
        (sid,)
    ).fetchone()[0]

    progress = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='In Progress'",
        (sid,)
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='Resolved'",
        (sid,)
    ).fetchone()[0]

    recent = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC LIMIT 5",
        (sid,)
    ).fetchall()

    conn.close()

    return render_template(
        "vennela/dashboard.html",
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved,
        recent=recent
    )
