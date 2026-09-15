import re
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app

import config
from database.db import get_db_connection
from services.auth_service import hash_reset_token
from services.email_service import send_otp_email

forgot_password_bp = Blueprint("forgot_password", __name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

@forgot_password_bp.route("/forgot-password", methods=["GET", "POST"])
@forgot_password_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email_raw = request.form.get("email", "")
        email = email_raw.strip()

        # 1. Empty field check
        if not email:
            flash("Email address is required.", "danger")
            return render_template("deepthi/forgot_password.html", email="")

        # 2. Syntax validation
        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("deepthi/forgot_password.html", email=email)

        # 3. Domain validation (must be @rguktong.ac.in, case-insensitive)
        email_lower = email.lower()
        college_domain = config.COLLEGE_DOMAIN.lower()
        if not college_domain.startswith("@"):
            college_domain = "@" + college_domain

        if (
            not email_lower.endswith(college_domain)
            or email_lower == college_domain
            or email_lower.count("@") != 1
            or email_lower.split("@")[0] == ""
        ):
            flash("Please enter your registered RGUKT college email address.", "danger")
            return render_template("deepthi/forgot_password.html", email=email)

        # 4. Check whether student account exists in the database
        conn = get_db_connection()
        student = conn.execute(
            "SELECT id, email FROM students WHERE lower(email)=?",
            (email_lower,)
        ).fetchone()

        if not student:
            conn.close()
            # CRITICAL: Do NOT generate OTP, do NOT send email, do NOT create session
            session.pop("reset_student_id", None)
            session.pop("reset_email", None)
            session.pop("reset_verified", None)
            flash("No account found with this college email address. Please check your email or create a student account.", "danger")
            return render_template("deepthi/forgot_password.html", email=email)

        # 5. Registered account exists -> Generate secure OTP
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
            if not current_app.config.get("TESTING"):
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
            return render_template("deepthi/forgot_password.html", email=email)

        conn.close()
        session["reset_student_id"] = student["id"]
        session["reset_email"] = student["email"]
        flash("OTP sent successfully to your registered college email.", "success")
        return redirect(url_for("verify_reset_otp"))

    return render_template("deepthi/forgot_password.html")

