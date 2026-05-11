import logging
import os
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.events import Event
from app.schemas.events import EventCreate, EventUpdate, EventOut
from app.service.events import (
    get_events,
    get_event,
    create_event,
    update_event,
    delete_event,
    NotFoundError,
    ValidationError,
)
from app.utils.response import success_response, paginated_response

router = APIRouter(prefix="/events", tags=["Events"])
logger = logging.getLogger(__name__)

# Configuration for event image uploads
EVENT_UPLOAD_DIR = os.path.join("static", "events")
os.makedirs(EVENT_UPLOAD_DIR, exist_ok=True)

# Allowed image extensions
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _event_to_dict(e: Event) -> dict:
    """Convert Event ORM object to API response dict."""
    image_url = None
    if e.image_path:
        # If already a full URL, use as-is; otherwise prefix static path
        if e.image_path.startswith(("http://", "https://")):
            image_url = e.image_path
        else:
            image_url = f"/static/{e.image_path}"
    return {
        "id": str(e.id),
        "tenant_id": str(e.tenant_id),
        "code": e.code,
        "name": e.name,
        "type": e.type,
        "starts_at": e.starts_at.isoformat() if e.starts_at else None,
        "ends_at": e.ends_at.isoformat() if e.ends_at else None,
        "max_participants": e.max_participants,
        "per_user_cap": e.per_user_cap,
        "status": e.status,
        "image_url": image_url,
        "url": e.url,
        "description": e.description,
        "btn_name": e.btn_name,
        "sort_order": e.sort_order,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _raise_not_found(event_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Event {event_id} not found.",
    )


def _raise_validation(exc: ValidationError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _save_image_file(upload_file: UploadFile) -> str:
    """
    Validate and save an uploaded image file.
    Returns the relative path (e.g., 'events/<filename>') to store in DB.
    Raises ValidationError on invalid input.
    """
    if not upload_file.content_type.startswith("image/"):
        raise ValidationError("Event image must be an image file.")

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
    relative_path = os.path.join("events", filename).replace("\\", "/")
    full_path = os.path.join(EVENT_UPLOAD_DIR, filename)

    try:
        # Read uploaded file content and write to disk
        content = upload_file.file.read()
        with open(full_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error("Failed to save event image file: %s", e)
        raise ValidationError("Could not save event image file.") from e

    return relative_path


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
    tenant_id: Optional[UUID] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    """
    List events with optional filters:
    - tenant_id: filter by tenant
    - status: filter by event status (DRAFT, ACTIVE, PAUSED, ENDED)
    Pagination via offset.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    items, total = get_events(
        db,
        tenant_id=tenant_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_response(
        message="Events fetched successfully",
        data=[_event_to_dict(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Get single ───────────────────────────────────────────────────────────────

@router.get("/{event_id}", status_code=status.HTTP_200_OK)
def read_event(event_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single event by ID."""
    db_event = get_event(db, event_id)
    if not db_event:
        _raise_not_found(event_id)

    return success_response(
        message="Event fetched successfully",
        data=_event_to_dict(db_event),
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_new_event(
    tenant_id: UUID = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    starts_at: Optional[str] = Form(None),
    ends_at: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    max_participants: int = Form(...),
    status: str = Form(...),
    type: str = Form(...),
    sort_order: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """Create a new event with optional image."""
    saved_image_path = None
    try:
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

        # Build event data without image and validate
        event_data = {
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "starts_at": starts_at_dt,
            "ends_at": ends_at_dt,
            "max_participants": max_participants,
            "status": status,
            "type": type,
            "image_path": None,
            "sort_order": sort_order,
        }
        try:
            event_in = EventCreate(**event_data)  # may raise PydanticValidationError
        except PydanticValidationError as e:
            raise ValidationError(str(e))

        # Save image only after other fields validated
        if image is not None:
            saved_image_path = _save_image_file(image)
            event_in.image_path = saved_image_path

        db_event = create_event(db, event_in)
    except (ValidationError, PydanticValidationError) as exc:
        # Clean up image if it was saved but event creation failed
        if saved_image_path:
            _delete_image_file(saved_image_path)
        _raise_validation(exc)

    return success_response(
        message="Event created successfully",
        data=_event_to_dict(db_event),
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.put("/{event_id}", status_code=status.HTTP_200_OK)
async def update_existing_event(
    event_id: UUID,
    name: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    starts_at: Optional[str] = Form(None),
    ends_at: Optional[str] = Form(None),
    max_participants: Optional[int] = Form(None),
    per_user_cap: Optional[int] = Form(None),
    status: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    btn_name: Optional[str] = Form(None),
    sort_order: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """Partial update of an event (only supplied fields are changed)."""
    try:
        # Fetch existing event for potential image cleanup
        old_event = get_event(db, event_id)
        if old_event is None:
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
        if url is not None:
            update_data["url"] = url
        if description is not None:
            update_data["description"] = description
        if btn_name is not None:
            update_data["btn_name"] = btn_name
        if sort_order is not None:
            update_data["sort_order"] = sort_order

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
                data=_event_to_dict(old_event),
            )

        try:
            event_in = EventUpdate(**update_data)
            db_event = update_event(db, event_id, event_in)
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
        data=_event_to_dict(db_event),
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{event_id}", status_code=status.HTTP_200_OK)
def delete_existing_event(event_id: UUID, db: Session = Depends(get_db)):
    """Delete an event by ID."""
    try:
        db_event = delete_event(db, event_id)
        # Delete associated image if exists
        if db_event.image_path:
            _delete_image_file(db_event.image_path)
    except NotFoundError:
        _raise_not_found(event_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Event deleted successfully",
        data=_event_to_dict(db_event),
    )
