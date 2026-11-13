import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from werkzeug.security import generate_password_hash

import backend.config as config
from backend.database.db import get_db_connection
from backend.services.auth_service import is_college_email, is_valid_id, hash_reset_token, mask_email
from backend.services.email_service import send_registration_otp_email

register_bp = Blueprint("register", __name__)

_otp_reg_request_log = {}

REGISTRATION_OTP_EXPIRY_MINUTES = 5


def _check_rate_limit(ip_key: str) -> tuple[bool, str, int]:
    if current_app.config.get("TESTING"):
        return True, "", 0
    now = time.time()
    events = [t for t in _otp_reg_request_log.get(ip_key, []) if now - t < 3600]
    if events and now - events[-1] < config.OTP_REQUEST_COOLDOWN_SECONDS:
        rem = int(config.OTP_REQUEST_COOLDOWN_SECONDS - (now - events[-1]))
        return False, f"Please wait {rem} seconds before requesting another verification code.", rem
    if len(events) >= config.OTP_MAX_REQUESTS_PER_HOUR:
        return False, "Too many verification requests. Please try again later.", 3600
    return True, "", 0


def _record_rate_event(ip_key: str):
    now = time.time()
    events = [t for t in _otp_reg_request_log.get(ip_key, []) if now - t < 3600]
    events.append(now)
    _otp_reg_request_log[ip_key] = events


