import logging
import uuid
from uuid import UUID
from typing import Tuple, List, Optional

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


# ─── Event Service Class ────────────────────────────────────────────────────────

class EventService:
    """
    Object-Oriented Service class for Event management.
    Encapsulates all event-related business logic and database operations.
    """

    def __init__(self, db: Session):
        """
        Initialize EventService with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.logger = logging.getLogger(__name__)

    def _safe_expunge(self, obj: Event) -> Event:
        """
        Expunge the given ORM object from the session.
        
        Args:
            obj: Event ORM object to expunge
            
        Returns:
            Expunged Event object
        """
        self.db.expunge(obj)
        return obj

    def list_events(
        self,
        tenant_id: Optional[UUID] = None,
        status: Optional[str] = None,
        location: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Event], int]:
        """
        Retrieve a paginated list of events with optional filters.
        
        Args:
            tenant_id: Filter by tenant ID
            status: Filter by event status
            location: Filter by location (partial match, case-insensitive)
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            Tuple of (list of Event objects, total count)
        """
        offset = (page - 1) * page_size
        count_col = func.count().over().label("total_count")

        stmt = select(Event, count_col)

        # Apply filters
        if tenant_id is not None:
            stmt = stmt.where(Event.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Event.status == status)
        if location is not None:
            stmt = stmt.where(Event.location.ilike(f"%{location}%"))

        # Order by sort_order (ascending, NULLS LAST), then created_at DESC
        stmt = stmt.order_by(
            Event.sort_order.asc().nullslast(),
            Event.created_at.desc()
        ).offset(offset).limit(page_size)

        rows = self.db.execute(stmt).all()

        if not rows:
            return [], 0

        return [row.Event for row in rows], rows[0].total_count

    def get_event(self, event_id: UUID) -> Optional[Event]:
        """
        Retrieve a single event by ID.
        
        Args:
            event_id: UUID of the event to retrieve
            
        Returns:
            Event object or None if not found
        """
        return self.db.execute(
            select(Event).where(Event.id == event_id)
        ).scalar_one_or_none()

    def create_event(self, payload: EventCreate) -> Event:
        """
        Create a new event.
        
        Args:
            payload: EventCreate schema with event data
            
        Returns:
            Created Event object
            
        Raises:
            ValidationError: If event with same code already exists or other constraint violated
        """
        data = payload.model_dump()

        # Generate code if not provided
        if not data.get('code'):
            data['code'] = str(uuid.uuid4().hex[:8])

        print(f"[create_event] data_to_store={data}")

        db_event = Event(**data)
        self.db.add(db_event)

        try:
            self.db.commit()
            self.db.refresh(db_event)
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("create_event integrity error: %s", exc.orig)
            raise ValidationError("An event with this code already exists for this tenant.") from exc

        self.logger.info("Event created: id=%s code=%r name=%r", db_event.id, db_event.code, db_event.name)
        return db_event

    def update_event(self, event_id: UUID, payload: EventUpdate) -> Event:
        """
        Partially update an existing event.
        
        Args:
            event_id: UUID of the event to update
            payload: EventUpdate schema with updated fields
            
        Returns:
            Updated Event object
            
        Raises:
            NotFoundError: If event doesn't exist
            ValidationError: If constraint violation occurs
        """
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            # Nothing to update — return existing
            db_event = self.get_event(event_id)
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
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Event {event_id} not found.")

            refreshed = self._safe_expunge(result)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("update_event integrity error: %s", exc.orig)
            raise ValidationError("An event with this code already exists.") from exc

        self.logger.info("Event updated: id=%s fields=%s", event_id, list(update_data.keys()))
        return refreshed

    def delete_event(self, event_id: UUID) -> Event:
        """
        Hard delete an event from the database.
        
        Args:
            event_id: UUID of the event to delete
            
        Returns:
            Deleted Event object
            
        Raises:
            NotFoundError: If event doesn't exist
            ValidationError: If event is still referenced
        """
        stmt = (
            sa_delete(Event)
            .where(Event.id == event_id)
            .returning(Event)
        )

        try:
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Event {event_id} not found.")

            refreshed = self._safe_expunge(result)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("delete_event integrity error: %s", exc.orig)
            raise ValidationError("Event cannot be deleted — it is still referenced.") from exc

        self.logger.info("Event deleted: id=%s", event_id)
        return refreshed


# ─── Backward Compatibility Functions (Deprecated) ──────────────────────────────

def _get_service(db: Session) -> EventService:
    """Factory function to create EventService instance."""
    return EventService(db)


def get_events(
    db: Session,
    tenant_id: Optional[UUID] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Event], int]:
    """Deprecated: Use EventService.list_events() instead."""
    service = _get_service(db)
    return service.list_events(tenant_id, status, location, page, page_size)


def get_event(db: Session, event_id: UUID) -> Optional[Event]:
    """Deprecated: Use EventService.get_event() instead."""
    service = _get_service(db)
    return service.get_event(event_id)


def create_event(db: Session, payload: EventCreate) -> Event:
    """Deprecated: Use EventService.create_event() instead."""
    service = _get_service(db)
    return service.create_event(payload)


def update_event(db: Session, event_id: UUID, payload: EventUpdate) -> Event:
    """Deprecated: Use EventService.update_event() instead."""
    service = _get_service(db)
    return service.update_event(event_id, payload)


def delete_event(db: Session, event_id: UUID) -> Event:
    """Deprecated: Use EventService.delete_event() instead."""
    service = _get_service(db)
    return service.delete_event(event_id)
