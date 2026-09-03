from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename

import config
from database.db import get_db_connection
from services.auth_service import student_required
from services.storage_service import allowed_file, upload_to_cloud_storage
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

        ai = predict_complaint(title, description, category, priority)
        duplicate = find_duplicate(title, description, existing)

        duplicate_id = duplicate["id"] if duplicate else None
        duplicate_similarity = duplicate["similarity"] if duplicate else None

        insert_sql = """
            INSERT INTO complaints(
                student_id, category, title, description, image, priority, status,
                ai_category, ai_category_confidence, ai_priority, ai_priority_confidence,
                ai_resolution_days, ai_duplicate_id, ai_duplicate_similarity
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        if config.DATABASE_URL:
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
                str(ai["predicted_category"]) if ai.get("predicted_category") is not None else None,
                float(ai["category_confidence"]) if ai.get("category_confidence") is not None else None,
                str(ai["predicted_priority"]) if ai.get("predicted_priority") is not None else None,
                float(ai["priority_confidence"]) if ai.get("priority_confidence") is not None else None,
                float(ai["resolution_days"]) if ai.get("resolution_days") is not None else None,
                duplicate_id,
                float(duplicate_similarity) if duplicate_similarity is not None else None
            )
        )

        if config.DATABASE_URL:
            complaint_id = cur.fetchone()["id"]
        else:
            complaint_id = cur.lastrowid

        conn.execute(
            "INSERT INTO complaint_history(complaint_id, status) VALUES(?,?)",
            (complaint_id, "Pending")
        )
        conn.commit()
        conn.close()

        if duplicate:
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
