from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash

import config
from database.db import get_db_connection
from services.auth_service import is_college_email, is_valid_id

register_bp = Blueprint("register", __name__)

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

        if not all([name, id_no, email, password]):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        if not is_valid_id(id_no):
            flash("Invalid ID Number. Must start with O, N, R, or S followed by 6 digits (e.g., O210894, N210894, R210894, S210894).", "danger")
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

    return render_template("raghunitha/register.html")
