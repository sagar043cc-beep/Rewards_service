import logging
import uuid
from uuid import UUID
from typing import Tuple, List, Optional
from datetime import datetime

from sqlalchemy import select, func, update as sa_update, delete as sa_delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.events import Event
from app.schemas.events import EventCreate, EventUpdate

logger = logging.getLogger(__name__)


# ─── Exceptions ────────────────────────────────────────────────────────────────

class EventsServiceError(Exception):
    """Base for all events service errors."""


class NotFoundError(EventsServiceError):
    """Raised when an event cannot be located."""


class ValidationError(EventsServiceError):
    """Raised on constraint violations or invalid input."""


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _safe_expunge(db: Session, obj: Event) -> Event:
    """
    Expunge the given ORM object from the session so it can be used
    after the session is closed or committed.
    
    For objects returned via RETURNING from INSERT/UPDATE/DELETE,
    all column values are already populated, so no refresh is needed.
    """
    db.expunge(obj)
    return obj


def _event_to_dict(e: Event) -> dict:
    """Convert Event ORM object to API response dict."""
    image_url = None
    if e.image_path:
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


# ─── Queries ────────────────────────────────────────────────────────────────────

def get_events(
    db: Session,
    tenant_id: Optional[UUID] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Event], int]:
    """
    Paginated list of events with optional filters.
    Uses window function for single-query total count.
    """
    offset = (page - 1) * page_size
    count_col = func.count().over().label("total_count")

    stmt = select(Event, count_col)

    # Apply filters
    if tenant_id is not None:
        stmt = stmt.where(Event.tenant_id == tenant_id)
    if status is not None:
        stmt = stmt.where(Event.status == status)

    # Order by sort_order (ascending, NULLS LAST), then created_at DESC
    stmt = stmt.order_by(
        Event.sort_order.asc().nullslast(),
        Event.created_at.desc()
    ).offset(offset).limit(page_size)

    rows = db.execute(stmt).all()

    if not rows:
        return [], 0

    return [row.Event for row in rows], rows[0].total_count


def get_event(db: Session, event_id: UUID) -> Optional[Event]:
    """Fetch a single event by primary key."""
    return db.execute(
        select(Event).where(Event.id == event_id)
    ).scalar_one_or_none()


# ─── Create ─────────────────────────────────────────────────────────────────────

def create_event(db: Session, payload: EventCreate) -> Event:
    """Insert a new event row."""
    data = payload.model_dump()

    # Generate code if not provided
    if not data.get('code'):
        data['code'] = str(uuid.uuid4().hex[:8])

    db_event = Event(**data)
    db.add(db_event)

    try:
        db.commit()
        db.refresh(db_event)
    except IntegrityError as exc:
        db.rollback()
        logger.warning("create_event integrity error: %s", exc.orig)
        raise ValidationError("An event with this code already exists for this tenant.") from exc

    logger.info("Event created: id=%s code=%r name=%r", db_event.id, db_event.code, db_event.name)
    return db_event


# ─── Update ─────────────────────────────────────────────────────────────────────

def update_event(db: Session, event_id: UUID, payload: EventUpdate) -> Event:
    """
    Partial update using SET-based UPDATE with RETURNING.
    Raises NotFoundError when event doesn't exist.
    """
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        # Nothing to update — return existing
        db_event = get_event(db, event_id)
        if db_event is None:
            raise NotFoundError(f"Event {event_id} not found.")
        return db_event

    stmt = (
        sa_update(Event)
        .where(Event.id == event_id)
        .values(**update_data)
        .returning(Event)
    )

    try:
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            db.rollback()
            raise NotFoundError(f"Event {event_id} not found.")

        refreshed = _safe_expunge(db, result)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("update_event integrity error: %s", exc.orig)
        raise ValidationError("An event with this code already exists.") from exc

    logger.info("Event updated: id=%s fields=%s", event_id, list(update_data.keys()))
    return refreshed


# ─── Delete ─────────────────────────────────────────────────────────────────────

def delete_event(db: Session, event_id: UUID) -> Event:
    """
    Hard delete with RETURNING. Ensures one DB round-trip.
    Raises NotFoundError when event doesn't exist.
    """
    stmt = (
        sa_delete(Event)
        .where(Event.id == event_id)
        .returning(Event)
    )

    try:
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            db.rollback()
            raise NotFoundError(f"Event {event_id} not found.")

        refreshed = _safe_expunge(db, result)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("delete_event integrity error: %s", exc.orig)
        raise ValidationError("Event cannot be deleted — it is still referenced.") from exc

    logger.info("Event deleted: id=%s", event_id)
    return refreshed
