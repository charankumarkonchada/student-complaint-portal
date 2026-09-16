from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database.db import get_db_connection
import config
import os
import time

_failed_attempts = {}

admin_login_bp = Blueprint("admin_login", __name__)

@admin_login_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if "student_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        key = request.remote_addr or "unknown"
        now = time.time()
        recent = [t for t in _failed_attempts.get(key, []) if now - t < 900]
        if len(recent) >= 10:
            flash("Too many login attempts. Please try again later.", "danger")
            return render_template("charan/admin_login.html"), 429

        conn = get_db_connection()
        admin = conn.execute("SELECT id, username, password FROM admin WHERE username=?", (username,)).fetchone()
        conn.close()
        valid = bool(admin and check_password_hash(admin["password"], password))

        # Optional bootstrap compatibility in development/testing or when explicitly enabled in production.
        if not valid and (not config.IS_PRODUCTION or os.environ.get("ALLOW_LEGACY_ADMIN_ENV_AUTH", "0").lower() in {"1","true","yes"}):
            valid = username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD

        if valid:
            _failed_attempts.pop(key, None)
            session.clear()
            session["admin"] = admin["username"] if admin else username
            flash("Admin Login Successful.", "success")
            return redirect(url_for("admin_dashboard"))

        recent.append(now)
        _failed_attempts[key] = recent
        flash("Invalid Username or Password.", "danger")

    return render_template("charan/admin_login.html")

@admin_login_bp.route("/admin_logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("Admin Logged Out Successfully.", "success")
    return redirect(url_for("admin_login"))
