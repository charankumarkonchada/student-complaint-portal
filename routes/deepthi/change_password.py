from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db_connection
from services.auth_service import student_required

change_password_bp = Blueprint("change_password", __name__)

@change_password_bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if not student_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if new != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("change_password"))

        if len(new) < 6:
            flash("New password must contain at least 6 characters.", "danger")
            return redirect(url_for("change_password"))

        conn = get_db_connection()
        student = conn.execute(
            "SELECT password FROM students WHERE id=?",
            (session["student_id"],)
        ).fetchone()

        if not student or not check_password_hash(student["password"], old):
            conn.close()
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("change_password"))

        conn.execute(
            "UPDATE students SET password=? WHERE id=?",
            (generate_password_hash(new), session["student_id"])
        )
        conn.commit()
        conn.close()

        flash("Password Updated Successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("deepthi/change_password.html")
