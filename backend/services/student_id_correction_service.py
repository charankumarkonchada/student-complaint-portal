"""Student ID Correction Request Service for IntelliHostel.

Provides centralized business logic for student ID correction workflow:
- Request validation (format, prefix, length, identical ID prevention)
- Duplicate checking against existing student registry
- Safe submission and pending request deduplication
- Atomic admin approval with student ID & email sync
- Atomic admin rejection requiring remarks
- In-app and email notifications
"""
import logging
from typing import Optional, Tuple, List, Dict, Any

import backend.config as config
from backend.database.db import get_db_connection
from backend.services.auth_service import is_valid_id
from backend.services.email_service import send_email

logger = logging.getLogger(__name__)


def validate_correction_request(current_id: str, requested_id: str, reason: str) -> Tuple[bool, str, str]:
    """Validates correction request parameters.
    
    Returns:
        (is_valid, error_message, clean_requested_id)
    """
    clean_req_id = (requested_id or "").strip().upper()
    clean_cur_id = (current_id or "").strip().upper()
    clean_reason = (reason or "").strip()

    if not clean_req_id:
        return False, "Requested Student ID is required.", ""

    if not is_valid_id(clean_req_id):
        return False, "Invalid ID Number. Must start with O, N, R, or S followed by 6 digits (e.g., OXXXXXX, NXXXXXX, RXXXXXX, SXXXXXX).", ""

    if clean_req_id == clean_cur_id:
        return False, "Your requested Student ID is the same as your current Student ID.", ""

    if not clean_reason or len(clean_reason) < 5:
        return False, "Please provide a valid reason for the correction request (at least 5 characters).", ""

    return True, "", clean_req_id


