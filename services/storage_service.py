import uuid
import requests
import config

def allowed_file(filename):
    """Checks whether the file extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )

def upload_to_cloud_storage(file_obj, original_name, student_id):
    """Uploads an attachment to Supabase storage bucket."""
    if not config.SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is not configured.")

    if not config.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured.")

    if not config.SUPABASE_STORAGE_BUCKET:
        raise RuntimeError("SUPABASE_STORAGE_BUCKET is not configured.")

    if not original_name or "." not in original_name:
        raise ValueError("Invalid attachment filename.")

    ext = original_name.rsplit(".", 1)[1].lower()
    object_path = f"complaints/{student_id}/{uuid.uuid4().hex}.{ext}"

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
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            f"Supabase Storage upload failed ({response.status_code}): {response.text[:500]}"
        )

    return (
        f"{config.SUPABASE_URL.rstrip('/')}"
        f"/storage/v1/object/public/"
        f"{config.SUPABASE_STORAGE_BUCKET}/"
        f"{object_path}"
    )
