from flask import Blueprint, render_template, request, redirect, url_for
from database.db import get_db_connection
from services.auth_service import admin_required

manage_complaints_bp = Blueprint("manage_complaints", __name__)

@manage_complaints_bp.route("/manage_complaints")
def manage_complaints():
    if not admin_required():
        return redirect(url_for("admin_login"))

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 10
    offset = (page - 1) * per_page

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    date = request.args.get("date", "").strip()

    conn = get_db_connection()
    where = ["1=1"]
    params = []

    if search:
        where.append(
            """
            (
                students.name LIKE ?
                OR students.id_no LIKE ?
                OR complaints.title LIKE ?
                OR complaints.description LIKE ?
            )
            """
        )
        q = f"%{search}%"
        params.extend([q, q, q, q])

    if status:
        where.append("complaints.status=?")
        params.append(status)

    if priority:
        where.append("complaints.priority=?")
        params.append(priority)

    if date:
        where.append("DATE(complaints.created_at)=?")
        params.append(date)

    where_sql = " AND ".join(where)

    total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM complaints
        JOIN students ON students.id=complaints.student_id
        WHERE {where_sql}
        """,
        params
    ).fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT complaints.*, students.name, students.id_no, students.hostel
        FROM complaints
        JOIN students ON students.id=complaints.student_id
        WHERE {where_sql}
        ORDER BY complaints.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset]
    ).fetchall()

    conn.close()

    pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "charan/manage_complaints.html",
        complaints=rows,
        page=page,
        pages=pages,
        total=total
    )
