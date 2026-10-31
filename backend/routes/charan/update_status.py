from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from backend.database.db import get_db_connection
from backend.services.auth_service import admin_required

update_status_bp = Blueprint("update_status", __name__)

@update_status_bp.route("/update_status/<int:id>", methods=["GET", "POST"])
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
        status = request.form.get("status", "Pending").strip()
        if status not in {"Pending", "In Progress", "Resolved", "Closed", "Rejected"}:
            conn.close()
            flash("Invalid complaint status.", "danger")
            return redirect(url_for("update_status", id=id))
        assigned = request.form.get("assigned_to", "").strip()
        remarks = request.form.get("remarks", "").strip()
        resolution_remarks = request.form.get("resolution_remarks", "").strip()
        remove_resolution_image = request.form.get("remove_resolution_image", "0") == "1"
        old_status = complaint["status"]

        resolution_image = None if remove_resolution_image else (complaint["resolution_image"] if "resolution_image" in complaint.keys() else None)
        resolved_at = complaint["resolved_at"] if "resolved_at" in complaint.keys() else None
        existing_res_remarks = complaint["resolution_remarks"] if "resolution_remarks" in complaint.keys() else None
        res_remarks_to_save = resolution_remarks or existing_res_remarks

        new_image_ref = None

        if status == "Resolved":
            file = request.files.get("resolution_image")
            has_file = file is not None and getattr(file, "filename", "") != ""

            if not has_file and not resolution_image:
                conn.close()
                flash("A resolution proof image is required when marking a complaint as Resolved.", "danger")
                return redirect(url_for("update_status", id=id))

            if has_file:
                try:
                    from backend.services.storage_service import upload_resolution_proof
                    new_image_ref = upload_resolution_proof(file, file.filename, id)
                    resolution_image = new_image_ref
                    from datetime import datetime
                    resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                except ValueError as ve:
                    conn.close()
                    flash(str(ve), "danger")
                    return redirect(url_for("update_status", id=id))
                except Exception as ex:
                    current_app.logger.exception("Failed to upload resolution proof for complaint %s", id)
                    conn.close()
                    flash("Failed to upload resolution proof image. Please try again.", "danger")
                    return redirect(url_for("update_status", id=id))
            elif not resolved_at:
                from datetime import datetime
                resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if resolution_remarks and not remarks:
                remarks = resolution_remarks
            elif remarks and not resolution_remarks:
                res_remarks_to_save = remarks

        try:
            conn.execute(
                """
                UPDATE complaints
                SET status=?, assigned_to=?, remarks=?, resolution_image=?, resolved_at=?, resolution_remarks=?
                WHERE id=?
                """,
                (status, assigned, remarks, resolution_image, resolved_at, res_remarks_to_save, id)
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
        except Exception:
            conn.rollback()
            conn.close()
            if new_image_ref:
                try:
                    from backend.services.storage_service import delete_from_cloud_storage
                    delete_from_cloud_storage(new_image_ref)
                except Exception:
                    pass
            current_app.logger.exception("Failed to update status in database for complaint %s", id)
            flash("Database error while updating complaint status.", "danger")
            return redirect(url_for("update_status", id=id))

        # Fetch student details for email dispatch
        student = conn.execute(
            "SELECT name, email FROM students WHERE id=?",
            (complaint["student_id"],)
        ).fetchone()
        conn.close()

        # Resilient Email Notification: failure never breaks application or transaction
        if student and student["email"]:
            try:
                from backend.services.email_service import send_complaint_status_email
                send_complaint_status_email(
                    student_name=student["name"],
                    student_email=student["email"],
                    complaint_id=id,
                    complaint_title=complaint["title"],
                    new_status=status,
                    remarks=remarks,
                    assigned_to=assigned
                )
            except Exception:
                current_app.logger.exception("Failed to send complaint status email for complaint %s", id)

        flash("Complaint Updated Successfully.", "success")
        return redirect(url_for("manage_complaints"))

    history = conn.execute(
        "SELECT * FROM complaint_history WHERE complaint_id=? ORDER BY date DESC",
        (id,)
    ).fetchall()
    conn.close()

    return render_template(
        "admin/update_status.html",
        complaint=complaint,
        history=history
    )
