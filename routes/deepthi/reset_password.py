from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from database.db import get_db_connection

reset_password_bp = Blueprint("reset_password", __name__)

@reset_password_bp.route("/reset-password", methods=["GET", "POST"])
@reset_password_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if not session.get("reset_verified") or not session.get("reset_student_id"):
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return redirect(url_for("reset_password"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("reset_password"))

        conn = get_db_connection()
        conn.execute(
            "UPDATE students SET password=? WHERE id=?",
            (generate_password_hash(password), session["reset_student_id"])
        )
        conn.execute(
            "DELETE FROM password_reset_otps WHERE student_id=?",
            (session["reset_student_id"],)
        )
        conn.commit()
        conn.close()

        session.pop("reset_student_id", None)
        session.pop("reset_email", None)
        session.pop("reset_verified", None)

        flash("Password reset successfully. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("deepthi/reset_password.html")
