import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.badges import Badge
from app.schemas.image_schema import GymImageOut
from app.schemas.badges import BadgeCreate, BadgeUpdate
from app.service.badges import BadgeService, NotFoundError, ValidationError
from app.service.gcs_upload import upload_image_to_gcs
from app.auth import get_current_tenant_id
from app.utils.response import success_response, paginated_response
from app.utils.gcs import normalize_db_image_path

router = APIRouter(prefix="/badges", tags=["Badges"])
logger = logging.getLogger(__name__)


def get_badge_service(db: Session = Depends(get_db)) -> BadgeService:
    return BadgeService(db)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _badge_to_dict(b: Badge) -> dict:
    image = GymImageOut(id=str(b.id), image=b.icon_path)
    return {
        "id": str(b.id),
        "name": b.name,
        "icon_path": image.image,
        "icon_url": image.image_url,
        "tenant_id": str(b.tenant_id) if b.tenant_id else None,
    }


def _raise_not_found(badge_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Badge {badge_id} not found.",
    )


def _raise_validation(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _save_image_file(upload_file: UploadFile) -> str:
    """
    Validate and upload an image file to GCS.
    Returns stable object path to store in DB, e.g. 'uploads/filename.png'.
    Raises ValidationError on invalid input.
    """
    if not upload_file.content_type or not upload_file.content_type.startswith("image/"):
        raise ValidationError("Badge icon must be an image file.")

    try:
        result = upload_image_to_gcs(file=upload_file)
        object_path = result.get("object_path")
        if not object_path:
            raise ValidationError("Upload response missing object path.")
        return normalize_db_image_path(object_path) or object_path
    except Exception as e:
        logger.error("Failed to upload badge icon file: %s", e)
        raise ValidationError("Could not upload badge icon file.") from e


def _normalize_badge_image_path(raw_value: Optional[str]) -> Optional[str]:
    return normalize_db_image_path(raw_value)


def _delete_image_file(image_path: Optional[str]) -> None:
    """Delete a badge image file from disk if it exists (skip external URLs)."""
    if not image_path:
        return
    if image_path.startswith(("http://", "https://")):
        return
    full_path = os.path.join("static", image_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        logger.warning("Failed to delete badge image file %s: %s", full_path, e)


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK)
def list_badges(
    page: int = 1,
    page_size: int = 10,
    tenant_id: UUID = Depends(get_current_tenant_id),
    badge_service: BadgeService = Depends(get_badge_service),
):
    """List all badges for the authenticated tenant."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    items, total = badge_service.list_badges(tenant_id=tenant_id, page=page, page_size=page_size)
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
    tenant_id: UUID = Depends(get_current_tenant_id),
    badge_service: BadgeService = Depends(get_badge_service),
):
    """Fetch a single badge by ID (tenant-scoped)."""
    db_badge = badge_service.get_badge(badge_id)
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
    icon_path: Optional[str] = Form(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    badge_service: BadgeService = Depends(get_badge_service),
):
    """Create a new badge with optional icon image for the authenticated tenant."""
    try:
        normalized_icon_path = _normalize_badge_image_path(icon_path)
        if icon is not None:
            normalized_icon_path = _save_image_file(icon)

        badge_in = BadgeCreate(name=name, icon_path=normalized_icon_path)
        db_badge = badge_service.create_badge(badge_in, tenant_id)
    except (ValidationError, PydanticValidationError) as exc:
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
    icon_path: Optional[str] = Form(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    badge_service: BadgeService = Depends(get_badge_service),
):
    """Partial update of a badge (only supplied fields are changed)."""
    try:
        # Fetch existing badge for potential icon cleanup and ownership check
        old_badge = badge_service.get_badge(badge_id)
        if old_badge is None:
            _raise_not_found(badge_id)
        if old_badge.tenant_id != tenant_id:
            _raise_not_found(badge_id)

        # Initialize image path tracker for cleanup on failure
        new_image_path = None

        # Collect non-image updates
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if icon_path is not None:
            update_data["icon_path"] = _normalize_badge_image_path(icon_path)

        # Validate non-image fields before potentially saving image
        if update_data:
            try:
                BadgeUpdate(**update_data)  # may raise PydanticValidationError
            except PydanticValidationError as e:
                raise ValidationError(str(e))

        # Handle image upload (after validating other fields)
        if icon is not None:
            new_image_path = _save_image_file(icon)
            update_data["icon_path"] = new_image_path

        if not update_data:
            # Nothing to change — return existing
            return success_response(
                message="Badge updated successfully",
                data=_badge_to_dict(old_badge),
            )

        try:
            badge_in = BadgeUpdate(**update_data)
            db_badge = badge_service.update_badge(badge_id, badge_in)
        except Exception:
            # Clean up newly saved image on any failure
            if new_image_path:
                _delete_image_file(new_image_path)
            raise

        # Delete old image if it was replaced (only on success)
        if new_image_path and old_badge.icon_path and old_badge.icon_path != new_image_path:
            _delete_image_file(old_badge.icon_path)

    except NotFoundError:
        # Ensure cleanup if image was saved before NotFound occurred
        if new_image_path:
            _delete_image_file(new_image_path)
        _raise_not_found(badge_id)
    except (ValidationError, PydanticValidationError) as exc:
        # Ensure cleanup if image was saved before validation error
        if new_image_path:
            _delete_image_file(new_image_path)
        _raise_validation(exc)

    return success_response(
        message="Badge updated successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{badge_id}", status_code=status.HTTP_200_OK)
def delete_existing_badge(
    badge_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    badge_service: BadgeService = Depends(get_badge_service),
):
    """Delete a badge by ID (tenant-scoped)."""
    try:
        # Verify ownership before deletion
        old_badge = badge_service.get_badge(badge_id)
        if old_badge is None or old_badge.tenant_id != tenant_id:
            _raise_not_found(badge_id)

        db_badge = badge_service.delete_badge(badge_id)
        # Delete associated icon image if exists
        if db_badge.icon_path:
            _delete_image_file(db_badge.icon_path)
    except NotFoundError:
        _raise_not_found(badge_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge deleted successfully",
        data=_badge_to_dict(db_badge),
    )
