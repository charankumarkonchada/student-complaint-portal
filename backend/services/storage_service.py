import os
import uuid
import logging
import requests
from werkzeug.utils import secure_filename
import backend.config as config

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


def extract_storage_path(image_ref: str, bucket_name: str = "") -> str:
    """
    Safely extracts the relative object path in Supabase Storage from an image reference or URL.
    Returns None if the reference is empty, local, invalid, or does not target the bucket.
    """
    if not image_ref or not isinstance(image_ref, str):
        return None

    cleaned = image_ref.strip()
    if not cleaned:
        return None

    # Ignore local fallback uploads
    if cleaned.startswith("/static/") or cleaned.startswith("static/"):
        return None

    bucket = (bucket_name or getattr(config, "SUPABASE_STORAGE_BUCKET", "complaint-attachments") or "complaint-attachments").strip()

    # If it's a full or partial URL containing the bucket name:
    # e.g., .../storage/v1/object/(public|authenticated|sign)/<bucket>/<object_path>
    bucket_marker = f"/{bucket}/"
    if bucket_marker in cleaned:
        raw_path = cleaned.split(bucket_marker, 1)[1]
        raw_path = raw_path.split("?")[0].strip().lstrip("/")
        if raw_path and not raw_path.startswith("..") and "/" in raw_path:
            return raw_path

    # If already a relative storage path starting with complaints/
    if cleaned.startswith("complaints/"):
        raw_path = cleaned.split("?")[0].strip().lstrip("/")
        if raw_path and not raw_path.startswith("..") and "/" in raw_path:
            return raw_path

    return None


def delete_from_cloud_storage(image_refs, bucket_name: str = "") -> bool:
    """
    Deletes complaint attachment object(s) from Supabase Storage using the official Storage API.

    Accepts a single string URL/path or an iterable of URLs/paths.
    Only deletes the exact objects belonging to the specified image references.
    Never deletes unrelated files or the bucket itself.
    Safely handles missing or empty paths.
    Logs and reports failures.

    Returns:
        bool: True if deletion succeeded or if there was nothing to delete,
              False if deletion failed.
    """
    if not image_refs:
        return True

    if isinstance(image_refs, str):
        refs = [image_refs]
    elif hasattr(image_refs, "__iter__"):
        refs = list(image_refs)
    else:
        refs = [str(image_refs)]

    bucket = (bucket_name or getattr(config, "SUPABASE_STORAGE_BUCKET", "complaint-attachments") or "complaint-attachments").strip()

    # 1. Safely remove local file if a local fallback upload path was provided
    for ref in refs:
        if isinstance(ref, str) and (ref.strip().startswith("/static/uploads/") or ref.strip().startswith("static/uploads/")):
            local_fname = os.path.basename(ref.strip())
            if local_fname and not local_fname.startswith(".."):
                local_path = os.path.join(config.UPLOAD_FOLDER, local_fname)
                try:
                    if os.path.exists(local_path) and os.path.isfile(local_path):
                        os.remove(local_path)
                        logger.info("Deleted local fallback attachment file: %s", local_path)
                except Exception as e:
                    logger.warning("Could not delete local fallback attachment %s: %s", local_path, e)

    # 2. Extract and sanitize Supabase Storage paths
    target_paths = []
    for ref in refs:
        storage_path = extract_storage_path(ref, bucket_name=bucket)
        if storage_path and storage_path not in target_paths:
            target_paths.append(storage_path)

    # If no remote Supabase objects need deletion, return successfully
    if not target_paths:
        return True

    # Check configuration
    supabase_url = getattr(config, "SUPABASE_URL", "")
    service_role_key = getattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    if not (supabase_url and service_role_key and bucket):
        logger.error(
            "Supabase Storage credentials not configured (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET). "
            "Cannot delete remote object(s): %s",
            target_paths
        )
        return False

    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.delete(
            url,
            headers=headers,
            json={"prefixes": target_paths},
            timeout=20
        )
        if response.ok:
            logger.info(
                "Successfully deleted %d object(s) from Supabase Storage bucket '%s': %s",
                len(target_paths),
                bucket,
                target_paths
            )
            return True

        logger.error(
            "Supabase Storage deletion failed with HTTP %s: %s. Target paths: %s",
            response.status_code,
            response.text,
            target_paths
        )
        return False
    except Exception as e:
        logger.exception("Supabase Storage deletion encountered an error for paths %s: %s", target_paths, e)
        return False

