from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database.db import get_db_connection

login_bp = Blueprint("login", __name__)

@login_bp.route("/login", methods=["GET", "POST"])
def login():
    if "admin" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        id_no = request.form.get("id_no", "").strip().upper()
        password = request.form.get("password", "")

        conn = get_db_connection()
        student = conn.execute(
            "SELECT * FROM students WHERE id_no=?",
            (id_no,)
        ).fetchone()
        conn.close()

        if student and check_password_hash(student["password"], password):
            session.clear()
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]
            session["id_no"] = student["id_no"]
            session["email"] = student["email"]
            session["hostel"] = student["hostel"]
            session["room_no"] = student["room_no"]
            flash("Login Successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid ID Number or Password.", "danger")

    return render_template("deepthi/login.html")

@login_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged Out Successfully.", "success")
    return redirect(url_for("login"))
