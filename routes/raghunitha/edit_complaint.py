from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename

from database.db import get_db_connection
from database.queries import complaint_for_student
from services.auth_service import student_required
from services.storage_service import allowed_file, upload_to_cloud_storage
from ml_engine import predict_complaint, find_duplicate

edit_complaint_bp = Blueprint("edit_complaint", __name__)

@edit_complaint_bp.route("/complaint/<int:id>/edit", methods=["GET", "POST"])
@edit_complaint_bp.route("/edit_complaint/<int:id>", methods=["GET", "POST"])
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
                str(ai["predicted_category"]) if ai.get("predicted_category") is not None else None,
                float(ai["category_confidence"]) if ai.get("category_confidence") is not None else None,
                str(ai["predicted_priority"]) if ai.get("predicted_priority") is not None else None,
                float(ai["priority_confidence"]) if ai.get("priority_confidence") is not None else None,
                float(ai["resolution_days"]) if ai.get("resolution_days") is not None else None,
                duplicate["id"] if duplicate else None,
                float(duplicate["similarity"]) if duplicate and duplicate.get("similarity") is not None else None,
                id
            )
        )
        conn.commit()
        conn.close()

        flash("Complaint Updated Successfully with fresh AI analysis.", "success")
        return redirect(url_for("complaints"))

    conn.close()
    return render_template("raghunitha/edit_complaint.html", complaint=complaint)

@edit_complaint_bp.route("/complaint/<int:id>/delete", methods=["POST"])
@edit_complaint_bp.route("/delete_complaint/<int:id>", methods=["POST"])
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
