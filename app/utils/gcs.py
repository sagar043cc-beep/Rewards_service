from datetime import timedelta
from urllib.parse import urlparse

from google.cloud import storage

# Config
GCS_BUCKET_NAME = "bookify-gym"
GCS_UPLOAD_FOLDER = "uploads"
GCS_BASE_URL = "https://storage.googleapis.com"

# If you use a service account key file:
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/service-account.json"

storage_client = storage.Client()


def _normalize_object_path(raw_value: str, folder: str = GCS_UPLOAD_FOLDER) -> str:
    """
    Convert any URL/path into a stable object key under `folder`.
    Examples:
    - Screenshot.png -> uploads/Screenshot.png
    - uploads/Screenshot.png -> uploads/Screenshot.png
    - bookify-gym/uploads/Screenshot.png -> uploads/Screenshot.png
    - https://storage.googleapis.com/bookify-gym/uploads/Screenshot.png?... -> uploads/Screenshot.png
    """
    value = raw_value.strip().split("?", 1)[0]
    parsed = urlparse(value)

    if parsed.scheme in {"http", "https"} and parsed.netloc:
        path = parsed.path.lstrip("/")
    else:
        path = value.lstrip("/")

    bucket_prefix = f"{GCS_BUCKET_NAME}/"
    folder_prefix = f"{folder}/"

    if path.startswith(bucket_prefix):
        path = path[len(bucket_prefix):]
    if path.startswith(folder_prefix):
        return path
    return f"{folder_prefix}{path}"


def get_db_path(filename: str) -> str:
    """Given a filename/path/url, return DB key like 'uploads/<name>'."""
    if not filename:
        return filename
    return _normalize_object_path(filename)


def normalize_db_image_path(raw_value: str | None) -> str | None:
    """Normalize any URL/path into a stable DB key: 'uploads/<name>'."""
    if not raw_value:
        return None

    value = raw_value.strip()
    if not value:
        return None
    return _normalize_object_path(value)


def build_signed_url(db_image_path: str, expiration_minutes: int = 60) -> str | None:
    """
    Given the path stored in DB (e.g. "Screenshot_1_abc.png"),
    return a signed GCS URL valid for `expiration_minutes`.

    Returns None if db_image_path is None or empty.
    """
    if not db_image_path:
        return None

    clean_path = normalize_db_image_path(db_image_path)
    if not clean_path:
        return None

    blob_path = clean_path

    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_path)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET",
    )
    return signed_url


def build_public_url(db_image_path: str) -> str | None:
    """
    If your bucket is PUBLIC, use this instead of signed URLs.
    Returns: https://storage.googleapis.com/bookify-gym/uploads/filename.png
    """
    if not db_image_path:
        return None

    clean_path = normalize_db_image_path(db_image_path)
    if not clean_path:
        return None
    return f"{GCS_BASE_URL}/{GCS_BUCKET_NAME}/{clean_path}"
