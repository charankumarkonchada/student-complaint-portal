import os
import uuid
import logging
import requests
from werkzeug.utils import secure_filename
import config

logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Checks whether the file extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )

def upload_to_cloud_storage(file_obj, original_name, student_id):
    """
    Uploads an attachment to Supabase Storage bucket.
    If Supabase is not configured or unavailable, safely saves locally in UPLOAD_FOLDER.
    """
    if not original_name or "." not in original_name:
        raise ValueError("Invalid attachment filename.")

    ext = original_name.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    # 1. Attempt Supabase Cloud Storage if configured
    if config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY and config.SUPABASE_STORAGE_BUCKET:
        try:
            object_path = f"complaints/{student_id}/{safe_name}"
            url = (
                f"{config.SUPABASE_URL.rstrip('/')}"
                f"/storage/v1/object/"
                f"{config.SUPABASE_STORAGE_BUCKET}/"
                f"{object_path}"
            )

            content_types = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "pdf": "application/pdf"
            }
            content_type = content_types.get(ext, "application/octet-stream")

            file_obj.seek(0)
            data = file_obj.read()

            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
                    "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": content_type,
                    "x-upsert": "false"
                },
                data=data,
                timeout=20
            )

            if response.ok:
                return (
                    f"{config.SUPABASE_URL.rstrip('/')}"
                    f"/storage/v1/object/public/"
                    f"{config.SUPABASE_STORAGE_BUCKET}/"
                    f"{object_path}"
                )
            else:
                logger.warning("Supabase storage upload responded %s. Falling back to local storage.", response.status_code)
        except Exception as e:
            logger.warning("Supabase storage upload failed (%s). Falling back to local storage.", e)

    # 2. Resilient local filesystem storage fallback
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    local_path = os.path.join(config.UPLOAD_FOLDER, safe_name)
    file_obj.seek(0)
    file_obj.save(local_path)
    return f"/static/uploads/{safe_name}"
