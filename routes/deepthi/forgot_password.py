import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app

import config
from database.db import get_db_connection
from services.auth_service import hash_reset_token
from services.email_service import send_otp_email

forgot_password_bp = Blueprint("forgot_password", __name__)

@forgot_password_bp.route("/forgot-password", methods=["GET", "POST"])
@forgot_password_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        conn = get_db_connection()
        student = conn.execute(
            "SELECT id, email FROM students WHERE lower(email)=?",
            (email,)
        ).fetchone()

        if student:
            otp = f"{secrets.randbelow(1000000):06d}"
            otp_hash = hash_reset_token(otp)
            expires_at = (
                datetime.utcnow() + timedelta(minutes=config.OTP_EXPIRY_MINUTES)
            ).isoformat()

            conn.execute(
                "DELETE FROM password_reset_otps WHERE student_id=?",
                (student["id"],)
            )
            conn.execute(
                """
                INSERT INTO password_reset_otps(
                    student_id, otp_hash, expires_at, attempts, verified
                )
                VALUES(?,?,?,0,0)
                """,
                (student["id"], otp_hash, expires_at)
            )
            conn.commit()

            try:
                send_otp_email(student["email"], otp)
            except Exception as exc:
                conn.execute(
                    "DELETE FROM password_reset_otps WHERE student_id=?",
                    (student["id"],)
                )
                conn.commit()
                conn.close()

                current_app.logger.exception("OTP email failed")
                if current_app.debug:
                    flash(f"Unable to send OTP: {exc}", "danger")
                else:
                    flash(
                        "Unable to send the reset OTP right now. Please check the SMTP settings and try again.",
                        "danger"
                    )
                return redirect(url_for("forgot_password"))

            conn.close()
            session["reset_student_id"] = student["id"]
            session["reset_email"] = student["email"]
            flash("A 6-digit OTP has been sent to your registered email.", "success")
            return redirect(url_for("verify_reset_otp"))

        conn.close()
        flash("If an account exists for that email, an OTP has been sent.", "success")

    return render_template("deepthi/forgot_password.html")
