from flask import Blueprint, render_template, request, redirect, url_for, session
from database.db import get_db_connection
from services.auth_service import student_required

complaint_history_bp = Blueprint("complaint_history", __name__)

@complaint_history_bp.route("/complaints")
def complaints():
    if not student_required():
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db_connection()
    query = "SELECT * FROM complaints WHERE student_id=?"
    params = [session["student_id"]]

    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR category LIKE ?)"
        q = f"%{search}%"
        params.extend([q, q, q])

    if status:
        query += " AND status=?"
        params.append(status)

    query += " ORDER BY created_at DESC"
    data = conn.execute(query, params).fetchall()
    conn.close()

    return render_template("jagan/complaint_history.html", complaints=data)
