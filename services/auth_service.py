import re
import hashlib
from flask import session
import config

def is_college_email(email):
    """Validates that the email is a single email belonging to the college domain."""
    email = (email or "").strip().lower()
    return (
        email.count("@") == 1
        and email.endswith(config.COLLEGE_DOMAIN)
    )

def is_valid_id(id_no):
    """Validates that the student ID matches the RGUKT pattern O123456."""
    return bool(
        re.fullmatch(
            r"O\d{6}",
            (id_no or "").strip().upper()
        )
    )

def hash_reset_token(token):
    """Hashes the password reset OTP or token using SHA-256."""
    return hashlib.sha256(
        token.encode()
    ).hexdigest()

def student_required():
    """Checks if a student session is active."""
    return "student_id" in session

def admin_required():
    """Checks if an admin session is active."""
    return "admin" in session
