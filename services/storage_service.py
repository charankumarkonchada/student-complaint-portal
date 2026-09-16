import os
import uuid
import logging
import requests
from werkzeug.utils import secure_filename
import config

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}
MAGIC = {
    "jpg": ((b"\xff\xd8\xff",),),
    "jpeg": ((b"\xff\xd8\xff",),),
    "png": ((b"\x89PNG\r\n\x1a\n",),),
}

def allowed_file(filename):
    if not filename or "\x00" in filename or "/" in filename or "\\" in filename:
        return False
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS

def _validate_content(file_obj, ext):
    if ext not in CONTENT_TYPES:
        raise ValueError("Unsupported attachment type.")
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > config.MAX_CONTENT_LENGTH:
        raise ValueError("Attachment exceeds the maximum allowed size.")
    header = file_obj.read(16)
    file_obj.seek(0)
    if not any(header.startswith(sig) for group in MAGIC.get(ext, ()) for sig in group):
        raise ValueError("Attachment content does not match its file type.")

def upload_to_cloud_storage(file_obj, original_name, student_id):
    if not original_name or not allowed_file(original_name):
        raise ValueError("Invalid attachment filename.")
    ext = original_name.rsplit(".", 1)[1].lower()
    _validate_content(file_obj, ext)
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    object_path = f"complaints/{student_id}/{safe_name}"
    content_type = CONTENT_TYPES[ext]

    if config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY and config.SUPABASE_STORAGE_BUCKET:
        try:
            url = f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/{config.SUPABASE_STORAGE_BUCKET}/{object_path}"
            file_obj.seek(0)
            data = file_obj.read()
            response = requests.post(url, headers={
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
                "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": content_type,
                "x-upsert": "false"
            }, data=data, timeout=20)
            if response.ok:
                # Prefer private buckets in production. The service currently returns a URL
                # for compatibility; production should configure a private bucket and a
                # signed-URL delivery layer before exposing attachments externally.
                return f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{config.SUPABASE_STORAGE_BUCKET}/{object_path}"
            logger.error("Supabase storage upload failed with HTTP %s", response.status_code)
        except Exception:
            logger.exception("Supabase storage upload failed")

    if not config.ALLOW_LOCAL_STORAGE_FALLBACK:
        raise RuntimeError("Cloud attachment storage is unavailable and local fallback is disabled.")

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    local_path = os.path.join(config.UPLOAD_FOLDER, safe_name)
    file_obj.seek(0)
    file_obj.save(local_path)
    return f"/static/uploads/{safe_name}"
