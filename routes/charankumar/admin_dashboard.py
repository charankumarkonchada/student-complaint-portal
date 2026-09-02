from flask import Blueprint, render_template, redirect, url_for
from database.db import get_db_connection
from services.auth_service import admin_required

admin_dashboard_bp = Blueprint("admin_dashboard", __name__)

@admin_dashboard_bp.route("/admin_dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0],
        "progress": conn.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0],
        "resolved": conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0],
        "high_ai": conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE ai_priority='High' AND status!='Resolved'"
        ).fetchone()[0],
        "duplicates": conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE ai_duplicate_id IS NOT NULL"
        ).fetchone()[0]
    }

    recent = conn.execute(
        """
        SELECT complaints.*, students.name, students.id_no
        FROM complaints
        JOIN students ON students.id=complaints.student_id
        ORDER BY complaints.created_at DESC
        LIMIT 8
        """
    ).fetchall()

    conn.close()

    return render_template(
        "charankumar/admin_dashboard.html",
        **stats,
        recent=recent
    )