def check_duplicate_student_id(conn, requested_id: str, exclude_student_id: Optional[int] = None) -> bool:
    """Checks whether the given student ID is already associated with an existing student."""
    clean_id = (requested_id or "").strip().upper()
    if exclude_student_id is not None:
        row = conn.execute(
            "SELECT 1 FROM students WHERE UPPER(id_no) = ? AND id != ?",
            (clean_id, exclude_student_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM students WHERE UPPER(id_no) = ?",
            (clean_id,)
        ).fetchone()
    return bool(row)


def submit_correction_request(student_id: int, requested_id: str, reason: str) -> Tuple[bool, str, Optional[int]]:
    """Validates and persists a new student ID correction request.
    
    Returns:
        (success, message, request_id)
    """
    conn = get_db_connection()
    try:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            return False, "Student account not found.", None

        # Check for existing pending request
        pending = conn.execute(
            "SELECT id FROM student_id_correction_requests WHERE student_id = ? AND status = 'Pending'",
            (student_id,)
        ).fetchone()
        if pending:
            return False, "You already have a pending Student ID correction request. Please wait for administrator review.", None

        is_valid, err_msg, clean_req_id = validate_correction_request(student["id_no"], requested_id, reason)
        if not is_valid:
            return False, err_msg, None

        if check_duplicate_student_id(conn, clean_req_id, exclude_student_id=student_id):
            return False, "This Student ID is already associated with another student account.", None

        conn.execute(
            """
            INSERT INTO student_id_correction_requests(
                student_id, current_student_id, requested_student_id, reason, status
            )
            VALUES(?, ?, ?, ?, 'Pending')
            """,
            (student_id, student["id_no"], clean_req_id, reason.strip())
        )

        req_row = conn.execute(
            "SELECT id FROM student_id_correction_requests WHERE student_id = ? AND status = 'Pending' ORDER BY id DESC LIMIT 1",
            (student_id,)
        ).fetchone()
        req_id = req_row["id"] if req_row else None

        # Create in-app notification
        conn.execute(
            "INSERT INTO notifications(student_id, message) VALUES(?, ?)",
            (student_id, "Your Student ID correction request has been submitted.")
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.exception("Failed to submit ID correction request for student %s: %s", student_id, e)
        return False, "Failed to submit request due to a database error. Please try again.", None
    finally:
        conn.close()

    # Dispatch confirmation email if enabled
    try:
        send_email(
            recipient=student["email"],
            subject=f"{config.COLLEGE_NAME} - Student ID Correction Request Submitted",
            text_body=(
                f"Hello {student['name']},\n\n"
                f"Your request to correct your Student ID from {student['id_no']} to {clean_req_id} has been submitted.\n"
                f"Reason: {reason.strip()}\n\n"
                f"You will receive an update once an administrator reviews your request.\n\n"
                f"Best regards,\nHostel Administration"
            )
        )
    except Exception:
        pass

    return True, "Your Student ID correction request has been submitted.", req_id


def get_student_requests(student_id: int) -> List[Dict[str, Any]]:
    """Retrieves all correction requests for the specified student ordered by creation date descending."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM student_id_correction_requests
            WHERE student_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (student_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_requests(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves correction requests for administrative review."""
    conn = get_db_connection()
    try:
        query = """
            SELECT r.*, s.name AS student_name, s.email AS student_email, s.hostel AS student_hostel, s.room_no AS student_room_no
            FROM student_id_correction_requests r
            JOIN students s ON r.student_id = s.id
        """
        params = []
        if status_filter and status_filter.lower() != "all":
            query += " WHERE LOWER(r.status) = LOWER(?)"
            params.append(status_filter)

        query += " ORDER BY CASE WHEN r.status = 'Pending' THEN 0 ELSE 1 END, r.created_at DESC, r.id DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_request_by_id(request_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single request by its ID joined with student details."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT r.*, s.name AS student_name, s.email AS student_email, s.hostel AS student_hostel, s.room_no AS student_room_no
            FROM student_id_correction_requests r
            JOIN students s ON r.student_id = s.id
            WHERE r.id = ?
            """,
            (request_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def approve_correction_request(request_id: int, admin_username: str, admin_remarks: str = "") -> Tuple[bool, str]:
    """Approves a pending student ID correction request inside an atomic database transaction.
    
    Updates:
    1. Student's id_no in students table.
    2. Student's college email if it was previously matching the old id_no.
    3. Request status to 'Approved' with reviewer info and timestamp.
    4. In-app and email notifications.
    """
    conn = get_db_connection()
    should_sync_email = False
    new_email = None
    student_record = None
    req_record = None

    try:
        req = conn.execute("SELECT * FROM student_id_correction_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return False, "Correction request not found."

        if req["status"] != "Pending":
            return False, f"Request has already been processed (Current status: {req['status']})."

        student = conn.execute("SELECT * FROM students WHERE id = ?", (req["student_id"],)).fetchone()
        if not student:
            return False, "Associated student account no longer exists."

        req_record = dict(req)
        student_record = dict(student)

        # Re-check that requested ID is not taken by another student
        if check_duplicate_student_id(conn, req["requested_student_id"], exclude_student_id=req["student_id"]):
            return False, "The requested Student ID is already associated with another student account."

        # Email synchronization: if existing email matched the old ID, update it to match new ID
        old_expected_email = str(req["current_student_id"]).strip().lower() + config.COLLEGE_DOMAIN.lower()
        new_email = str(req["requested_student_id"]).strip().lower() + config.COLLEGE_DOMAIN.lower()
        should_sync_email = (str(student["email"]).strip().lower() == old_expected_email)

        if should_sync_email:
            # Verify new email is not taken by another student
            email_dup = conn.execute(
                "SELECT 1 FROM students WHERE LOWER(email) = LOWER(?) AND id != ?",
                (new_email, req["student_id"])
            ).fetchone()
            if email_dup:
                return False, f"The college email corresponding to the new ID ({new_email}) is already associated with another account."
            conn.execute(
                "UPDATE students SET id_no = ?, email = ? WHERE id = ?",
                (req["requested_student_id"], new_email, req["student_id"])
            )
        else:
            conn.execute(
                "UPDATE students SET id_no = ? WHERE id = ?",
                (req["requested_student_id"], req["student_id"])
            )

        remarks = (admin_remarks or "").strip()
        conn.execute(
            """
            UPDATE student_id_correction_requests
            SET status = 'Approved', admin_remarks = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
            WHERE id = ?
            """,
            (remarks, admin_username, request_id)
        )

        notif_msg = f"Your Student ID correction request has been approved. Your Student ID is now {req['requested_student_id']}."
        conn.execute(
            "INSERT INTO notifications(student_id, message) VALUES(?, ?)",
            (req["student_id"], notif_msg)
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.exception("Failed to approve ID correction request %s: %s", request_id, e)
        return False, f"An error occurred while approving the request: {e}"
    finally:
        conn.close()

    # Dispatch email outside transaction
    try:
        recipient_email = new_email if should_sync_email else student_record["email"]
        send_email(
            recipient=recipient_email,
            subject=f"{config.COLLEGE_NAME} - Student ID Correction Approved",
            text_body=(
                f"Hello {student_record['name']},\n\n"
                f"Your Student ID correction request has been approved by {admin_username}.\n\n"
                f"Updated Student ID: {req_record['requested_student_id']}\n"
                + (f"Updated College Email: {new_email}\n" if should_sync_email else "")
                + (f"Admin Remarks: {admin_remarks}\n" if admin_remarks else "")
                + f"\nYou can now log in using your updated Student ID and existing password.\n\n"
                f"Best regards,\nHostel Administration"
            )
        )
    except Exception:
        pass

    return True, f"Request approved. Student ID successfully updated to {req_record['requested_student_id']}."


def reject_correction_request(request_id: int, admin_username: str, admin_remarks: str) -> Tuple[bool, str]:
    """Rejects a pending student ID correction request requiring admin remarks.
    
    Leaves student's current ID and records intact.
    """
    remarks = (admin_remarks or "").strip()
    if not remarks:
        return False, "Rejection remarks are required to explain the reason to the student."

    conn = get_db_connection()
    student_record = None
    req_record = None

    try:
        req = conn.execute("SELECT * FROM student_id_correction_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return False, "Correction request not found."

        if req["status"] != "Pending":
            return False, f"Request has already been processed (Current status: {req['status']})."

        student = conn.execute("SELECT * FROM students WHERE id = ?", (req["student_id"],)).fetchone()
        req_record = dict(req)
        if student:
            student_record = dict(student)

        conn.execute(
            """
            UPDATE student_id_correction_requests
            SET status = 'Rejected', admin_remarks = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
            WHERE id = ?
            """,
            (remarks, admin_username, request_id)
        )

        notif_msg = "Your Student ID correction request has been rejected. Please review the administrator's remarks."
        if student:
            conn.execute(
                "INSERT INTO notifications(student_id, message) VALUES(?, ?)",
                (req["student_id"], notif_msg)
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.exception("Failed to reject ID correction request %s: %s", request_id, e)
        return False, f"An error occurred while rejecting the request: {e}"
    finally:
        conn.close()

    # Dispatch email outside transaction
    if student_record:
        try:
            send_email(
                recipient=student_record["email"],
                subject=f"{config.COLLEGE_NAME} - Student ID Correction Request Update",
                text_body=(
                    f"Hello {student_record['name']},\n\n"
                    f"Your Student ID correction request for ID {req_record['requested_student_id']} has been rejected by {admin_username}.\n\n"
                    f"Admin Remarks:\n{remarks}\n\n"
                    f"Your current Student ID remains {req_record['current_student_id']}.\n\n"
                    f"Best regards,\nHostel Administration"
                )
            )
        except Exception:
            pass

    return True, "Request has been rejected."
