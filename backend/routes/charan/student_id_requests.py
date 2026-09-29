"""Admin Student ID Correction Requests Route Module.
Owned by Charan / Admin Operations.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from backend.services.auth_service import admin_required
from backend.services.student_id_correction_service import (
    get_all_requests,
    get_request_by_id,
    approve_correction_request,
    reject_correction_request
)

student_id_requests_bp = Blueprint("student_id_requests", __name__)


@student_id_requests_bp.route("/admin/id_correction_requests", methods=["GET"])
@student_id_requests_bp.route("/admin/student_id_requests", methods=["GET"])
def list_requests():
    if not admin_required():
        return redirect(url_for("admin_login"))

    status_filter = request.args.get("status", "all").strip().lower()
    all_reqs = get_all_requests()

    pending_count = sum(1 for r in all_reqs if r.get("status") == "Pending")
    approved_count = sum(1 for r in all_reqs if r.get("status") == "Approved")
    rejected_count = sum(1 for r in all_reqs if r.get("status") == "Rejected")
    total_count = len(all_reqs)

    if status_filter != "all":
        filtered_reqs = [r for r in all_reqs if r.get("status", "").lower() == status_filter]
    else:
        filtered_reqs = all_reqs

    return render_template(
        "admin/student_id_requests.html",
        requests=filtered_reqs,
        status_filter=status_filter,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        total_count=total_count
    )


@student_id_requests_bp.route("/admin/id_correction_requests/<int:request_id>/approve", methods=["POST"])
def approve_request(request_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    admin_user = session.get("admin", "Admin")
    admin_remarks = request.form.get("admin_remarks", "").strip()

    success, message = approve_correction_request(request_id, admin_user, admin_remarks)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("student_id_requests.list_requests"))


@student_id_requests_bp.route("/admin/id_correction_requests/<int:request_id>/reject", methods=["POST"])
def reject_request(request_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    admin_user = session.get("admin", "Admin")
    admin_remarks = request.form.get("admin_remarks", "").strip()

    success, message = reject_correction_request(request_id, admin_user, admin_remarks)
    if success:
        flash(message, "warning")
    else:
        flash(message, "danger")

    return redirect(url_for("student_id_requests.list_requests"))
