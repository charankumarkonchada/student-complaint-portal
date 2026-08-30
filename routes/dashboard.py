from flask import render_template, request, redirect, url_for, session, flash

from database.db import get_db_connection
from services.auth_service import student_required, is_college_email
from routes import dashboard_bp

@dashboard_bp.route("/dashboard")
def dashboard():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=?",
        (sid,)
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='Pending'",
        (sid,)
    ).fetchone()[0]

    progress = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='In Progress'",
        (sid,)
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE student_id=? AND status='Resolved'",
        (sid,)
    ).fetchone()[0]

    recent = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC LIMIT 5",
        (sid,)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved,
        recent=recent
    )

@dashboard_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        hostel = request.form.get("hostel", "").strip()
        room = request.form.get("room_no", "").strip()

        if not is_college_email(email):
            flash("Only RGUKT Ongole college email addresses are allowed.", "danger")
        else:
            try:
                conn.execute(
                    """
                    UPDATE students
                    SET name=?, email=?, phone=?, hostel=?, room_no=?
                    WHERE id=?
                    """,
                    (name, email, phone, hostel, room, session["student_id"])
                )
                conn.commit()
                session["student_name"] = name
                session["email"] = email
                session["hostel"] = hostel
                session["room_no"] = room
                flash("Profile Updated Successfully.", "success")
            except Exception:
                conn.rollback()
                flash("Unable to update profile. Email may already be in use.", "danger")

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (session["student_id"],)
    ).fetchone()
    conn.close()

    return render_template("profile.html", student=student)

@dashboard_bp.route("/notifications")
def notifications():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    data = conn.execute(
        "SELECT * FROM notifications WHERE student_id=? ORDER BY created_at DESC",
        (session["student_id"],)
    ).fetchall()
    conn.close()

    return render_template("notifications.html", notifications=data)

@dashboard_bp.route("/notification/read/<int:id>", methods=["POST"])
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

@dashboard_bp.route("/notifications/read-all", methods=["POST"])
@dashboard_bp.route("/notifications/read_all", methods=["POST"])
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

@dashboard_bp.route("/activity")
def activity():
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaints_rows = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC LIMIT 10",
        (session["student_id"],)
    ).fetchall()

    history = conn.execute(
        """
        SELECT h.*, c.title
        FROM complaint_history h
        JOIN complaints c ON c.id=h.complaint_id
        WHERE c.student_id=?
        ORDER BY h.date DESC
        LIMIT 30
        """,
        (session["student_id"],)
    ).fetchall()
    conn.close()

    return render_template(
        "activity.html",
        complaints=complaints_rows,
        history=history
    )
