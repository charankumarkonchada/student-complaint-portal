"""
Common Issues Route Module for IntelliHostel Admin.
Provides interface for master issue inspection, single-action propagation,
student association viewing, and group creation.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db_connection
from services.auth_service import admin_required
from services.common_issue_service import (
    get_all_common_issues,
    get_common_issue_with_stats,
    get_common_issue_complaints,
    update_common_issue_once,
    create_common_issue,
    associate_complaint_to_common_issue,
    unlink_complaint_from_common_issue,
    is_active_status
)

common_issues_bp = Blueprint("common_issues", __name__)


@common_issues_bp.route("/admin/common_issues")
def list_common_issues():
    """Administrative dashboard list of all common/shared campus issues."""
    if not admin_required():
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip() or None
    hostel_filter = request.args.get("hostel", "").strip() or None
    category_filter = request.args.get("category", "").strip() or None

    conn = get_db_connection()
    issues = get_all_common_issues(
        conn=conn,
        status_filter=status_filter,
        hostel_filter=hostel_filter,
        category_filter=category_filter,
        search=search if search else None
    )

    # Calculate overall stats
    total_issues = len(issues)
    active_issues = sum(1 for i in issues if is_active_status(i["status"]))
    resolved_issues = total_issues - active_issues
    total_affected = sum(i["affected_count"] for i in issues)

    # Fetch unique hostels and categories for filter dropdowns
    hostel_rows = conn.execute("SELECT DISTINCT hostel FROM common_issues WHERE hostel IS NOT NULL AND hostel != ''").fetchall()
    category_rows = conn.execute("SELECT DISTINCT category FROM common_issues WHERE category IS NOT NULL AND category != ''").fetchall()

    hostels = [r["hostel"] for r in hostel_rows]
    categories = [r["category"] for r in category_rows]

    conn.close()

    return render_template(
        "charan/common_issues.html",
        issues=issues,
        total_issues=total_issues,
        active_issues=active_issues,
        resolved_issues=resolved_issues,
        total_affected=total_affected,
        hostels=hostels,
        categories=categories
    )


@common_issues_bp.route("/admin/common_issue/<int:id>")
def view_common_issue(id):
    """Detailed view of a master common issue, affected student complaints, and audit log."""
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    issue = get_common_issue_with_stats(id, conn)

    if not issue:
        conn.close()
        flash("Common Issue Not Found.", "danger")
        return redirect(url_for("list_common_issues"))

    complaints = get_common_issue_complaints(id, conn)

    # Fetch available unlinked complaints in the same hostel and category that could be associated
    unlinked = conn.execute(
        """
        SELECT c.id, c.title, c.created_at, s.name, s.id_no, s.room_no
        FROM complaints c
        JOIN students s ON s.id = c.student_id
        WHERE c.common_issue_id IS NULL
          AND LOWER(TRIM(s.hostel)) = LOWER(TRIM(?))
          AND LOWER(TRIM(c.category)) = LOWER(TRIM(?))
        ORDER BY c.created_at DESC
        LIMIT 20
        """,
        (issue["hostel"], issue["category"])
    ).fetchall()

    conn.close()

    return render_template(
        "charan/view_common_issue.html",
        issue=issue,
        complaints=complaints,
        unlinked_candidates=unlinked
    )


@common_issues_bp.route("/admin/common_issue/<int:id>/update", methods=["POST"])
def update_common_issue(id):
    """
    SINGLE-ACTION UPDATE:
    Admin updates master status and remarks ONCE.
    Propagates to all associated student complaints in one SQL query.
    """
    if not admin_required():
        return redirect(url_for("admin_login"))

    status = request.form.get("status", "In Progress").strip()
    remarks = request.form.get("remarks", "").strip()
    assigned_to = request.form.get("assigned_to", "").strip()

    conn = get_db_connection()
    affected = update_common_issue_once(
        common_issue_id=id,
        status=status,
        remarks=remarks,
        assigned_to=assigned_to,
        updated_by="Hostel Administration",
        conn=conn
    )
    conn.close()

    flash(
        f"Master Issue #{id} updated to '{status}'. Successfully synchronized {affected} associated student complaint(s).",
        "success"
    )
    return redirect(url_for("common_issues.view_common_issue", id=id))


@common_issues_bp.route("/admin/common_issue/create", methods=["GET", "POST"])
def create_new_common_issue():
    """Creates a new master common issue and optionally associates selected complaints."""
    if not admin_required():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        hostel = request.form.get("hostel", "").strip()
        location_details = request.form.get("location_details", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "Medium").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        admin_remarks = request.form.get("admin_remarks", "").strip()
        selected_complaints = request.form.getlist("complaint_ids")

        if not all([title, category, hostel]):
            flash("Title, category, and hostel location are required to establish a Common Issue.", "danger")
            return redirect(url_for("common_issues.list_common_issues"))

        conn = get_db_connection()
        issue_id = create_common_issue(
            title=title,
            category=category,
            hostel=hostel,
            location_details=location_details,
            description=description,
            priority=priority,
            assigned_to=assigned_to,
            admin_remarks=admin_remarks,
            created_by="Hostel Administration",
            conn=conn
        )

        linked_count = 0
        for cid_str in selected_complaints:
            try:
                cid = int(cid_str)
                if associate_complaint_to_common_issue(cid, issue_id, conn):
                    linked_count += 1
            except ValueError:
                pass

        conn.close()

        msg = f"Common Issue #{issue_id} ('{title}') successfully created."
        if linked_count > 0:
            msg += f" Linked {linked_count} complaint(s)."
        flash(msg, "success")

        return redirect(url_for("common_issues.view_common_issue", id=issue_id))

    # GET request - show create form
    conn = get_db_connection()
    hostel_rows = conn.execute("SELECT DISTINCT hostel FROM students WHERE hostel IS NOT NULL AND hostel != ''").fetchall()
    conn.close()
    hostels = [r["hostel"] for r in hostel_rows]

    return render_template(
        "charan/create_common_issue.html",
        hostels=hostels
    )


@common_issues_bp.route("/admin/common_issue/<int:id>/unlink/<int:complaint_id>", methods=["POST"])
def unlink_complaint(id, complaint_id):
    """Unlinks a complaint from a common issue if it was misclassified."""
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    unlink_complaint_from_common_issue(complaint_id, conn)
    conn.close()

    flash(f"Complaint #{complaint_id} unlinked from Common Issue #{id}.", "info")
    return redirect(url_for("common_issues.view_common_issue", id=id))


@common_issues_bp.route("/admin/common_issue/<int:id>/link", methods=["POST"])
def link_complaint(id):
    """Manually links an unlinked complaint to this common issue."""
    if not admin_required():
        return redirect(url_for("admin_login"))

    complaint_id = request.form.get("complaint_id")
    if not complaint_id:
        flash("Please select a complaint to link.", "warning")
        return redirect(url_for("common_issues.view_common_issue", id=id))

    try:
        cid = int(complaint_id)
        conn = get_db_connection()
        success = associate_complaint_to_common_issue(cid, id, conn)
        conn.close()

        if success:
            flash(f"Complaint #{cid} successfully linked to Common Issue #{id}.", "success")
        else:
            flash("Unable to link complaint.", "danger")
    except ValueError:
        flash("Invalid complaint ID.", "danger")

    return redirect(url_for("common_issues.view_common_issue", id=id))
