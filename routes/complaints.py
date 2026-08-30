from flask import render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename

import config
from database.db import get_db_connection
from database.queries import complaint_for_student
from services.auth_service import student_required
from services.storage_service import allowed_file, upload_to_cloud_storage
from ml_engine import predict_complaint, find_duplicate
from routes import complaints_bp

@complaints_bp.route("/add_complaint", methods=["GET", "POST"])
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
                ai["predicted_category"],
                ai["category_confidence"],
                ai["predicted_priority"],
                ai["priority_confidence"],
                ai["resolution_days"],
                duplicate_id,
                duplicate_similarity
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

    return render_template("add_complaint.html")

@complaints_bp.route("/complaints")
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

    return render_template("complaint_history.html", complaints=data)

@complaints_bp.route("/complaint/<int:id>")
def view_complaint(id):
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaint = complaint_for_student(conn, id)

    history = (
        conn.execute(
            "SELECT * FROM complaint_history WHERE complaint_id=? ORDER BY date ASC",
            (id,)
        ).fetchall()
        if complaint
        else []
    )

    duplicate = None
    if complaint and complaint["ai_duplicate_id"]:
        duplicate = conn.execute(
            "SELECT id, title, status FROM complaints WHERE id=?",
            (complaint["ai_duplicate_id"],)
        ).fetchone()

    conn.close()

    if not complaint:
        flash("Complaint Not Found.", "danger")
        return redirect(url_for("complaints"))

    return render_template(
        "view_complaint.html",
        complaint=complaint,
        history=history,
        duplicate=duplicate
    )

@complaints_bp.route("/complaint/<int:id>/edit", methods=["GET", "POST"])
@complaints_bp.route("/edit_complaint/<int:id>", methods=["GET", "POST"])
def edit_complaint(id):
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaint = complaint_for_student(conn, id)

    if not complaint:
        conn.close()
        flash("Complaint Not Found.", "danger")
        return redirect(url_for("complaints"))

    if complaint["status"] == "Resolved":
        conn.close()
        flash("Resolved complaints cannot be edited.", "warning")
        return redirect(url_for("complaints"))

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        image_name = complaint["image"]

        image = request.files.get("image")
        if image and image.filename:
            if not allowed_file(image.filename):
                conn.close()
                flash("Only PNG, JPG and JPEG images are allowed.", "danger")
                return redirect(url_for("edit_complaint", id=id))

            try:
                image_name = upload_to_cloud_storage(
                    image,
                    secure_filename(image.filename),
                    session["student_id"]
                )
            except Exception:
                conn.close()
                current_app.logger.exception("Complaint attachment upload failed during edit")
                flash("Complaint image upload failed. Please check Supabase Storage settings and try again.", "danger")
                return redirect(url_for("edit_complaint", id=id))

        existing = conn.execute(
            "SELECT id, title, description, status FROM complaints WHERE id!=?",
            (id,)
        ).fetchall()

        ai = predict_complaint(title, description, category, priority)
        duplicate = find_duplicate(title, description, existing)

        conn.execute(
            """
            UPDATE complaints
            SET category=?, priority=?, title=?, description=?, image=?,
                ai_category=?, ai_category_confidence=?, ai_priority=?, ai_priority_confidence=?,
                ai_resolution_days=?, ai_duplicate_id=?, ai_duplicate_similarity=?
            WHERE id=?
            """,
            (
                category,
                priority,
                title,
                description,
                image_name,
                ai["predicted_category"],
                ai["category_confidence"],
                ai["predicted_priority"],
                ai["priority_confidence"],
                ai["resolution_days"],
                duplicate["id"] if duplicate else None,
                duplicate["similarity"] if duplicate else None,
                id
            )
        )
        conn.commit()
        conn.close()

        flash("Complaint Updated Successfully with fresh AI analysis.", "success")
        return redirect(url_for("view_complaint", id=id))

    conn.close()
    return render_template("edit_complaint.html", complaint=complaint)

@complaints_bp.route("/complaint/<int:id>/delete", methods=["POST"])
@complaints_bp.route("/delete_complaint/<int:id>", methods=["POST"])
def delete_complaint(id):
    if not student_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    complaint = complaint_for_student(conn, id)

    if not complaint:
        conn.close()
        flash("Complaint Not Found.", "danger")
        return redirect(url_for("complaints"))

    if complaint["status"] == "Resolved":
        conn.close()
        flash("Resolved complaints cannot be deleted.", "warning")
        return redirect(url_for("complaints"))

    conn.execute("DELETE FROM complaints WHERE id=? AND student_id=?", (id, session["student_id"]))
    conn.commit()
    conn.close()

    flash("Complaint Deleted Successfully.", "success")
    return redirect(url_for("complaints"))

@complaints_bp.route("/api/ai/analyze", methods=["POST"])
@complaints_bp.route("/api/ai_analyze", methods=["POST"])
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
