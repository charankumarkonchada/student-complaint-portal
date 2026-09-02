import io
from flask import Blueprint, redirect, url_for, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from openpyxl import Workbook

import config
from database.db import get_db_connection
from services.auth_service import admin_required

export_reports_bp = Blueprint("export_reports", __name__)

@export_reports_bp.route("/export_pdf")
def export_pdf():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT complaints.*, students.name, students.id_no
        FROM complaints
        JOIN students ON complaints.student_id=students.id
        ORDER BY complaints.created_at DESC
        """
    ).fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"{config.COLLEGE_NAME} Complaint Report")

    width, height = A4
    margin = 40
    printable_width = width - (2 * margin)

    title_style = ParagraphStyle(
        name="ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a")
    )

    title_text = f"<b>{config.COLLEGE_NAME}</b><br/><font size='11' color='#475569'>Hostel Complaint Report</font>"
    title_p = Paragraph(title_text, title_style)
    _, title_h = title_p.wrap(printable_width, height)

    y = height - margin - title_h
    title_p.drawOn(pdf, margin, y)

    y -= 10
    pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
    pdf.setLineWidth(1)
    pdf.line(margin, y, width - margin, y)
    y -= 20

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#1e293b"))

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
        pdf.drawString(margin, y, line[:115])
        y -= 16
        if y < 45:
            pdf.showPage()
            y = height - margin
            pdf.setFont("Helvetica", 9)
            pdf.setFillColor(colors.HexColor("#1e293b"))

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="RGUKT_Ongole_Complaint_Report.pdf",
        mimetype="application/pdf"
    )

@export_reports_bp.route("/export_excel")
def export_excel():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT complaints.*, students.name, students.id_no, students.hostel
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
