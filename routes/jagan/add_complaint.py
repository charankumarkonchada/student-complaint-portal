from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename

import config
from database.db import get_db_connection
from services.auth_service import student_required
from services.storage_service import allowed_file, upload_to_cloud_storage
from services.common_issue_service import (
    find_matching_common_issue,
    process_complaint_common_issue,
    get_common_issue_with_stats
)
from ml_engine import predict_complaint, find_duplicate

add_complaint_bp = Blueprint("add_complaint", __name__)

@add_complaint_bp.route("/add_complaint", methods=["GET", "POST"])
def add_complaint():
    if not student_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not all([category, priority, title, description]):
            flash("Category, priority, title and description are required.", "danger")
            return redirect(url_for("add_complaint"))

        filename = ""
        image = request.files.get("image")

        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Only PNG, JPG and JPEG images are allowed.", "danger")
                return redirect(url_for("add_complaint"))

            try:
                filename = upload_to_cloud_storage(
                    image,
                    secure_filename(image.filename),
                    session["student_id"]
                )
            except Exception:
                current_app.logger.exception("Complaint attachment upload failed")
                flash("Complaint image upload failed. Please check Supabase Storage settings and try again.", "danger")
                return redirect(url_for("add_complaint"))

        conn = get_db_connection()
        existing = conn.execute("SELECT id, title, description, status FROM complaints").fetchall()

        # Fetch student's details for location-based grouping and notification delivery
        student = conn.execute("SELECT name, email, hostel FROM students WHERE id = ?", (session["student_id"],)).fetchone()
        student_hostel = (student["hostel"] if student else session.get("hostel", "")).strip()

        ai = predict_complaint(title, description, category, priority)
        duplicate = find_duplicate(title, description, existing)

        duplicate_id = duplicate["id"] if duplicate else None
        duplicate_similarity = duplicate["similarity"] if duplicate else None

        insert_sql = """
            INSERT INTO complaints(
                student_id, category, title, description, image, priority, status,
                assigned_to, remarks, common_issue_id,
                ai_category, ai_category_confidence, ai_priority, ai_priority_confidence,
                ai_resolution_days, ai_duplicate_id, ai_duplicate_similarity
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        from database.db import ConnectionAdapter
        is_postgres = isinstance(conn, ConnectionAdapter)

        if is_postgres:
            insert_sql += " RETURNING id"

        cur = conn.execute(
            insert_sql,
            (
                session["student_id"],
                category,
                title,
                description,
                filename,
                priority,
                "Pending",
                None,
                None,
                None,
                str(ai["predicted_category"]) if ai.get("predicted_category") is not None else None,
                float(ai["category_confidence"]) if ai.get("category_confidence") is not None else None,
                str(ai["predicted_priority"]) if ai.get("predicted_priority") is not None else None,
                float(ai["priority_confidence"]) if ai.get("priority_confidence") is not None else None,
                float(ai["resolution_days"]) if ai.get("resolution_days") is not None else None,
                duplicate_id,
                float(duplicate_similarity) if duplicate_similarity is not None else None
            )
        )

        if is_postgres:
            complaint_id = cur.fetchone()["id"]
        else:
            complaint_id = cur.lastrowid

        # AI Grouping Engine: Detect matching active Common Issue or similar complaint
        ci_id, auto_dup_id, auto_sim = process_complaint_common_issue(
            complaint_id=complaint_id,
            category=category,
            hostel=student_hostel,
            title=title,
            description=description,
            priority=priority,
            conn=conn
        )

        initial_status = "Pending"
        issue_stats = None
        if ci_id:
            issue_stats = get_common_issue_with_stats(ci_id, conn)
            if issue_stats and issue_stats.get("status"):
                initial_status = issue_stats["status"]

        conn.execute(
            "INSERT INTO complaint_history(complaint_id, status) VALUES(?,?)",
            (complaint_id, initial_status)
        )

        # In-App Notification: Record submission confirmation
        conn.execute(
            "INSERT INTO notifications(student_id, message) VALUES(?, ?)",
            (session["student_id"], f"Your complaint #{complaint_id} has been submitted successfully.")
        )

        conn.commit()
        conn.close()

        # Resilient Email Notification: Send submission confirmation
        # Failure to send email must NEVER fail or block complaint submission
        if student and student["email"]:
            try:
                from services.email_service import send_complaint_submitted_email
                student_name = student["name"] if student["name"] else session.get("name", "Student")
                send_complaint_submitted_email(
                    student_name=student_name,
                    student_email=student["email"],
                    complaint_id=complaint_id,
                    title=title,
                    category=category,
                    priority=priority,
                    estimated_days=ai.get("resolution_days")
                )
            except Exception:
                current_app.logger.exception("Failed to dispatch complaint submission confirmation email")

        if ci_id and issue_stats:
            code = issue_stats.get("issue_code") or f"CI-{ci_id:03d}"
            aff = issue_stats.get("affected_count") or 1
            iss_title = issue_stats.get("title") or "Hostel Issue"
            flash(
                f"Complaint submitted and linked to Common Issue '{iss_title}' ({code}) affecting {aff} student(s) in {student_hostel}. Administration updates will automatically update your ticket.",
                "info"
            )
        elif duplicate:
            flash(
                f"Complaint submitted. Possible duplicate #{duplicate_id} detected ({duplicate_similarity}% similarity).",
                "warning"
            )
        else:
            flash(
                f"Complaint submitted. AI estimated resolution time: {ai['resolution_days']} days.",
                "success"
            )

        return redirect(url_for("view_complaint", id=complaint_id))

    return render_template("jagan/add_complaint.html")

@add_complaint_bp.route("/api/ai/analyze", methods=["POST"])
@add_complaint_bp.route("/api/ai_analyze", methods=["POST"])
def ai_analyze():
    if not student_required():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "")
    description = payload.get("description", "")
    category = payload.get("category", "")
    priority = payload.get("priority", "")

    if not title or not description:
        return jsonify({"error": "Title and description are required"}), 400

    return jsonify(predict_complaint(title, description, category, priority))
