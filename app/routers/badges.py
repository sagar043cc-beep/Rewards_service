import logging
import os
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.badges import Badge
from app.schemas.badges import BadgeCreate, BadgeUpdate, BadgeOut
from app.service.badges import (
    get_badges,
    get_badge,
    create_badge,
    update_badge,
    delete_badge,
    NotFoundError,
    ValidationError,
)
from app.auth import get_current_tenant_id
from app.utils.response import success_response, error_response, paginated_response

router = APIRouter(prefix="/badges", tags=["Badges"])
logger = logging.getLogger(__name__)

# Configuration for badge icon uploads
BADGE_UPLOAD_DIR = os.path.join("static", "badges")
os.makedirs(BADGE_UPLOAD_DIR, exist_ok=True)

# Allowed image extensions
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _badge_to_dict(b: Badge) -> dict:
    raw_icon = b.icon_path
    if raw_icon:
        # If it's already a full URL, use as-is; otherwise prefix static path
        if raw_icon.startswith(("http://", "https://")):
            icon_url = raw_icon
        else:
            icon_url = f"/static/{raw_icon}"
    else:
        icon_url = None
    return {
        "id": str(b.id),
        "name": b.name,
        "icon_url": icon_url,
        "tenant_id": str(b.tenant_id) if b.tenant_id else None,
    }


def _raise_not_found(badge_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Badge {badge_id} not found.",
    )


def _raise_validation(exc: ValidationError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _save_icon_file(upload_file: UploadFile) -> str:
    """
    Validate and save an uploaded icon file.
    Returns the relative path (e.g., 'badges/<filename>') to store in DB.
    Raises ValidationError on invalid input.
    """
    if not upload_file.content_type.startswith("image/"):
        raise ValidationError("Icon must be an image file.")

    # Determine file extension
    original_filename = upload_file.filename or ""
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image format. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    # Generate unique filename
    filename = f"{uuid.uuid4().hex}{ext}"
    relative_path = os.path.join("badges", filename).replace("\\", "/")
    full_path = os.path.join(BADGE_UPLOAD_DIR, filename)

    try:
        # Read uploaded file content and write to disk
        content = upload_file.file.read()
        with open(full_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error("Failed to save icon file: %s", e)
        raise ValidationError("Could not save icon file.") from e

    return relative_path


def _delete_icon_file(icon_path: Optional[str]) -> None:
    """Delete an icon file from disk if it exists (skip external URLs)."""
    if not icon_path:
        return
    # Skip external URLs
    if icon_path.startswith(("http://", "https://")):
        return
    full_path = os.path.join("static", icon_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        logger.warning("Failed to delete icon file %s: %s", full_path, e)


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK)
def list_badges(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all badges for the authenticated tenant."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    items, total = get_badges(db, tenant_id=tenant_id, page=page, page_size=page_size)
    return paginated_response(
        message="Badges fetched successfully",
        data=[_badge_to_dict(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Get single ───────────────────────────────────────────────────────────────

@router.get("/{badge_id}", status_code=status.HTTP_200_OK)
def read_badge(
    badge_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Fetch a single badge by ID (tenant-scoped)."""
    db_badge = get_badge(db, badge_id)
    if not db_badge or db_badge.tenant_id != tenant_id:
        _raise_not_found(badge_id)

    return success_response(
        message="Badge fetched successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_new_badge(
    name: str = Form(...),
    icon: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create a new badge with optional icon image for the authenticated tenant."""
    try:
        icon_path = None
        if icon is not None:
            icon_path = _save_icon_file(icon)
        badge_in = BadgeCreate(name=name, icon_path=icon_path, tenant_id=tenant_id)
        db_badge = create_badge(db, badge_in)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge created successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.put("/{badge_id}", status_code=status.HTTP_200_OK)
async def update_existing_badge(
    badge_id: UUID,
    name: Optional[str] = Form(None),
    icon: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Partial update of a badge (only supplied fields are changed)."""
    try:
        # Fetch existing badge for potential icon cleanup and ownership check
        old_badge = get_badge(db, badge_id)
        if old_badge is None:
            _raise_not_found(badge_id)
        if old_badge.tenant_id != tenant_id:
            _raise_not_found(badge_id)

        update_data = {}
        if name is not None:
            update_data["name"] = name

        new_icon_path = None
        if icon is not None:
            new_icon_path = _save_icon_file(icon)
            update_data["icon_path"] = new_icon_path

        if not update_data:
            # Nothing to change — return existing
            return success_response(
                message="Badge updated successfully",
                data=_badge_to_dict(old_badge),
            )

        badge_in = BadgeUpdate(**update_data)
        db_badge = update_badge(db, badge_id, badge_in)

        # Delete old icon file if it was replaced
        if new_icon_path and old_badge.icon_path and old_badge.icon_path != new_icon_path:
            _delete_icon_file(old_badge.icon_path)

    except NotFoundError:
        _raise_not_found(badge_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge updated successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{badge_id}", status_code=status.HTTP_200_OK)
def delete_existing_badge(
    badge_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Delete a badge by ID (tenant-scoped)."""
    try:
        # Verify ownership before deletion
        old_badge = get_badge(db, badge_id)
        if old_badge is None or old_badge.tenant_id != tenant_id:
            _raise_not_found(badge_id)

        db_badge = delete_badge(db, badge_id)
        # Delete associated icon file if exists
        if db_badge.icon_path:
            _delete_icon_file(db_badge.icon_path)
    except NotFoundError:
        _raise_not_found(badge_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge deleted successfully",
        data=_badge_to_dict(db_badge),
    )
