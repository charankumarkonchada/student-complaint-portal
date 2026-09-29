from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.database.db import get_db_connection
from backend.services.auth_service import student_required, is_college_email
from backend.services.student_id_correction_service import (
    get_student_requests,
    submit_correction_request
)

profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        hostel = request.form.get("hostel", "").strip()
        room = request.form.get("room_no", "").strip()

        expected_local = None
        current_student = conn.execute("SELECT id_no FROM students WHERE id=?", (session["student_id"],)).fetchone()
        if current_student:
            expected_local = str(current_student["id_no"]).strip().lower()
        email_local = email.split("@", 1)[0] if "@" in email else ""
        if not is_college_email(email) or (expected_local and email_local != expected_local):
            flash("Use the college email address registered for your student ID.", "danger")
        else:
            try:
                conn.execute(
                    """
                    UPDATE students
                    SET name=?, email=?, phone=?, hostel=?, room_no=?
                    WHERE id=?
                    """,
                    (name, email, phone, hostel, room, session["student_id"])
                )
                conn.commit()
                session["student_name"] = name
                session["email"] = email
                session["hostel"] = hostel
                session["room_no"] = room
                flash("Profile Updated Successfully.", "success")
            except Exception:
                conn.rollback()
                flash("Unable to update profile. Email may already be in use.", "danger")

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (session["student_id"],)
    ).fetchone()
    conn.close()

    if student:
        session["id_no"] = student["id_no"]
        session["email"] = student["email"]

    correction_requests = get_student_requests(session["student_id"])

    return render_template(
        "student/profile.html",
        student=student,
        correction_requests=correction_requests
    )


@profile_bp.route("/profile/request_id_correction", methods=["POST"])
@profile_bp.route("/request_id_correction", methods=["POST"])
def request_id_correction():
    if not student_required():
        return redirect(url_for("login"))

    requested_id = request.form.get("requested_id", "").strip()
    reason = request.form.get("reason", "").strip()

    success, message, _ = submit_correction_request(session["student_id"], requested_id, reason)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("profile.profile"))
