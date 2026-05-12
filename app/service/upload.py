from __future__ import annotations

import json
import logging
import os
import re
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from google.cloud import storage
from google.oauth2 import service_account

from app.core.settings import settings

logger = logging.getLogger(__name__)


ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


def _get_bucket_name() -> str:
    bucket = settings.GCS_BUCKET_NAME or os.getenv("GCS_BUCKET_NAME")

    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GCS_BUCKET_NAME is not configured",
        )

    return bucket


def _get_storage_client() -> storage.Client:
    sa_json = (
        settings.GCS_SERVICE_ACCOUNT_JSON
        or os.getenv("GCS_SERVICE_ACCOUNT_JSON")
    )

    if sa_json:
        try:
            info = json.loads(sa_json)

            creds = service_account.Credentials.from_service_account_info(
                info
            )

            return storage.Client(
                credentials=creds,
                project=info.get("project_id"),
            )

        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid GCS service account JSON",
            ) from exc

    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )

    return storage.Client()


def _safe_ext(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ""

    ext = filename.rsplit(".", 1)[-1].lower().strip()

    if len(ext) > 10:
        return ""

    return f".{ext}"


def _sanitize_filename(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)

    return name or "file"


def _validate_image(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image type",
        )


def _generate_signed_url(blob) -> str:
    expires_seconds = int(
        settings.GCS_SIGNED_URL_EXPIRES_SECONDS
        or os.getenv("GCS_SIGNED_URL_EXPIRES_SECONDS", "3600")
    )

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expires_seconds),
        method="GET",
    )


def upload_image_to_gcs(
    *,
    file: UploadFile,
    tenant_id: UUID,
    folder: str,
    object_name_prefix: str,
) -> str:
    _validate_image(file)

    bucket_name = _get_bucket_name()
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)

    ext = _safe_ext(file.filename)

    sanitized_prefix = _sanitize_filename(object_name_prefix)

    unique_id = uuid4().hex

    object_name = (
        f"tenants/{tenant_id}/{folder}/"
        f"{sanitized_prefix}_{unique_id}{ext}"
    )

    logger.info(
        "Starting GCS upload",
        extra={
            "bucket": bucket_name,
            "object_name": object_name,
            "tenant_id": str(tenant_id),
            "content_type": file.content_type,
        },
    )

    try:
        blob = bucket.blob(object_name)

        file.file.seek(0)

        blob.upload_from_file(
            file.file,
            content_type=file.content_type,
        )

        signed_url = _generate_signed_url(blob)

        logger.info(
            "GCS upload completed",
            extra={
                "bucket": bucket_name,
                "object_name": object_name,
                "tenant_id": str(tenant_id),
            },
        )

        return signed_url

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "GCS upload failed",
            extra={
                "bucket": bucket_name,
                "object_name": object_name,
                "tenant_id": str(tenant_id),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to GCS",
        ) from exc


def upload_training_program_image_to_gcs(
    *,
    file: UploadFile,
    tenant_id: UUID,
    training_program_name: str,
) -> str:
    return upload_image_to_gcs(
        file=file,
        tenant_id=tenant_id,
        folder="training_programs",
        object_name_prefix=training_program_name,
    )