from flask import Blueprint, render_template, redirect, url_for, session
from database.db import get_db_connection
from services.auth_service import student_required

notifications_bp = Blueprint("notifications", __name__)

@notifications_bp.route("/notifications")
def notifications():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    data = conn.execute(
        "SELECT * FROM notifications WHERE student_id=? ORDER BY created_at DESC",
        (session["student_id"],)
    ).fetchall()
    conn.close()

    return render_template("deepthi/notifications.html", notifications=data)

@notifications_bp.route("/notification/read/<int:id>", methods=["POST"])
def notification_read(id):
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE id=? AND student_id=?",
        (id, session["student_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("notifications"))

@notifications_bp.route("/notifications/read-all", methods=["POST"])
@notifications_bp.route("/notifications/read_all", methods=["POST"])
def notifications_read_all():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE student_id=?",
        (session["student_id"],)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("notifications"))
