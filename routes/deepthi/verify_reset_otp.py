from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

import config
from database.db import get_db_connection
from services.auth_service import hash_reset_token

verify_reset_otp_bp = Blueprint("verify_reset_otp", __name__)

@verify_reset_otp_bp.route("/verify-reset-otp", methods=["GET", "POST"])
@verify_reset_otp_bp.route("/verify_reset_otp", methods=["GET", "POST"])
def verify_reset_otp():
    if "reset_student_id" not in session:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        if not otp.isdigit() or len(otp) != 6:
            flash("Enter a valid 6-digit OTP.", "danger")
            return redirect(url_for("verify_reset_otp"))

        conn = get_db_connection()
        row = conn.execute(
            """
            SELECT *
            FROM password_reset_otps
            WHERE student_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session["reset_student_id"],)
        ).fetchone()

        if not row:
            conn.close()
            flash("OTP not found. Request a new OTP.", "danger")
            return redirect(url_for("forgot_password"))

        if row["attempts"] >= config.OTP_MAX_ATTEMPTS:
            conn.close()
            flash("Too many incorrect attempts. Request a new OTP.", "danger")
            return redirect(url_for("forgot_password"))

        try:
            valid_time = (
                datetime.fromisoformat(str(row["expires_at"])) > datetime.utcnow()
            )
        except ValueError:
            valid_time = False

        if not valid_time:
            conn.close()
            flash("OTP has expired. Request a new OTP.", "danger")
            return redirect(url_for("forgot_password"))

        if hash_reset_token(otp) != row["otp_hash"]:
            conn.execute(
                """
                UPDATE password_reset_otps
                SET attempts=attempts+1
                WHERE id=?
                """,
                (row["id"],)
            )
            conn.commit()
            conn.close()
            flash("Incorrect OTP. Please try again.", "danger")
            return redirect(url_for("verify_reset_otp"))

        conn.execute(
            "UPDATE password_reset_otps SET verified=1 WHERE id=?",
            (row["id"],)
        )
        conn.commit()
        conn.close()

        session["reset_verified"] = True
        return redirect(url_for("reset_password"))

    return render_template(
        "deepthi/verify_reset_otp.html",
        email=session.get("reset_email")
    )