@register_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        id_no = request.form.get("id_no", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        hostel = request.form.get("hostel", "").strip()
        room = request.form.get("room", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # 1. Required fields validation
        if not all([name, id_no, email, password]):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        # 2. Student ID format validation
        if not is_valid_id(id_no):
            flash(
                "Invalid ID Number. Must start with O, N, R, or S followed by 6 digits (e.g., OXXXXXX, NXXXXXX, RXXXXXX, SXXXXXX).",
                "danger"
            )
            return redirect(url_for("register"))

        # 3. Domain validation - Strictly @rguktong.ac.in
        college_domain = config.COLLEGE_DOMAIN.lower()
        if not college_domain.startswith("@"):
            college_domain = "@" + college_domain

        if not is_college_email(email):
            flash("Only RGUKT Ongole college email addresses ending in @rguktong.ac.in are allowed.", "danger")
            return redirect(url_for("register"))

        # 4. ID Number and Email correspondence validation
        expected_email = id_no.lower() + college_domain
        if email != expected_email:
            flash("ID Number and college email do not match.", "danger")
            return redirect(url_for("register"))

        # 5. Password confirmation and length
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return redirect(url_for("register"))

        # 6. Check existing students for duplicates
        conn = get_db_connection()
        try:
            existing_id = conn.execute(
                "SELECT 1 FROM students WHERE id_no=?",
                (id_no,)
            ).fetchone()

            if existing_id:
                flash("ID Number Already Exists.", "warning")
                return redirect(url_for("register"))

            existing_email = conn.execute(
                "SELECT 1 FROM students WHERE lower(email)=?",
                (email,)
            ).fetchone()

            if existing_email:
                flash("Email Already Exists.", "warning")
                return redirect(url_for("register"))

            # 7. Rate limit check for OTP dispatch
            ip_key = request.remote_addr or "unknown"
            allowed, limit_msg, _ = _check_rate_limit(ip_key)
            if not allowed:
                flash(limit_msg, "warning")
                return redirect(url_for("register"))

            # 8. Cryptographically secure 6-digit OTP generation
            otp = f"{secrets.randbelow(1000000):06d}"
            otp_hash = hash_reset_token(otp)
            expires_at = (
                datetime.now(timezone.utc) + timedelta(minutes=REGISTRATION_OTP_EXPIRY_MINUTES)
            ).isoformat()

            # Store registration data with securely hashed password (NEVER plaintext)
            registration_payload = json.dumps({
                "name": name,
                "id_no": id_no,
                "email": email,
                "phone": phone,
                "hostel": hostel,
                "room_no": room,
                "password_hash": generate_password_hash(password)
            })

            # Invalidate any prior pending registration OTPs for this email or ID
            conn.execute(
                "DELETE FROM registration_otps WHERE lower(email)=? OR id_no=?",
                (email, id_no)
            )
            conn.execute(
                """
                INSERT INTO registration_otps(
                    email, id_no, otp_hash, registration_data, expires_at, attempts, verified
                )
                VALUES(?,?,?,?,?,0,0)
                """,
                (email, id_no, otp_hash, registration_payload, expires_at)
            )
            conn.commit()

            # 9. Send OTP to student's RGUKT email address
            try:
                send_registration_otp_email(email, otp, expiry_minutes=REGISTRATION_OTP_EXPIRY_MINUTES)
            except Exception as exc:
                conn.execute(
                    "DELETE FROM registration_otps WHERE lower(email)=? OR id_no=?",
                    (email, id_no)
                )
                conn.commit()
                current_app.logger.exception("Failed to dispatch registration OTP email")
                if current_app.debug:
                    flash(f"Unable to send verification OTP: {exc}", "danger")
                else:
                    flash(
                        "Unable to send verification OTP to your college email. Please verify SMTP settings and try again.",
                        "danger"
                    )
                return redirect(url_for("register"))

            _record_rate_event(ip_key)

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        # Set session indicators for verification step
        session["reg_email"] = email
        session["reg_id_no"] = id_no
        session["reg_otp_sent_at"] = time.time()

        flash(
            f"A 6-digit verification code has been sent to your college email ({mask_email(email)}).",
            "success"
        )
        return redirect(url_for("register.verify_registration_otp"))

    return render_template("student/register.html")


@register_bp.route("/verify-registration-otp", methods=["GET", "POST"])
@register_bp.route("/verify_registration_otp", methods=["GET", "POST"])
def verify_registration_otp():
    if "reg_email" not in session or "reg_id_no" not in session:
        flash("Please complete the registration form to receive a verification OTP.", "warning")
        return redirect(url_for("register.register"))

    reg_email = session["reg_email"].lower()
    reg_id_no = session["reg_id_no"]

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM registration_otps
            WHERE lower(email)=? AND id_no=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (reg_email, reg_id_no)
        ).fetchone()

        if not row:
            session.pop("reg_email", None)
            session.pop("reg_id_no", None)
            session.pop("reg_otp_sent_at", None)
            flash("No pending registration session found. Please fill out the registration form again.", "warning")
            return redirect(url_for("register.register"))

        if request.method == "POST":
            otp = request.form.get("otp", "").strip()

            if not otp.isdigit() or len(otp) != 6:
                flash("Please enter a valid 6-digit OTP code.", "danger")
                return redirect(url_for("register.verify_registration_otp"))

            # Check if OTP already verified
            if row["verified"] == 1:
                flash("This verification code has already been used. Please log in.", "info")
                return redirect(url_for("login.login"))

            # Check attempt limit (max 5 incorrect attempts)
            if row["attempts"] >= config.OTP_MAX_ATTEMPTS:
                conn.execute("DELETE FROM registration_otps WHERE id=?", (row["id"],))
                conn.commit()
                session.pop("reg_email", None)
                session.pop("reg_id_no", None)
                session.pop("reg_otp_sent_at", None)
                flash("Maximum verification attempts exceeded (5/5). Please register again.", "danger")
                return redirect(url_for("register.register"))

            # Check expiration (5 minutes)
            try:
                exp_dt = datetime.fromisoformat(str(row["expires_at"]))
                now_utc = datetime.now(timezone.utc)
                if exp_dt.tzinfo is None:
                    valid_time = exp_dt > now_utc.replace(tzinfo=None)
                else:
                    valid_time = exp_dt > now_utc
            except ValueError:
                valid_time = False

            if not valid_time:
                flash("Verification code has expired. Please request a new code.", "danger")
                return redirect(url_for("register.verify_registration_otp"))

            # Compare cryptographic hash
            if hash_reset_token(otp) != row["otp_hash"]:
                conn.execute(
                    "UPDATE registration_otps SET attempts = attempts + 1 WHERE id=?",
                    (row["id"],)
                )
                conn.commit()
                new_attempts = row["attempts"] + 1

                if new_attempts >= config.OTP_MAX_ATTEMPTS:
                    conn.execute("DELETE FROM registration_otps WHERE id=?", (row["id"],))
                    conn.commit()
                    session.pop("reg_email", None)
                    session.pop("reg_id_no", None)
                    session.pop("reg_otp_sent_at", None)
                    flash("Too many incorrect attempts (5/5). Verification failed. Please start registration again.", "danger")
                    return redirect(url_for("register.register"))

                remaining = config.OTP_MAX_ATTEMPTS - new_attempts
                flash(f"Incorrect verification code. {remaining} attempt(s) remaining.", "danger")
                return redirect(url_for("register.verify_registration_otp"))

            # OTP is correct -> Mark verified and create student account atomically
            data = json.loads(row["registration_data"])

            # Final race-condition check for duplicate account
            dup = conn.execute(
                "SELECT 1 FROM students WHERE id_no=? OR lower(email)=?",
                (data["id_no"], data["email"].lower())
            ).fetchone()

            if dup:
                conn.execute("DELETE FROM registration_otps WHERE id=?", (row["id"],))
                conn.commit()
                session.pop("reg_email", None)
                session.pop("reg_id_no", None)
                session.pop("reg_otp_sent_at", None)
                flash("An account with this ID or email has already been registered.", "warning")
                return redirect(url_for("login.login"))

            # Insert new verified student account
            conn.execute(
                """
                INSERT INTO students(
                    name, id_no, email, phone, hostel, room_no, password, is_verified
                )
                VALUES(?,?,?,?,?,?,?,1)
                """,
                (
                    data["name"],
                    data["id_no"],
                    data["email"],
                    data["phone"],
                    data["hostel"],
                    data["room_no"],
                    data["password_hash"]
                )
            )

            # Invalidate temporary OTP registration data
            conn.execute("DELETE FROM registration_otps WHERE lower(email)=? OR id_no=?", (reg_email, reg_id_no))
            conn.commit()

            # Clean session
            session.pop("reg_email", None)
            session.pop("reg_id_no", None)
            session.pop("reg_otp_sent_at", None)

            flash("Registration Successful and college email verified. Please sign in.", "success")
            return redirect(url_for("login.login"))

    finally:
        conn.close()

    sent_at = session.get("reg_otp_sent_at", 0)
    now = time.time()
    remaining_cooldown = max(0, int(config.OTP_REQUEST_COOLDOWN_SECONDS - (now - sent_at)))

    return render_template(
        "student/verify_registration_otp.html",
        email=reg_email,
        masked_email=mask_email(reg_email),
        cooldown=remaining_cooldown,
        expiry_minutes=REGISTRATION_OTP_EXPIRY_MINUTES
    )


@register_bp.route("/resend-registration-otp", methods=["POST"])
@register_bp.route("/resend_registration_otp", methods=["POST"])
def resend_registration_otp():
    if "reg_email" not in session or "reg_id_no" not in session:
        if request.is_json:
            return jsonify({"success": False, "error": "Registration session expired"}), 400
        flash("Registration session expired. Please register again.", "warning")
        return redirect(url_for("register.register"))

    reg_email = session["reg_email"].lower()
    reg_id_no = session["reg_id_no"]
    ip_key = request.remote_addr or "unknown"

    sent_at = session.get("reg_otp_sent_at", 0)
    now = time.time()
    time_since_last = now - sent_at

    if not current_app.config.get("TESTING") and time_since_last < config.OTP_REQUEST_COOLDOWN_SECONDS:
        rem = int(config.OTP_REQUEST_COOLDOWN_SECONDS - time_since_last)
        msg = f"Please wait {rem} seconds before requesting another code."
        if request.is_json:
            return jsonify({"success": False, "error": msg, "cooldown": rem}), 429
        flash(msg, "warning")
        return redirect(url_for("register.verify_registration_otp"))

    allowed, limit_msg, _ = _check_rate_limit(ip_key)
    if not allowed:
        if request.is_json:
            return jsonify({"success": False, "error": limit_msg}), 429
        flash(limit_msg, "danger")
        return redirect(url_for("register.verify_registration_otp"))

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM registration_otps
            WHERE lower(email)=? AND id_no=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (reg_email, reg_id_no)
        ).fetchone()

        if not row:
            if request.is_json:
                return jsonify({"success": False, "error": "No pending registration found"}), 400
            flash("No pending registration found. Please register again.", "danger")
            return redirect(url_for("register.register"))

        # Generate new 6-digit OTP
        new_otp = f"{secrets.randbelow(1000000):06d}"
        new_otp_hash = hash_reset_token(new_otp)
        new_expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=REGISTRATION_OTP_EXPIRY_MINUTES)
        ).isoformat()

        # Invalidate previous OTP and reinsert
        conn.execute("DELETE FROM registration_otps WHERE lower(email)=? OR id_no=?", (reg_email, reg_id_no))
        conn.execute(
            """
            INSERT INTO registration_otps(
                email, id_no, otp_hash, registration_data, expires_at, attempts, verified
            )
            VALUES(?,?,?,?,?,0,0)
            """,
            (reg_email, reg_id_no, new_otp_hash, row["registration_data"], new_expires_at)
        )
        conn.commit()

        try:
            send_registration_otp_email(reg_email, new_otp, expiry_minutes=REGISTRATION_OTP_EXPIRY_MINUTES)
        except Exception as exc:
            current_app.logger.exception("Failed to resend registration OTP email")
            err_msg = "Unable to dispatch verification email. Please check SMTP settings."
            if request.is_json:
                return jsonify({"success": False, "error": err_msg}), 500
            flash(err_msg, "danger")
            return redirect(url_for("register.verify_registration_otp"))

        session["reg_otp_sent_at"] = time.time()
        _record_rate_event(ip_key)

        success_msg = f"A new verification code has been dispatched to {mask_email(reg_email)}."
        if request.is_json:
            return jsonify({
                "success": True,
                "message": success_msg,
                "cooldown": config.OTP_REQUEST_COOLDOWN_SECONDS
            })

        flash(success_msg, "success")
        return redirect(url_for("register.verify_registration_otp"))

    finally:
        conn.close()
