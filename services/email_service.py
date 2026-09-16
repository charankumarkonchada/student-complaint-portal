import smtplib
import logging
from email.message import EmailMessage
from typing import Optional, Any
import config

logger = logging.getLogger(__name__)


def send_email(recipient: str, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
    """
    Sends an email to the specified recipient via SMTP.
    Non-blocking / resilient:
    - Returns False immediately if EMAIL_NOTIFICATIONS_ENABLED is False.
    - Catches all exceptions, logs them, and returns False so application flow is never disrupted.
    - Returns True upon successful delivery.
    """
    if not getattr(config, "EMAIL_NOTIFICATIONS_ENABLED", True):
        logger.info("Email notifications disabled via EMAIL_NOTIFICATIONS_ENABLED=false. Skipping email to %s", recipient)
        return False

    if not recipient or "@" not in recipient:
        logger.warning("Invalid recipient email address '%s'. Skipping email dispatch.", recipient)
        return False

    if not config.SMTP_USERNAME or not config.SMTP_PASSWORD or not config.MAIL_FROM:
        logger.warning(
            "SMTP credentials not fully configured in environment (SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM). "
            "Skipping email delivery to %s.", recipient
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.MAIL_FROM
    msg["To"] = recipient.strip()
    msg.set_content(text_body)

    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        if config.SMTP_USE_TLS:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
                smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                smtp.send_message(msg)

        logger.info("Email successfully sent to %s: '%s'", recipient, subject)
        return True
    except Exception as e:
        logger.exception("Failed to deliver email to %s for subject '%s': %s", recipient, subject, e)
        return False


def send_otp_email(recipient: str, otp: str) -> None:
    """Sends password reset OTP email to student via configured SMTP server."""
    msg = EmailMessage()
    msg["Subject"] = (
        f"{config.COLLEGE_NAME} Hostel Complaint Portal - "
        "Password Reset OTP"
    )
    msg["From"] = config.MAIL_FROM
    msg["To"] = recipient

    msg.set_content(
        f"Your {config.COLLEGE_NAME} Hostel Complaint Portal "
        f"password reset OTP is: {otp}\n\n"
        f"This OTP expires in "
        f"{config.OTP_EXPIRY_MINUTES} minutes and can "
        f"be used only once.\n\n"
        "If you did not request this password reset, "
        "please ignore this email."
    )

    if (
        not config.SMTP_USERNAME
        or not config.SMTP_PASSWORD
        or not config.MAIL_FROM
    ):
        raise RuntimeError(
            "SMTP_USERNAME, SMTP_PASSWORD and "
            "MAIL_FROM must be configured in .env"
        )

    if config.SMTP_USE_TLS:
        with smtplib.SMTP(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=20
        ) as smtp:
            smtp.starttls()
            smtp.login(
                config.SMTP_USERNAME,
                config.SMTP_PASSWORD
            )
            smtp.send_message(msg)
    else:
        with smtplib.SMTP_SSL(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=20
        ) as smtp:
            smtp.login(
                config.SMTP_USERNAME,
                config.SMTP_PASSWORD
            )
            smtp.send_message(msg)


def send_complaint_status_email(
    student_name: str,
    student_email: str,
    complaint_id: int,
    complaint_title: str,
    new_status: str,
    remarks: str = "",
    assigned_to: str = ""
) -> bool:
    """
    Sends a complaint status update email to the student.
    Failure to send will NOT raise an exception.
    """
    subject = f"{config.COLLEGE_NAME} IntelliHostel — Complaint #{complaint_id} Status Updated"

    name = student_name.strip() if student_name else "Student"
    assigned_line = f"Assigned Technician/Staff: {assigned_to.strip()}\n" if assigned_to else ""
    remarks_line = f"Administration Remarks: {remarks.strip()}\n" if remarks else ""

    text_body = (
        f"Dear {name},\n\n"
        f"Your hostel complaint has been updated:\n\n"
        f"Complaint ID: #{complaint_id}\n"
        f"Title: {complaint_title}\n"
        f"Status: {new_status}\n"
        f"{assigned_line}"
        f"{remarks_line}\n"
        f"Please log in to the IntelliHostel portal to view the complete details and tracking history:\n"
        f"{config.APP_BASE_URL}/complaint/{complaint_id}\n\n"
        f"Regards,\n"
        f"IntelliHostel Administration\n"
        f"{config.COLLEGE_NAME}\n"
    )

    badge_color = "#10b981" if new_status.lower() == "resolved" else ("#f59e0b" if new_status.lower() == "in progress" else "#ef4444" if new_status.lower() == "rejected" else "#3b82f6")

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
        .card {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
        .header {{ background: #0f172a; padding: 24px; color: #ffffff; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }}
        .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #94a3b8; }}
        .content {{ padding: 24px; }}
        .greeting {{ font-size: 15px; margin-bottom: 16px; font-weight: 500; }}
        .detail-box {{ background: #f8fafc; border-left: 4px solid #0284c7; border-radius: 6px; padding: 16px; margin: 16px 0; }}
        .status-pill {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 12px; color: #ffffff; background-color: {badge_color}; }}
        .field-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-top: 10px; font-weight: 600; }}
        .field-val {{ font-size: 14px; font-weight: 500; color: #0f172a; margin-top: 2px; }}
        .btn {{ display: inline-block; background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 20px; text-align: center; }}
        .footer {{ padding: 16px 24px; background: #f1f5f9; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>IntelliHostel Portal</h1>
          <p>{config.COLLEGE_NAME}</p>
        </div>
        <div class="content">
          <div class="greeting">Dear {name},</div>
          <p style="font-size: 14px; line-height: 1.5; margin: 0 0 16px 0;">Your complaint has received an administrative update.</p>
          
          <div class="detail-box">
            <div class="field-label">Complaint Reference</div>
            <div class="field-val">#{complaint_id} — {complaint_title}</div>
            
            <div class="field-label">New Status</div>
            <div style="margin-top: 4px;"><span class="status-pill">{new_status}</span></div>
            
            {"<div class='field-label'>Assigned Technician</div><div class='field-val'>" + assigned_to + "</div>" if assigned_to else ""}
            {"<div class='field-label'>Admin Remarks</div><div class='field-val'>" + remarks + "</div>" if remarks else ""}
          </div>
          
          <a href="{config.APP_BASE_URL}/complaint/{complaint_id}" class="btn">View Complaint in Portal</a>
        </div>
        <div class="footer">
          IntelliHostel Complaint System • {config.COLLEGE_NAME}<br>
          This is an automated notification. Please do not reply directly to this email.
        </div>
      </div>
    </body>
    </html>
    """

    return send_email(recipient=student_email, subject=subject, text_body=text_body, html_body=html_body)


def send_common_issue_status_email(
    student_name: str,
    student_email: str,
    issue_code: str,
    issue_title: str,
    hostel: str,
    new_status: str,
    remarks: str = "",
    assigned_to: str = ""
) -> bool:
    """
    Sends a Common Issue status update email to an affected student.
    """
    code_display = issue_code or "Common Issue"
    subject = f"{config.COLLEGE_NAME} IntelliHostel — Common Issue Update: {issue_title} ({new_status})"

    name = student_name.strip() if student_name else "Student"
    assigned_line = f"Assigned Technician/Staff: {assigned_to.strip()}\n" if assigned_to else ""
    remarks_line = f"Admin Remark:\n{remarks.strip()}\n" if remarks else ""

    text_body = (
        f"Dear {name},\n\n"
        f"Your hostel complaint associated with:\n\n"
        f"{issue_title} ({hostel}) [{code_display}]\n\n"
        f"has been updated.\n\n"
        f"Status:\n{new_status}\n\n"
        f"{assigned_line}"
        f"{remarks_line}"
        f"Please log in to IntelliHostel to view the complete details:\n"
        f"{config.APP_BASE_URL}/notifications\n\n"
        f"Regards,\n"
        f"IntelliHostel Administration\n"
        f"{config.COLLEGE_NAME}\n"
    )

    badge_color = "#10b981" if new_status.lower() == "resolved" else ("#f59e0b" if new_status.lower() == "in progress" else "#ef4444" if new_status.lower() == "rejected" else "#3b82f6")

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
        .card {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
        .header {{ background: #0f172a; padding: 24px; color: #ffffff; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }}
        .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #94a3b8; }}
        .content {{ padding: 24px; }}
        .greeting {{ font-size: 15px; margin-bottom: 16px; font-weight: 500; }}
        .detail-box {{ background: #f8fafc; border-left: 4px solid #8b5cf6; border-radius: 6px; padding: 16px; margin: 16px 0; }}
        .status-pill {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 12px; color: #ffffff; background-color: {badge_color}; }}
        .field-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-top: 10px; font-weight: 600; }}
        .field-val {{ font-size: 14px; font-weight: 500; color: #0f172a; margin-top: 2px; }}
        .btn {{ display: inline-block; background-color: #8b5cf6; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 20px; text-align: center; }}
        .footer {{ padding: 16px 24px; background: #f1f5f9; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>IntelliHostel Common Issue Update</h1>
          <p>{config.COLLEGE_NAME}</p>
        </div>
        <div class="content">
          <div class="greeting">Dear {name},</div>
          <p style="font-size: 14px; line-height: 1.5; margin: 0 0 16px 0;">An ongoing common hostel issue linked to your complaint has received an administrative update.</p>
          
          <div class="detail-box">
            <div class="field-label">Master Common Issue</div>
            <div class="field-val">{issue_title} ({hostel}) — <strong>{code_display}</strong></div>
            
            <div class="field-label">Updated Status</div>
            <div style="margin-top: 4px;"><span class="status-pill">{new_status}</span></div>
            
            {"<div class='field-label'>Assigned Staff</div><div class='field-val'>" + assigned_to + "</div>" if assigned_to else ""}
            {"<div class='field-label'>Admin Remark</div><div class='field-val'>" + remarks + "</div>" if remarks else ""}
          </div>
          
          <a href="{config.APP_BASE_URL}/notifications" class="btn">View Notifications in Portal</a>
        </div>
        <div class="footer">
          IntelliHostel Common Issues Engine • {config.COLLEGE_NAME}<br>
          This is an automated notification. Please do not reply directly to this email.
        </div>
      </div>
    </body>
    </html>
    """

    return send_email(recipient=student_email, subject=subject, text_body=text_body, html_body=html_body)


def send_common_issue_broadcast_emails(
    common_issue_id: int,
    status: str,
    remarks: str = "",
    assigned_to: str = "",
    conn: Optional[Any] = None
) -> int:
    """
    Broadcasts email notifications to ALL distinct students affected by a Common Issue.
    Deduplicates recipients so each affected student receives exactly ONE email.
    Returns the count of successfully delivered emails.
    """
    close_conn = False
    if conn is None:
        from database.db import get_db_connection
        conn = get_db_connection()
        close_conn = True

    try:
        issue_row = conn.execute(
            "SELECT issue_code, title, hostel FROM common_issues WHERE id = ?",
            (common_issue_id,)
        ).fetchone()

        issue_code = issue_row["issue_code"] if issue_row and "issue_code" in issue_row.keys() else f"CI-{common_issue_id:03d}"
        issue_title = issue_row["title"] if issue_row else f"Common Issue #{common_issue_id}"
        hostel = issue_row["hostel"] if issue_row else "Hostel"

        # Query distinct students with valid emails linked to this common issue
        affected_students = conn.execute(
            """
            SELECT DISTINCT s.id, s.name, s.email
            FROM complaints c
            JOIN students s ON s.id = c.student_id
            WHERE c.common_issue_id = ?
              AND s.email IS NOT NULL
              AND s.email != ''
            """,
            (common_issue_id,)
        ).fetchall()

        delivered_count = 0
        for student in affected_students:
            try:
                success = send_common_issue_status_email(
                    student_name=student["name"],
                    student_email=student["email"],
                    issue_code=issue_code,
                    issue_title=issue_title,
                    hostel=hostel,
                    new_status=status,
                    remarks=remarks,
                    assigned_to=assigned_to
                )
                if success:
                    delivered_count += 1
            except Exception as ex:
                logger.exception("Failed to send common issue email to student %s (%s): %s", student["id"], student["email"], ex)

        return delivered_count
    finally:
        if close_conn:
            conn.close()


def send_complaint_submitted_email(
    student_name: str,
    student_email: str,
    complaint_id: int,
    title: str,
    category: str,
    priority: str,
    estimated_days: Optional[float] = None
) -> bool:
    """
    Sends a confirmation email to the student upon successful complaint submission.
    """
    subject = f"{config.COLLEGE_NAME} IntelliHostel — Complaint #{complaint_id} Received"
    name = student_name.strip() if student_name else "Student"
    est_line = f"Estimated Resolution Time: {estimated_days:.1f} days\n" if estimated_days is not None else ""

    text_body = (
        f"Dear {name},\n\n"
        f"Your hostel complaint has been successfully recorded in the IntelliHostel portal:\n\n"
        f"Complaint ID: #{complaint_id}\n"
        f"Title: {title}\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n"
        f"{est_line}\n"
        f"You will receive portal notifications and emails as hostel administration updates your ticket.\n\n"
        f"View your complaint status:\n"
        f"{config.APP_BASE_URL}/complaint/{complaint_id}\n\n"
        f"Regards,\n"
        f"IntelliHostel Administration\n"
        f"{config.COLLEGE_NAME}\n"
    )

    return send_email(recipient=student_email, subject=subject, text_body=text_body)

