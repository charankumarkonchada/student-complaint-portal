from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.db import get_db_connection
from services.auth_service import student_required, is_college_email

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

        if not is_college_email(email):
            flash("Only RGUKT Ongole college email addresses are allowed.", "danger")
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

    return render_template("raghunitha/profile.html", student=student)
