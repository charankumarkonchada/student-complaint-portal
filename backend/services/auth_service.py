import re
import hashlib
from flask import session
import backend.config as config

def is_college_email(email):
    """Validates that the email is a single email belonging to the college domain."""
    email = (email or "").strip().lower()
    domain = config.COLLEGE_DOMAIN.lower()
    if not domain.startswith("@"):
        domain = "@" + domain
    return (
        email.count("@") == 1
        and email.endswith(domain)
        and email != domain
        and bool(email.split("@")[0])
    )

def mask_email(email: str) -> str:
    """
    Masks the username part of an email address for safe display.
    E.g., o210001@rguktong.ac.in -> o2*****@rguktong.ac.in
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return email
    parts = email.split("@", 1)
    local_part, domain = parts[0], parts[1]
    if len(local_part) <= 2:
        masked_local = (local_part[0] + "*") if local_part else "*"
    else:
        masked_local = local_part[:2] + ("*" * (len(local_part) - 2))
    return f"{masked_local}@{domain}"

def is_valid_id(id_no):
    """Validates that the student ID matches the RGUKT pattern: O, N, R, or S followed by 6 digits."""
    return bool(
        re.fullmatch(
            r"[ONRS]\d{6}",
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
