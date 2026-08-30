import smtplib
from email.message import EmailMessage
import config

def send_otp_email(recipient, otp):
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
