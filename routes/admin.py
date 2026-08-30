import io
from flask import render_template, request, redirect, url_for, session, flash, send_file
from reportlab.pdfgen import canvas
from openpyxl import Workbook

import config
from database.db import get_db_connection
from services.auth_service import admin_required
from routes import admin_bp

@admin_bp.route("/admin_dashboard")
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

    try:
        recent = conn.execute(
            """
            SELECT complaints.*, students.name, students.id_no
            FROM complaints
            JOIN students ON students.id=complaints.student_id
            ORDER BY complaints.created_at DESC
            LIMIT 8
            """
        ).fetchall()
    except Exception:
        # SQLite schema fallback where column might be roll_no
        recent = conn.execute(
            """
            SELECT complaints.*, students.name, students.roll_no AS id_no
            FROM complaints
            JOIN students ON students.id=complaints.student_id
            ORDER BY complaints.created_at DESC
            LIMIT 8
            """
        ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        **stats,
        recent=recent
    )

@admin_bp.route("/manage_complaints")
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

    try:
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
    except Exception:
        # Fallback for SQLite schemas using roll_no
        where_alt = [w.replace("students.id_no", "students.roll_no") for w in where]
        where_alt_sql = " AND ".join(where_alt)
        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM complaints
            JOIN students ON students.id=complaints.student_id
            WHERE {where_alt_sql}
            """,
            params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT complaints.*, students.name, students.roll_no AS id_no, students.hostel
            FROM complaints
            JOIN students ON students.id=complaints.student_id
            WHERE {where_alt_sql}
            ORDER BY complaints.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset]
        ).fetchall()

    conn.close()

    pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "manage_complaints.html",
        complaints=rows,
        page=page,
        pages=pages,
        total=total
    )

@admin_bp.route("/update_status/<int:id>", methods=["GET", "POST"])
def update_status(id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    complaint = conn.execute("SELECT * FROM complaints WHERE id=?", (id,)).fetchone()

    if not complaint:
        conn.close()
        flash("Complaint Not Found.", "danger")
        return redirect(url_for("manage_complaints"))

    if request.method == "POST":
        status = request.form.get("status", "Pending")
        assigned = request.form.get("assigned_to", "").strip()
        remarks = request.form.get("remarks", "").strip()
        old_status = complaint["status"]

        conn.execute(
            """
            UPDATE complaints
            SET status=?, assigned_to=?, remarks=?
            WHERE id=?
            """,
            (status, assigned, remarks, id)
        )

        if old_status != status:
            conn.execute(
                "INSERT INTO complaint_history(complaint_id, status) VALUES(?,?)",
                (id, status)
            )
            conn.execute(
                "INSERT INTO notifications(student_id, message) VALUES(?,?)",
                (complaint["student_id"], f"Your complaint #{id} status changed to {status}.")
            )

        conn.commit()
        conn.close()

        flash("Complaint Updated Successfully.", "success")
        return redirect(url_for("manage_complaints"))

    history = conn.execute(
        "SELECT * FROM complaint_history WHERE complaint_id=? ORDER BY date DESC",
        (id,)
    ).fetchall()
    conn.close()

    return render_template(
        "update_status.html",
        complaint=complaint,
        history=history
    )

@admin_bp.route("/analytics")
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
        "analytics.html",
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

@admin_bp.route("/export_pdf")
def export_pdf():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT complaints.*, students.name, students.id_no
            FROM complaints
            JOIN students ON complaints.student_id=students.id
            ORDER BY complaints.created_at DESC
            """
        ).fetchall()
    except Exception:
        rows = conn.execute(
            """
            SELECT complaints.*, students.name, students.roll_no AS id_no
            FROM complaints
            JOIN students ON complaints.student_id=students.id
            ORDER BY complaints.created_at DESC
            """
        ).fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(f"{config.COLLEGE_NAME} Complaint Report")

    y = 800
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, f"{config.COLLEGE_NAME} - Hostel Complaint Report")
    y -= 30

    pdf.setFont("Helvetica", 9)
    for c in rows:
        line = (
            f"#{c['id']} | "
            f"{c['name']} | "
            f"{dict(c).get('id_no', '')} | "
            f"{c['category']} | "
            f"{c['priority']} | "
            f"{c['status']} | "
            f"AI: {c['ai_resolution_days'] or '-'}d"
        )
        pdf.drawString(40, y, line[:115])
        y -= 16
        if y < 45:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 9)

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="RGUKT_Ongole_Complaint_Report.pdf",
        mimetype="application/pdf"
    )

@admin_bp.route("/export_excel")
def export_excel():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT complaints.*, students.name, students.id_no, students.hostel
            FROM complaints
            JOIN students ON complaints.student_id=students.id
            ORDER BY complaints.created_at DESC
            """
        ).fetchall()
    except Exception:
        rows = conn.execute(
            """
            SELECT complaints.*, students.name, students.roll_no AS id_no, students.hostel
            FROM complaints
            JOIN students ON complaints.student_id=students.id
            ORDER BY complaints.created_at DESC
            """
        ).fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Complaints"
    ws.append([
        "ID", "Student", "ID No", "Hostel", "Category", "Title", "Priority",
        "Status", "Assigned To", "AI Category", "AI Category Confidence",
        "AI Priority", "AI Priority Confidence", "AI Resolution Days",
        "Duplicate ID", "Similarity %", "Date"
    ])

    for c in rows:
        ws.append([
            c["id"],
            c["name"],
            dict(c).get("id_no", ""),
            dict(c).get("hostel", ""),
            c["category"],
            c["title"],
            c["priority"],
            c["status"],
            c["assigned_to"],
            c["ai_category"],
            c["ai_category_confidence"],
            c["ai_priority"],
            c["ai_priority_confidence"],
            c["ai_resolution_days"],
            c["ai_duplicate_id"],
            c["ai_duplicate_similarity"],
            c["created_at"]
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="RGUKT_Ongole_Complaint_Report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
