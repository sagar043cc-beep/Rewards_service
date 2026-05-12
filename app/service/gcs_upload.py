import json
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from dotenv import load_dotenv
from google.cloud import storage
from google.oauth2 import service_account

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "app" / ".env")

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
}


def _get_bucket_name() -> str:
    bucket = (os.getenv("GCS_BUCKET_NAME") or "").strip().strip('"').strip("'")
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GCS_BUCKET_NAME is not configured.",
        )
    return bucket


def _get_storage_client() -> storage.Client:
    sa_json = os.getenv("GCS_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(info)
            return storage.Client(credentials=creds, project=info.get("project_id"))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid GCS_SERVICE_ACCOUNT_JSON value.",
            ) from exc

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "app/gcs-service-account.json")
    if credentials_path and os.path.exists(credentials_path):
        creds = service_account.Credentials.from_service_account_file(credentials_path)
        return storage.Client(credentials=creds, project=creds.project_id)

    return storage.Client()


def _sanitize_filename(name: str) -> str:
    safe = name.strip().replace(" ", "_")
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", safe)
    return safe or "image"


def _get_extension(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ""
    ext = f".{filename.rsplit('.', 1)[-1].lower()}"
    return ext


def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image format. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image content type.",
        )


def upload_event_image_to_gcs(*, file: UploadFile, tenant_id: UUID) -> dict:
    _validate_upload(file)

    bucket_name = _get_bucket_name()
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)

    ext = _get_extension(file.filename)
    base_name = _sanitize_filename((file.filename or "image").rsplit(".", 1)[0])
    unique_name = f"{base_name}_{uuid4().hex}{ext}"
    object_path = f"tenants/{tenant_id}/events/{unique_name}"

    try:
        blob = bucket.blob(object_path)
        file.file.seek(0)
        blob.upload_from_file(file.file, content_type=file.content_type)

        expires = int(os.getenv("GCS_SIGNED_URL_EXPIRES_SECONDS", "3600"))
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires),
            method="GET",
        )

        return {
            "bucket": bucket_name,
            "object_path": object_path,
            "url": signed_url,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to GCS.",
        ) from exc


def upload_image_to_gcs(*, file: UploadFile) -> dict:
    _validate_upload(file)

    bucket_name = _get_bucket_name()
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)

    ext = _get_extension(file.filename)
    base_name = _sanitize_filename((file.filename or "image").rsplit(".", 1)[0])
    unique_name = f"{base_name}_{uuid4().hex}{ext}"
    object_path = f"uploads/{unique_name}"

    try:
        blob = bucket.blob(object_path)
        file.file.seek(0)
        blob.upload_from_file(file.file, content_type=file.content_type)

        expires = int(os.getenv("GCS_SIGNED_URL_EXPIRES_SECONDS", "3600"))
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires),
            method="GET",
        )

        return {
            "bucket": bucket_name,
            "object_path": object_path,
            "url": signed_url,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to GCS.",
        ) from exc
