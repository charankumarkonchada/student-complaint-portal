from flask import Blueprint, render_template, redirect, url_for, session
from database.db import get_db_connection
from services.auth_service import student_required

notifications_bp = Blueprint("notifications", __name__)

@notifications_bp.route("/notifications")
def notifications():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()

    # Individual notifications
    ind_rows = conn.execute(
        "SELECT id, student_id, message, is_read, created_at, 'individual' AS notif_type FROM notifications WHERE student_id=? ORDER BY created_at DESC",
        (sid,)
    ).fetchall()

    # Shared common issue notifications
    common_rows = conn.execute(
        """
        SELECT DISTINCT cin.id, ? AS student_id, cin.message,
               CASE WHEN nr.id IS NOT NULL THEN 1 ELSE 0 END AS is_read,
               cin.created_at, 'common' AS notif_type
        FROM common_issue_notifications cin
        JOIN complaints c ON c.common_issue_id = cin.common_issue_id
        LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
        WHERE c.student_id = ?
        ORDER BY cin.created_at DESC
        """,
        (sid, sid, sid)
    ).fetchall()

    combined = [dict(r) for r in ind_rows] + [dict(r) for r in common_rows]
    combined.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)

    conn.close()

    return render_template("deepthi/notifications.html", notifications=combined)

@notifications_bp.route("/notification/read/<int:id>", methods=["POST"])
def notification_read(id):
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()

    # Check if this ID is an individual notification for this student
    notif = conn.execute("SELECT id FROM notifications WHERE id=? AND student_id=?", (id, sid)).fetchone()
    if notif:
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (id,))
    else:
        # Check if it's a common issue notification
        cin = conn.execute("SELECT id FROM common_issue_notifications WHERE id=?", (id,)).fetchone()
        if cin:
            try:
                conn.execute(
                    "INSERT INTO notification_reads (common_issue_notification_id, student_id) VALUES (?, ?)",
                    (id, sid)
                )
            except Exception:
                pass

    conn.commit()
    conn.close()

    return redirect(url_for("notifications"))

@notifications_bp.route("/notifications/read-all", methods=["POST"])
@notifications_bp.route("/notifications/read_all", methods=["POST"])
def notifications_read_all():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET is_read=1 WHERE student_id=?", (sid,))

    # Also mark all current common issue notifications as read for this student
    cins = conn.execute(
        """
        SELECT DISTINCT cin.id
        FROM common_issue_notifications cin
        JOIN complaints c ON c.common_issue_id = cin.common_issue_id
        WHERE c.student_id = ?
        """,
        (sid,)
    ).fetchall()

    for cin in cins:
        try:
            conn.execute(
                "INSERT INTO notification_reads (common_issue_notification_id, student_id) VALUES (?, ?)",
                (cin["id"], sid)
            )
        except Exception:
            pass

    conn.commit()
    conn.close()

    return redirect(url_for("notifications"))
