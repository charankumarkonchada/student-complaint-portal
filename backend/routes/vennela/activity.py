from flask import Blueprint, render_template, redirect, url_for, session
from backend.database.db import get_db_connection
from backend.services.auth_service import student_required

activity_bp = Blueprint("activity", __name__)

@activity_bp.route("/activity")
def activity():
    if not student_required():
        return redirect(url_for("login"))

    sid = session["student_id"]
    conn = get_db_connection()

    # 1. Fetch recent complaints for sidebar snapshot
    complaints_rows = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC, id DESC LIMIT 10",
        (sid,)
    ).fetchall()

    # 2. Individual history from complaint_history
    ind_history = conn.execute(
        """
        SELECT h.id, h.complaint_id, h.status, h.date, c.title,
               COALESCE(c.remarks, '') AS remarks,
               COALESCE(c.assigned_to, '') AS assigned_to,
               c.created_at AS complaint_created_at
        FROM complaint_history h
        JOIN complaints c ON c.id=h.complaint_id
        WHERE c.student_id=?
        ORDER BY h.date DESC, h.id DESC
        LIMIT 30
        """,
        (sid,)
    ).fetchall()

    # 3. Common issue history for complaints linked to a common issue
    common_history = conn.execute(
        """
        SELECT DISTINCT cih.id, c.id AS complaint_id, cih.status, cih.date,
               ci.title, COALESCE(cih.remarks, '') AS remarks,
               COALESCE(cih.updated_by, 'Hostel Administration') AS updated_by,
               COALESCE(c.assigned_to, '') AS assigned_to,
               c.created_at AS complaint_created_at
        FROM common_issue_history cih
        JOIN common_issues ci ON ci.id=cih.common_issue_id
        JOIN complaints c ON c.common_issue_id=cih.common_issue_id
        WHERE c.student_id=?
        ORDER BY cih.date DESC, cih.id DESC
        LIMIT 30
        """,
        (sid,)
    ).fetchall()

    processed_events = []
    seen_event_keys = set()

    for h in ind_history:
        h_dict = dict(h)
        st = h_dict.get("status", "")
        assigned = h_dict.get("assigned_to", "")
        if st == "Pending":
            h_dict["event_type"] = "Complaint Raised"
            h_dict["updated_by"] = "Student (Self)"
            h_dict["action_text"] = "Complaint submitted and registered in hostel system."
        elif st == "Resolved":
            h_dict["event_type"] = "Complaint Resolved"
            h_dict["updated_by"] = assigned or "Hostel Administration"
            h_dict["action_text"] = "Complaint has been resolved and closed by maintenance team."
        elif st == "In Progress":
            h_dict["event_type"] = "Complaint In Progress"
            h_dict["updated_by"] = assigned or "Hostel Administration"
            h_dict["action_text"] = f"Assigned to {assigned} — work in progress." if assigned else "Ticket status moved to In Progress."
        else:
            h_dict["event_type"] = f"Complaint {st}"
            h_dict["updated_by"] = assigned or "Hostel Administration"
            h_dict["action_text"] = f"Ticket status updated to {st}."

        key = (h_dict.get("complaint_id"), st, str(h_dict.get("date", ""))[:16])
        seen_event_keys.add(key)
        processed_events.append(h_dict)

    for h in common_history:
        h_dict = dict(h)
        st = h_dict.get("status", "")
        key = (h_dict.get("complaint_id"), st, str(h_dict.get("date", ""))[:16])
        if key not in seen_event_keys:
            seen_event_keys.add(key)
            h_dict["event_type"] = f"Common Issue {st}"
            h_dict["action_text"] = f"Common hostel issue updated to {st}."
            processed_events.append(h_dict)

    # 4. Guarantee that every complaint raised has an activity event recorded
    recorded_complaint_ids = {h.get("complaint_id") for h in processed_events}
    for c in complaints_rows:
        if c["id"] not in recorded_complaint_ids:
            creation_event = {
                "id": f"c_{c['id']}",
                "complaint_id": c["id"],
                "status": c.get("status", "Pending") or "Pending",
                "date": c["created_at"],
                "title": c["title"],
                "remarks": c.get("remarks", "") or "",
                "assigned_to": c.get("assigned_to", "") or "",
                "updated_by": "Student (Self)",
                "event_type": "Complaint Raised",
                "action_text": "Complaint submitted and registered in hostel system."
            }
            processed_events.append(creation_event)
            try:
                conn.execute(
                    "INSERT INTO complaint_history(complaint_id, status, date) VALUES(?, ?, ?)",
                    (c["id"], c.get("status", "Pending") or "Pending", c["created_at"])
                )
                conn.commit()
            except Exception:
                pass

    conn.close()

    # 5. Sort chronologically newest first
    def get_sort_key(item):
        d = item.get("date")
        if hasattr(d, "isoformat"):
            d_str = d.isoformat()
        else:
            d_str = str(d or "")
        cid = item.get("complaint_id") or 0
        try:
            cid = int(cid)
        except Exception:
            cid = 0
        raw_id = item.get("id") or 0
        if isinstance(raw_id, str) and raw_id.startswith("c_"):
            try:
                item_id = int(raw_id[2:])
            except Exception:
                item_id = 0
        else:
            try:
                item_id = int(raw_id)
            except Exception:
                item_id = 0
        return (d_str, cid, item_id)

    processed_events.sort(key=get_sort_key, reverse=True)

    # 6. Format dates cleanly for template rendering
    for item in processed_events:
        d = item.get("date")
        if hasattr(d, "strftime"):
            item["formatted_date"] = d.strftime("%Y-%m-%d %H:%M")
        elif d:
            item["formatted_date"] = str(d)[:16]
        else:
            item["formatted_date"] = ""

    return render_template(
        "student/activity.html",
        complaints=complaints_rows,
        history=processed_events[:30]
    )
