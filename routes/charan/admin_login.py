from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import config

admin_login_bp = Blueprint("admin_login", __name__)

@admin_login_bp.route("/admin_login", methods=["GET", "POST"])
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

    return render_template("charan/admin_login.html")

@admin_login_bp.route("/admin_logout")
def admin_logout():
    session.clear()
    flash("Admin Logged Out Successfully.", "success")
    return redirect(url_for("admin_login"))
