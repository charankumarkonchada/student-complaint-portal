"""Services package for IntelliHostel."""
from services.auth_service import is_college_email, is_valid_id, hash_reset_token, student_required, admin_required
from services.email_service import send_otp_email
from services.storage_service import allowed_file, upload_to_cloud_storage

__all__ = [
    "is_college_email",
    "is_valid_id",
    "hash_reset_token",
    "student_required",
    "admin_required",
    "send_otp_email",
    "allowed_file",
    "upload_to_cloud_storage",
]
