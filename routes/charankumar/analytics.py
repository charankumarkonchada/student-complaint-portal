from flask import Blueprint, render_template, redirect, url_for
import config
from database.db import get_db_connection
from services.auth_service import admin_required

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/analytics")
def analytics():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    if config.DATABASE_URL:
        month_expr = "TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM')"
    else:
        month_expr = "strftime('%Y-%m', created_at)"

    monthly = conn.execute(
        f"""
        SELECT {month_expr} AS month, COUNT(*) AS total
        FROM complaints
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()

    category_data = conn.execute(
        "SELECT category, COUNT(*) AS total FROM complaints GROUP BY category ORDER BY total DESC"
    ).fetchall()

    status_rows = conn.execute(
        "SELECT status, COUNT(*) AS total FROM complaints GROUP BY status"
    ).fetchall()

    priority_rows = conn.execute(
        "SELECT priority, COUNT(*) AS total FROM complaints GROUP BY priority"
    ).fetchall()

    ai_rows = conn.execute(
        "SELECT ai_category, COUNT(*) AS total FROM complaints GROUP BY ai_category ORDER BY total DESC"
    ).fetchall()

    avg_resolution = conn.execute(
        "SELECT AVG(ai_resolution_days) FROM complaints WHERE ai_resolution_days IS NOT NULL"
    ).fetchone()[0] or 0

    duplicate_count = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE ai_duplicate_id IS NOT NULL"
    ).fetchone()[0]

    conn.close()

    status_map = {r["status"]: r["total"] for r in status_rows}
    priority_map = {r["priority"]: r["total"] for r in priority_rows}

    return render_template(
        "charankumar/analytics.html",
        months=[r["month"] for r in monthly],
        totals=[r["total"] for r in monthly],
        categories=[r["category"] for r in category_data],
        category_count=[r["total"] for r in category_data],
        pending=status_map.get("Pending", 0),
        progress=status_map.get("In Progress", 0),
        resolved=status_map.get("Resolved", 0),
        low=priority_map.get("Low", 0),
        medium=priority_map.get("Medium", 0),
        high=priority_map.get("High", 0),
        ai_categories=[r["ai_category"] for r in ai_rows],
        ai_category_count=[r["total"] for r in ai_rows],
        avg_resolution=round(avg_resolution, 1),
        duplicate_count=duplicate_count
    )
