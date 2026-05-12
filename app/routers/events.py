import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.events import event_to_dict
from app.schemas.events import EventCreate, EventUpdate
from app.service.events import EventService, NotFoundError, ValidationError
from app.service.gcs_upload import upload_image_to_gcs
from app.auth import get_current_tenant_id
from app.utils.gcs import normalize_db_image_path
from app.utils.response import success_response, paginated_response

router = APIRouter(prefix="/events", tags=["Events"])
logger = logging.getLogger(__name__)

# ─── Dependency Injection ─────────────────────────────────────────────────────

def get_event_service(db: Session = Depends(get_db)) -> EventService:
    """
    Dependency injection function to provide EventService instance.
    
    Args:
        db: Database session from FastAPI dependency
        
    Returns:
        EventService instance
    """
    return EventService(db)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _raise_not_found(event_id: UUID) -> None:
    """Raise HTTP 404 Not Found exception."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Event {event_id} not found.",
    )


def _raise_validation(exc: Exception) -> None:
    """Raise HTTP 400 Bad Request exception."""
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
        raise ValidationError("Event image must be an image file.")

    try:
        result = upload_image_to_gcs(file=upload_file)
        object_path = result.get("object_path")
        if not object_path:
            raise ValidationError("Upload response missing object path.")
        return normalize_db_image_path(object_path) or object_path
    except Exception as e:
        logger.error("Failed to upload event image file: %s", e)
        raise ValidationError("Could not upload event image file.") from e


def _normalize_event_image_path(raw_value: Optional[str]) -> Optional[str]:
    return normalize_db_image_path(raw_value)


def _delete_image_file(image_path: Optional[str]) -> None:
    """Delete an event image file from disk if it exists (skip external URLs)."""
    if not image_path:
        return
    if image_path.startswith(("http://", "https://")):
        return
    full_path = os.path.join("static", image_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        logger.warning("Failed to delete event image file %s: %s", full_path, e)


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK)
def list_events(
    tenant_id: UUID = Depends(get_current_tenant_id),
    status_filter: Optional[str] = None,
    location: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    event_service: EventService = Depends(get_event_service),
):
    """
    List events for the authenticated tenant.
    Optional filters:
    - status_filter: filter by event status (DRAFT, ACTIVE, PAUSED, ENDED)
    - location: filter by location (partial match, case-insensitive)
    Pagination via offset.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    items, total = event_service.list_events(
        tenant_id=tenant_id,
        status=status_filter,
        location=location,
        page=page,
        page_size=page_size,
    )
    return paginated_response(
        message="Events fetched successfully",
        data=[event_to_dict(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Get single ───────────────────────────────────────────────────────────────

@router.get("/{event_id}", status_code=status.HTTP_200_OK)
def read_event(
    event_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    event_service: EventService = Depends(get_event_service),
):
    """Fetch a single event by ID (tenant-scoped)."""
    db_event = event_service.get_event(event_id)
    if not db_event or db_event.tenant_id != tenant_id:
        _raise_not_found(event_id)

    return success_response(
        message="Event fetched successfully",
        data=event_to_dict(db_event),
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_new_event(
    tenant_id: UUID = Depends(get_current_tenant_id),
    name: str = Form(...),
    location: str = Form(...),
    description: Optional[str] = Form(None),
    starts_at: Optional[str] = Form(None),
    ends_at: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    image_path: Optional[str] = Form(None),
    max_participants: int = Form(...),
    status: str = Form(...),
    type: str = Form(...),
    sort_order: Optional[int] = Form(None),
    event_service: EventService = Depends(get_event_service),
):
    """Create a new event for the authenticated tenant. Location is required."""
    try:
        normalized_image_path = _normalize_event_image_path(image_path)
        if image is not None:
            normalized_image_path = _save_image_file(image)

        # Parse optional datetime strings
        from datetime import datetime
        starts_at_dt = None
        if starts_at:
            try:
                starts_at_dt = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))
            except ValueError as e:
                raise ValidationError(f"Invalid starts_at datetime format: {e}")
        ends_at_dt = None
        if ends_at:
            try:
                ends_at_dt = datetime.fromisoformat(ends_at.replace('Z', '+00:00'))
            except ValueError as e:
                raise ValidationError(f"Invalid ends_at datetime format: {e}")

        # Build event data and validate
        event_data = {
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "starts_at": starts_at_dt,
            "ends_at": ends_at_dt,
            "max_participants": max_participants,
            "status": status,
            "type": type,
            "image_path": normalized_image_path,
            "location": location,
            "sort_order": sort_order,
        }
        try:
            event_in = EventCreate(**event_data)  # may raise PydanticValidationError
        except PydanticValidationError as e:
            raise ValidationError(str(e))

        db_event = event_service.create_event(event_in)
    except (ValidationError, PydanticValidationError) as exc:
        _raise_validation(exc)

    return success_response(
        message="Event created successfully",
        data=event_to_dict(db_event),
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.put("/{event_id}", status_code=status.HTTP_200_OK)
async def update_existing_event(
    event_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    name: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    starts_at: Optional[str] = Form(None),
    ends_at: Optional[str] = Form(None),
    max_participants: Optional[int] = Form(None),
    per_user_cap: Optional[int] = Form(None),
    status: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    image_path: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    btn_name: Optional[str] = Form(None),
    sort_order: Optional[int] = Form(None),
    event_service: EventService = Depends(get_event_service),
):
    """Partial update of an event (only supplied fields are changed)."""
    try:
        # Fetch existing event for potential image cleanup and ownership check
        old_event = event_service.get_event(event_id)
        if old_event is None:
            _raise_not_found(event_id)
        if old_event.tenant_id != tenant_id:
            _raise_not_found(event_id)

        # Initialize image path tracker for cleanup on failure
        new_image_path = None

        # Collect non-image updates
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if type is not None:
            update_data["type"] = type
        if max_participants is not None:
            update_data["max_participants"] = max_participants
        if per_user_cap is not None:
            update_data["per_user_cap"] = per_user_cap
        if status is not None:
            update_data["status"] = status
        if location is not None:
            update_data["location"] = location
        if description is not None:
            update_data["description"] = description
        if btn_name is not None:
            update_data["btn_name"] = btn_name
        if sort_order is not None:
            update_data["sort_order"] = sort_order
        if image_path is not None:
            update_data["image_path"] = _normalize_event_image_path(image_path)

        # Handle datetime fields
        from datetime import datetime
        if starts_at is not None:
            try:
                update_data["starts_at"] = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))
            except ValueError as e:
                raise ValidationError(f"Invalid starts_at datetime format: {e}")
        if ends_at is not None:
            try:
                update_data["ends_at"] = datetime.fromisoformat(ends_at.replace('Z', '+00:00'))
            except ValueError as e:
                raise ValidationError(f"Invalid ends_at datetime format: {e}")

        # Validate non-image fields before potentially saving image
        if update_data:
            try:
                EventUpdate(**update_data)  # may raise PydanticValidationError
            except PydanticValidationError as e:
                raise ValidationError(str(e))

        # Handle image upload (after validating other fields)
        if image is not None:
            new_image_path = _save_image_file(image)
            update_data["image_path"] = new_image_path

        if not update_data:
            # Nothing to change — return existing
            return success_response(
                message="Event updated successfully",
                data=event_to_dict(old_event),
            )

        try:
            event_in = EventUpdate(**update_data)
            db_event = event_service.update_event(event_id, event_in)
        except Exception:
            # Clean up newly saved image on any failure
            if new_image_path:
                _delete_image_file(new_image_path)
            raise

        # Delete old image if it was replaced (only on success)
        if new_image_path and old_event.image_path and old_event.image_path != new_image_path:
            _delete_image_file(old_event.image_path)

    except NotFoundError:
        # Ensure cleanup if image was saved before NotFound occurred
        if new_image_path:
            _delete_image_file(new_image_path)
        _raise_not_found(event_id)
    except (ValidationError, PydanticValidationError) as exc:
        # Ensure cleanup if image was saved before validation error
        if new_image_path:
            _delete_image_file(new_image_path)
        _raise_validation(exc)

    return success_response(
        message="Event updated successfully",
        data=event_to_dict(db_event),
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{event_id}", status_code=status.HTTP_200_OK)
def delete_existing_event(
    event_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    event_service: EventService = Depends(get_event_service),
):
    """Delete an event by ID (tenant-scoped)."""
    try:
        # Verify ownership before deletion
        old_event = event_service.get_event(event_id)
        if old_event is None or old_event.tenant_id != tenant_id:
            _raise_not_found(event_id)

        db_event = event_service.delete_event(event_id)
        # Delete associated image if exists
        if db_event.image_path:
            _delete_image_file(db_event.image_path)
    except NotFoundError:
        _raise_not_found(event_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Event deleted successfully",
        data=event_to_dict(db_event),
    )
