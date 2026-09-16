from flask import Blueprint, render_template, redirect, url_for, session, request
from database.db import get_db_connection
from services.auth_service import student_required
from services.notification_service import (
    auto_archive_notifications,
    archive_single_notification,
    unarchive_single_notification,
    archive_all_read_notifications,
    get_student_notifications
)

notifications_bp = Blueprint("notifications", __name__)

@notifications_bp.route("/notifications")
def notifications():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    
    # 1. Automated Lifecycle Auto-Archiving (Aged read notifications & capacity bounds)
    auto_archive_notifications(student_id=sid)

    # 2. View segmenting: 'active' (default) vs 'archived' (history)
    current_view = request.args.get("view", "active").strip().lower()
    if current_view not in ("active", "archived"):
        current_view = "active"

    page = max(1, request.args.get("page", 1, type=int) or 1)
    data = get_student_notifications(student_id=sid, view=current_view, page=page, per_page=20)

    return render_template(
        "deepthi/notifications.html",
        notifications=data["items"],
        view=data["view"],
        active_total=data["active_total"],
        unread_total=data["unread_total"],
        active_read_total=data["active_read_total"],
        archived_total=data["archived_total"],
        page=data["page"],
        total_pages=data["total_pages"]
    )

@notifications_bp.route("/notification/read/<int:id>", methods=["POST"])
def notification_read(id):
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    notif_type = request.form.get("notif_type", "").strip().lower()
    target_view = request.form.get("view", "active")
    conn = get_db_connection()

    if notif_type == "common":
        cin = conn.execute(
            """
            SELECT cin.id
            FROM common_issue_notifications cin
            JOIN complaints c ON c.common_issue_id = cin.common_issue_id
            WHERE cin.id = ? AND c.student_id = ?
            """,
            (id, sid)
        ).fetchone()
        if cin:
            conn.execute(
                """
                INSERT INTO notification_reads (common_issue_notification_id, student_id)
                VALUES (?, ?)
                ON CONFLICT (common_issue_notification_id, student_id) DO NOTHING
                """,
                (id, sid)
            )
    elif notif_type == "individual":
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND student_id=?", (id, sid))
    else:
        notif = conn.execute("SELECT id FROM notifications WHERE id=? AND student_id=?", (id, sid)).fetchone()
        if notif:
            conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND student_id=?", (id, sid))
        else:
            cin = conn.execute(
                """
                SELECT cin.id
                FROM common_issue_notifications cin
                JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                WHERE cin.id = ? AND c.student_id = ?
                """,
                (id, sid)
            ).fetchone()
            if cin:
                conn.execute(
                    """
                    INSERT INTO notification_reads (common_issue_notification_id, student_id)
                    VALUES (?, ?)
                    ON CONFLICT (common_issue_notification_id, student_id) DO NOTHING
                    """,
                    (id, sid)
                )

    conn.commit()
    conn.close()

    return redirect(url_for("notifications", view=target_view))

@notifications_bp.route("/notifications/read-all", methods=["POST"])
@notifications_bp.route("/notifications/read_all", methods=["POST"])
def notifications_read_all():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    target_view = request.form.get("view", "active")
    conn = get_db_connection()

    # 1. Atomically mark all unread active individual notifications as read
    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE student_id=? AND is_read=0 AND (is_archived=0 OR is_archived IS NULL)",
        (sid,)
    )

    # 2. Atomically insert all unread common issue notifications as read
    conn.execute(
        """
        INSERT INTO notification_reads (common_issue_notification_id, student_id)
        SELECT DISTINCT cin.id, ?
        FROM common_issue_notifications cin
        JOIN complaints c ON c.common_issue_id = cin.common_issue_id
        LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
        WHERE c.student_id = ? AND nr.id IS NULL
        ON CONFLICT (common_issue_notification_id, student_id) DO NOTHING
        """,
        (sid, sid, sid)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("notifications", view=target_view))

@notifications_bp.route("/notification/archive/<int:id>", methods=["POST"])
def notification_archive(id):
    """Transitions a notification to ARCHIVED state."""
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    notif_type = request.form.get("notif_type", "individual")
    target_view = request.form.get("view", "active")

    archive_single_notification(student_id=sid, notif_id=id, notif_type=notif_type)
    return redirect(url_for("notifications", view=target_view))

@notifications_bp.route("/notification/unarchive/<int:id>", methods=["POST"])
def notification_unarchive(id):
    """Restores an archived notification back to the ACTIVE inbox."""
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    notif_type = request.form.get("notif_type", "individual")

    unarchive_single_notification(student_id=sid, notif_id=id, notif_type=notif_type)
    return redirect(url_for("notifications", view="archived"))

@notifications_bp.route("/notifications/archive-all", methods=["POST"])
@notifications_bp.route("/notifications/archive_all", methods=["POST"])
def notifications_archive_all():
    """Bulk archives all active READ notifications for this student."""
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    archive_all_read_notifications(student_id=sid)
    return redirect(url_for("notifications", view="active"))

