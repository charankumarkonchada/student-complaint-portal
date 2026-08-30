import secrets
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash

import config
from database.db import get_db_connection
from services.auth_service import is_college_email, is_valid_id, hash_reset_token, student_required
from services.email_service import send_otp_email
from routes import auth_bp

@auth_bp.route("/register", methods=["GET", "POST"])
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

        if not all([name, id_no, email, password]):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        if not is_valid_id(id_no):
            flash("Invalid ID Number. Use format O221168.", "danger")
            return redirect(url_for("register"))

        if not is_college_email(email):
            flash("Only RGUKT Ongole college email addresses are allowed.", "danger")
            return redirect(url_for("register"))

        expected_email = id_no.lower() + config.COLLEGE_DOMAIN
        if email != expected_email:
            flash("ID Number and college email do not match.", "danger")
            return redirect(url_for("register"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return redirect(url_for("register"))

        conn = get_db_connection()
        try:
            try:
                existing_id = conn.execute(
                    "SELECT 1 FROM students WHERE roll_no=?",
                    (id_no,)
                ).fetchone()
            except Exception:
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

            try:
                conn.execute(
                    """
                    INSERT INTO students(
                        name, roll_no, email, phone, hostel, room_no, password
                    )
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        name,
                        id_no,
                        email,
                        phone,
                        hostel,
                        room,
                        generate_password_hash(password)
                    )
                )
            except Exception:
                conn.execute(
                    """
                    INSERT INTO students(
                        name, id_no, email, phone, hostel, room_no, password
                    )
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        name,
                        id_no,
                        email,
                        phone,
                        hostel,
                        room,
                        generate_password_hash(password)
                    )
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        flash("Registration Successful.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "admin" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        id_no = request.form.get("id_no", "").strip().upper()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            student = conn.execute(
                "SELECT * FROM students WHERE roll_no=?",
                (id_no,)
            ).fetchone()
        except Exception:
            student = conn.execute(
                "SELECT * FROM students WHERE id_no=?",
                (id_no,)
            ).fetchone()
        conn.close()

        if student and check_password_hash(student["password"], password):
            session.clear()
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]
            session["id_no"] = dict(student).get("roll_no") or dict(student).get("id_no") or id_no
            session["email"] = student["email"]
            session["hostel"] = student["hostel"]
            session["room_no"] = student["room_no"]
            flash("Login Successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid ID Number or Password.", "danger")

    return render_template("login.html")

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@auth_bp.route("/forgot_password", methods=["GET", "POST"])
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

    return render_template("forgot_password.html")

@auth_bp.route("/verify-reset-otp", methods=["GET", "POST"])
@auth_bp.route("/verify_reset_otp", methods=["GET", "POST"])
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
        "verify_reset_otp.html",
        email=session.get("reset_email")
    )

@auth_bp.route("/reset-password", methods=["GET", "POST"])
@auth_bp.route("/reset_password", methods=["GET", "POST"])
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

    return render_template("reset_password.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged Out Successfully.", "success")
    return redirect(url_for("login"))

@auth_bp.route("/change_password", methods=["GET", "POST"])
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

    return render_template("change_password.html")

@auth_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if "student_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            session.clear()
            session["admin"] = username
            flash("Admin Login Successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid Username or Password.", "danger")

    return render_template("admin_login.html")

@auth_bp.route("/admin_logout")
def admin_logout():
    session.clear()
    flash("Admin Logged Out Successfully.", "success")
    return redirect(url_for("admin_login"))
