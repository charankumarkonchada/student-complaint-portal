from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import get_db_connection
from services.auth_service import admin_required

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
        "charan/update_status.html",
        complaint=complaint,
        history=history
    )
