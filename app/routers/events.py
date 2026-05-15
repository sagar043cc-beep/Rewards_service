
import logging
import os
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.events import event_to_dict
from app.models.rewards import Reward
from app.schemas.events import EventCreate, EventUpdate
from app.service.events import EventService, NotFoundError, ValidationError
from app.service.rewards import RewardService
from app.service.gcs_upload import upload_image_to_gcs
from app.auth import get_current_tenant_id
from app.utils.gcs import normalize_db_image_path
from app.utils.response import success_response, paginated_response

router = APIRouter(prefix="/events", tags=["Events"])
logger = logging.getLogger(__name__)


# ─── Dependency ───────────────────────────────────────────────────────────────

def get_event_service(db: Session = Depends(get_db)) -> EventService:
    return EventService(db)


def get_reward_service(db: Session = Depends(get_db)) -> RewardService:
    return RewardService(db)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _raise_not_found(event_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Event {event_id} not found.",
    )


def _raise_validation(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _reward_to_dict(r: "Reward") -> dict:
    return {
        "id": str(r.id),
        "tenant_id": str(r.tenant_id) if r.tenant_id else None,
        "name": r.name,
        "type": r.type,
        "payload": r.payload,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _event_reward_to_dict(
    event_id: "UUID",
    reward_id: "UUID",
    tier: int,
    reward: Optional["Reward"] = None,
) -> dict:
    result: dict = {
        "event_id": str(event_id),
        "reward_id": str(reward_id),
        "tier": tier,
    }
    if reward is not None:
        result["reward"] = _reward_to_dict(reward)
    return result


def _save_image_file(upload_file: UploadFile) -> str:
    """
    Validate and upload an image file to GCS.
    Returns the stable object path to store in the DB, e.g. 'uploads/filename.png'.
    Raises ValidationError on invalid input or upload failure.
    """
    if not upload_file.content_type or not upload_file.content_type.startswith("image/"):
        raise ValidationError("Event image must be an image file.")

    try:
        result = upload_image_to_gcs(file=upload_file)
        object_path = result.get("object_path")
        if not object_path:
            raise ValidationError("Upload response missing object path.")
        return normalize_db_image_path(object_path) or object_path
    except ValidationError:
        raise
    except Exception as exc:
        logger.error("Failed to upload event image file: %s", exc)
        raise ValidationError("Could not upload event image file.") from exc


def _parse_datetime(value: str, field_name: str) -> datetime:
    """Parse an ISO datetime string, raising ValidationError on failure."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"Invalid {field_name} datetime format: {exc}") from exc


def _delete_image_file(image_path: Optional[str]) -> None:
    """Delete a local event image if it exists (skips external URLs)."""
    if not image_path or image_path.startswith(("http://", "https://")):
        return
    full_path = os.path.join("static", image_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as exc:
        logger.warning("Failed to delete event image file %s: %s", full_path, exc)


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
    - status_filter: DRAFT | ACTIVE | PAUSED | ENDED
    - location: partial match, case-insensitive
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
    event_ids = [item.id for item in items]
    condition_map = event_service.get_event_conditions_map(event_ids)
    rewards_map = event_service.get_event_rewards_details_map(event_ids)
    return paginated_response(
        message="Events fetched successfully",
        data=[event_to_dict(e, condition_map.get(e.id), rewards_map.get(e.id, [])) for e in items],
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
    reward_service: RewardService = Depends(get_reward_service),
):
    """Fetch a single event by ID (tenant-scoped)."""
    db_event = event_service.get_event(event_id)
    if not db_event or db_event.tenant_id != tenant_id:
        _raise_not_found(event_id)

    condition = event_service.get_event_condition(db_event.id)
    rewards_map = event_service.get_event_rewards_details_map([db_event.id])
    event_rewards = rewards_map.get(db_event.id, [])

    # Fallback: if event has direct reward_id but no event_rewards rows,
    # include reward details in response.
    if db_event.reward_id and not event_rewards:
        db_reward = reward_service.get_reward(db_event.reward_id)
        if db_reward and db_reward.tenant_id == tenant_id:
            event_rewards = [{
                "reward_id": str(db_reward.id),
                "tier": 1,
                "name": db_reward.name,
                "type": db_reward.type,
                "payload": db_reward.payload,
                "is_active": db_reward.is_active,
            }]

    return success_response(
        message="Event fetched successfully",
        data=event_to_dict(db_event, condition, event_rewards),
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
    action_type: Optional[str] = Form(None),
    equality: Optional[str] = Form(None),
    package_ids: Optional[str] = Form(None),
    qty: Optional[int] = Form(None),
    logical_group: Optional[int] = Form(None),
    sort_order: Optional[int] = Form(None),
    reward_id: Optional[str] = Form(None),
    event_service: EventService = Depends(get_event_service),
):
    """Create a new event for the authenticated tenant."""
    try:
        # Resolve image path
        normalized_image_path = normalize_db_image_path(image_path) if image_path else None
        if image is not None:
            normalized_image_path = _save_image_file(image)

        # Parse datetime strings
        starts_at_dt = _parse_datetime(starts_at, "starts_at") if starts_at else None
        ends_at_dt = _parse_datetime(ends_at, "ends_at") if ends_at else None

        # Parse comma-separated package_ids
        parsed_package_ids: Optional[list] = None
        if package_ids:
            parsed_package_ids = []
            for raw in package_ids.split(","):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    parsed_package_ids.append(UUID(raw))
                except ValueError:
                    raise ValidationError(f"Invalid package id: {raw!r}")

        # Parse and validate reward_id
        parsed_reward_id: Optional[UUID] = None
        if reward_id:
            try:
                parsed_reward_id = UUID(reward_id)
                # Validate that reward belongs to this tenant
                valid_count = event_service.count_rewards_by_ids_for_tenant([parsed_reward_id], tenant_id)
                if valid_count != 1:
                    raise ValidationError("Reward does not exist or does not belong to this tenant.")
            except ValueError:
                raise ValidationError(f"Invalid reward id: {reward_id!r}")

        try:
            event_in = EventCreate(
                tenant_id=tenant_id,
                name=name,
                description=description,
                starts_at=starts_at_dt,
                ends_at=ends_at_dt,
                max_participants=max_participants,
                status=status,
                type=type,
                action_type=action_type,
                equality=equality,
                package_ids=parsed_package_ids,
                qty=qty if qty is not None else logical_group,
                image_path=normalized_image_path,
                location=location,
                sort_order=sort_order,
                reward_id=parsed_reward_id,
            )
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc

        db_event = event_service.create_event(event_in)

    except (ValidationError, PydanticValidationError) as exc:
        _raise_validation(exc)

    return success_response(
        message="Event created successfully",
        data=event_to_dict(db_event, event_service.get_event_condition(db_event.id)),
    )


@router.post("/{event_id}/rewards", status_code=status.HTTP_201_CREATED)
def add_rewards_to_event(
    event_id: UUID,
    reward_id: Optional[str] = Form(None),
    tier: int = Form(1),
    tenant_id: UUID = Depends(get_current_tenant_id),
    event_service: EventService = Depends(get_event_service),
    reward_service: RewardService = Depends(get_reward_service),
):
    """Add a single reward to an event and store it in the event's reward_id column."""
    try:
        if tier < 1:
            raise ValidationError("tier must be greater than or equal to 1.")

        db_event = event_service.get_event(event_id)
        if not db_event or db_event.tenant_id != tenant_id:
            _raise_not_found(event_id)

        if not reward_id:
            raise ValidationError("Send reward_id.")

        try:
            parsed_reward_id = UUID(reward_id.strip())
        except ValueError:
            raise ValidationError(f"Invalid reward id: {reward_id!r}")

        # Validate that reward belongs to this tenant
        valid_count = event_service.count_rewards_by_ids_for_tenant([parsed_reward_id], tenant_id)
        if valid_count != 1:
            raise ValidationError("Reward does not exist or does not belong to this tenant.")

        # Update the event's reward_id column
        event_service.update_event_reward_id(event_id, parsed_reward_id)
        updated_event = event_service.get_event(event_id)

        # Fetch the full reward for the response payload
        db_reward = reward_service.get_reward(parsed_reward_id)

    except (ValidationError, PydanticValidationError) as exc:
        _raise_validation(exc)

    return success_response(
        message="Reward added to event successfully",
        data=_event_reward_to_dict(
            event_id=updated_event.id,
            reward_id=parsed_reward_id,
            tier=tier,
            reward=db_reward,
        ),
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
    new_image_path: Optional[str] = None

    try:
        # Ownership check
        old_event = event_service.get_event(event_id)
        if old_event is None or old_event.tenant_id != tenant_id:
            _raise_not_found(event_id)

        # Build update dict from supplied fields only
        update_data: dict = {}
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
            update_data["image_path"] = normalize_db_image_path(image_path)
        if starts_at is not None:
            update_data["starts_at"] = _parse_datetime(starts_at, "starts_at")
        if ends_at is not None:
            update_data["ends_at"] = _parse_datetime(ends_at, "ends_at")

        # Validate non-image fields before touching GCS
        if update_data:
            try:
                EventUpdate(**update_data)
            except PydanticValidationError as exc:
                raise ValidationError(str(exc)) from exc

        # Upload image only after other fields are validated
        if image is not None:
            new_image_path = _save_image_file(image)
            update_data["image_path"] = new_image_path

        if not update_data:
            return success_response(
                message="Event updated successfully",
                data=event_to_dict(old_event, event_service.get_event_condition(old_event.id)),
            )

        db_event = event_service.update_event(event_id, EventUpdate(**update_data))

        # Clean up the old image only after a successful DB update
        if new_image_path and old_event.image_path and old_event.image_path != new_image_path:
            _delete_image_file(old_event.image_path)

    except NotFoundError:
        _delete_image_file(new_image_path)
        _raise_not_found(event_id)
    except (ValidationError, PydanticValidationError) as exc:
        _delete_image_file(new_image_path)
        _raise_validation(exc)
    except Exception:
        _delete_image_file(new_image_path)
        raise

    return success_response(
        message="Event updated successfully",
        data=event_to_dict(db_event, event_service.get_event_condition(db_event.id)),
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
        old_event = event_service.get_event(event_id)
        if old_event is None or old_event.tenant_id != tenant_id:
            _raise_not_found(event_id)

        db_event = event_service.delete_event(event_id)
        _delete_image_file(db_event.image_path)

    except NotFoundError:
        _raise_not_found(event_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Event deleted successfully",
        data=event_to_dict(db_event, event_service.get_event_condition(db_event.id)),
    )
