# import logging
# import uuid
# from uuid import UUID
# from typing import Tuple, List, Optional, Dict

# from sqlalchemy import select, func, update as sa_update, delete as sa_delete
# from sqlalchemy.orm import Session
# from sqlalchemy.exc import IntegrityError

# from app.models.events import Event, EventCondition
# from app.schemas.events import EventCreate, EventUpdate

# logger = logging.getLogger(__name__)


# # ─── Exceptions ────────────────────────────────────────────────────────────────

# class EventsServiceError(Exception):
#     """Base for all events service errors."""


# class NotFoundError(EventsServiceError):
#     """Raised when an event cannot be located."""


# class ValidationError(EventsServiceError):
#     """Raised on constraint violations or invalid input."""


# # ─── Event Service Class ────────────────────────────────────────────────────────

# class EventService:
#     """
#     Object-Oriented Service class for Event management.
#     Encapsulates all event-related business logic and database operations.
#     """

#     def __init__(self, db: Session):
#         """
#         Initialize EventService with database session.
        
#         Args:
#             db: SQLAlchemy database session
#         """
#         self.db = db
#         self.logger = logging.getLogger(__name__)

#     def _safe_expunge(self, obj: Event) -> Event:
#         """
#         Expunge the given ORM object from the session.
        
#         Args:
#             obj: Event ORM object to expunge
            
#         Returns:
#             Expunged Event object
#         """
#         self.db.expunge(obj)
#         return obj

#     def list_events(
#         self,
#         tenant_id: Optional[UUID] = None,
#         status: Optional[str] = None,
#         location: Optional[str] = None,
#         page: int = 1,
#         page_size: int = 10,
#     ) -> Tuple[List[Event], int]:
#         """
#         Retrieve a paginated list of events with optional filters.
        
#         Args:
#             tenant_id: Filter by tenant ID
#             status: Filter by event status
#             location: Filter by location (partial match, case-insensitive)
#             page: Page number (1-indexed)
#             page_size: Number of items per page
            
#         Returns:
#             Tuple of (list of Event objects, total count)
#         """
#         offset = (page - 1) * page_size
#         count_col = func.count().over().label("total_count")

#         stmt = select(Event, count_col)

#         # Apply filters
#         if tenant_id is not None:
#             stmt = stmt.where(Event.tenant_id == tenant_id)
#         if status is not None:
#             stmt = stmt.where(Event.status == status)
#         if location is not None:
#             stmt = stmt.where(Event.location.ilike(f"%{location}%"))

#         # Order by sort_order (ascending, NULLS LAST), then created_at DESC
#         stmt = stmt.order_by(
#             Event.sort_order.asc().nullslast(),
#             Event.created_at.desc()
#         ).offset(offset).limit(page_size)

#         rows = self.db.execute(stmt).all()

#         if not rows:
#             return [], 0

#         return [row.Event for row in rows], rows[0].total_count

#     def get_event(self, event_id: UUID) -> Optional[Event]:
#         """
#         Retrieve a single event by ID.
        
#         Args:
#             event_id: UUID of the event to retrieve
            
#         Returns:
#             Event object or None if not found
#         """
#         return self.db.execute(
#             select(Event).where(Event.id == event_id)
#         ).scalar_one_or_none()

#     def get_event_condition(self, event_id: UUID) -> Optional[EventCondition]:
#         """Retrieve a single condition row for an event, if present."""
#         return self.db.execute(
#             select(EventCondition).where(EventCondition.event_id == event_id)
#         ).scalars().first()

#     def get_event_conditions_map(self, event_ids: List[UUID]) -> Dict[UUID, EventCondition]:
#         """Retrieve condition rows mapped by event_id for a batch of events."""
#         if not event_ids:
#             return {}
#         rows = self.db.execute(
#             select(EventCondition).where(EventCondition.event_id.in_(event_ids))
#         ).scalars().all()
#         return {row.event_id: row for row in rows}

#     def create_event(self, payload: EventCreate) -> Event:
#         """
#         Create a new event.
        
#         Args:
#             payload: EventCreate schema with event data
            
#         Returns:
#             Created Event object
            
#         Raises:
#             ValidationError: If event with same code already exists or other constraint violated
#         """
#         data = payload.model_dump()
#         action_type = data.pop("action_type", None)
#         package_ids = data.pop("package_ids", None)
#         qty = data.pop("qty", None)

#         # Generate code if not provided
#         if not data.get('code'):
#             data['code'] = str(uuid.uuid4().hex[:8])

#         print(f"[create_event] data_to_store={data}")

#         db_event = Event(**data)
#         self.db.add(db_event)

#         try:
#             self.db.flush()
#             if db_event.type == "action" and action_type:
#                 filters = None
#                 if action_type == "package_purchase" and package_ids:
#                     filters = {"package_ids": [str(package_id) for package_id in package_ids]}
#                 self.db.add(
#                     EventCondition(
#                         event_id=db_event.id,
#                         action_type=action_type,
#                         filters=filters,
#                         qty=qty,
#                     )
#                 )
#             self.db.commit()
#             self.db.refresh(db_event)
#         except IntegrityError as exc:
#             self.db.rollback()
#             self.logger.warning("create_event integrity error: %s", exc.orig)
#             raise ValidationError("An event with this code already exists for this tenant.") from exc

#         self.logger.info("Event created: id=%s code=%r name=%r", db_event.id, db_event.code, db_event.name)
#         return db_event

#     def update_event(self, event_id: UUID, payload: EventUpdate) -> Event:
#         """
#         Partially update an existing event.
        
#         Args:
#             event_id: UUID of the event to update
#             payload: EventUpdate schema with updated fields
            
#         Returns:
#             Updated Event object
            
#         Raises:
#             NotFoundError: If event doesn't exist
#             ValidationError: If constraint violation occurs
#         """
#         update_data = payload.model_dump(exclude_unset=True)

#         if not update_data:
#             # Nothing to update — return existing
#             db_event = self.get_event(event_id)
#             if db_event is None:
#                 raise NotFoundError(f"Event {event_id} not found.")
#             return db_event

#         stmt = (
#             sa_update(Event)
#             .where(Event.id == event_id)
#             .values(**update_data)
#             .returning(Event)
#         )

#         try:
#             result = self.db.execute(stmt).scalar_one_or_none()
#             if result is None:
#                 self.db.rollback()
#                 raise NotFoundError(f"Event {event_id} not found.")

#             refreshed = self._safe_expunge(result)
#             self.db.commit()
#         except IntegrityError as exc:
#             self.db.rollback()
#             self.logger.warning("update_event integrity error: %s", exc.orig)
#             raise ValidationError("An event with this code already exists.") from exc

#         self.logger.info("Event updated: id=%s fields=%s", event_id, list(update_data.keys()))
#         return refreshed

#     def delete_event(self, event_id: UUID) -> Event:
#         """
#         Hard delete an event from the database.
        
#         Args:
#             event_id: UUID of the event to delete
            
#         Returns:
#             Deleted Event object
            
#         Raises:
#             NotFoundError: If event doesn't exist
#             ValidationError: If event is still referenced
#         """
#         stmt = (
#             sa_delete(Event)
#             .where(Event.id == event_id)
#             .returning(Event)
#         )

#         try:
#             result = self.db.execute(stmt).scalar_one_or_none()
#             if result is None:
#                 self.db.rollback()
#                 raise NotFoundError(f"Event {event_id} not found.")

#             refreshed = self._safe_expunge(result)
#             self.db.commit()
#         except IntegrityError as exc:
#             self.db.rollback()
#             self.logger.warning("delete_event integrity error: %s", exc.orig)
#             raise ValidationError("Event cannot be deleted — it is still referenced.") from exc

#         self.logger.info("Event deleted: id=%s", event_id)
#         return refreshed


# # ─── Backward Compatibility Functions (Deprecated) ──────────────────────────────

# def _get_service(db: Session) -> EventService:
#     """Factory function to create EventService instance."""
#     return EventService(db)


# def get_events(
#     db: Session,
#     tenant_id: Optional[UUID] = None,
#     status: Optional[str] = None,
#     location: Optional[str] = None,
#     page: int = 1,
#     page_size: int = 10,
# ) -> Tuple[List[Event], int]:
#     """Deprecated: Use EventService.list_events() instead."""
#     service = _get_service(db)
#     return service.list_events(tenant_id, status, location, page, page_size)


# def get_event(db: Session, event_id: UUID) -> Optional[Event]:
#     """Deprecated: Use EventService.get_event() instead."""
#     service = _get_service(db)
#     return service.get_event(event_id)


# def create_event(db: Session, payload: EventCreate) -> Event:
#     """Deprecated: Use EventService.create_event() instead."""
#     service = _get_service(db)
#     return service.create_event(payload)


# def update_event(db: Session, event_id: UUID, payload: EventUpdate) -> Event:
#     """Deprecated: Use EventService.update_event() instead."""
#     service = _get_service(db)
#     return service.update_event(event_id, payload)


# def delete_event(db: Session, event_id: UUID) -> Event:
#     """Deprecated: Use EventService.delete_event() instead."""
#     service = _get_service(db)
#     return service.delete_event(event_id)


import logging
import uuid
from uuid import UUID
from typing import Tuple, List, Optional, Dict

from sqlalchemy import select, func, update as sa_update, delete as sa_delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.events import Event, EventCondition, EventReward
from app.models.rewards import Reward
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
    Service class for Event management.
    Encapsulates all event-related business logic and database operations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

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

        Returns:
            Tuple of (list of Event objects, total count)
        """
        offset = (page - 1) * page_size
        count_col = func.count().over().label("total_count")

        stmt = select(Event, count_col)

        if tenant_id is not None:
            stmt = stmt.where(Event.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Event.status == status)
        if location is not None:
            stmt = stmt.where(Event.location.ilike(f"%{location}%"))

        stmt = stmt.order_by(
            Event.sort_order.asc().nullslast(),
            Event.created_at.desc(),
        ).offset(offset).limit(page_size)

        rows = self.db.execute(stmt).all()

        if not rows:
            return [], 0

        return [row.Event for row in rows], rows[0].total_count

    def get_event(self, event_id: UUID) -> Optional[Event]:
        """Retrieve a single event by ID."""
        return self.db.execute(
            select(Event).where(Event.id == event_id)
        ).scalar_one_or_none()

    def get_event_condition(self, event_id: UUID) -> Optional[EventCondition]:
        """Retrieve a single condition row for an event, if present."""
        return self.db.execute(
            select(EventCondition).where(EventCondition.event_id == event_id)
        ).scalars().first()

    def get_event_conditions_map(self, event_ids: List[UUID]) -> Dict[UUID, EventCondition]:
        """Retrieve condition rows mapped by event_id for a batch of events."""
        if not event_ids:
            return {}
        rows = self.db.execute(
            select(EventCondition).where(EventCondition.event_id.in_(event_ids))
        ).scalars().all()
        return {row.event_id: row for row in rows}

    def add_rewards_to_event(self, event_id: UUID, reward_ids: List[UUID], tier: int = 1) -> List[EventReward]:
        """Attach rewards to an event in the event_rewards table."""
        created: List[EventReward] = []
        for reward_id in reward_ids:
            row = EventReward(event_id=event_id, reward_id=reward_id, tier=tier)
            self.db.add(row)
            created.append(row)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("add_rewards_to_event integrity error: %s", exc.orig)
            raise ValidationError("One or more event-reward mappings already exist.") from exc
        return created

    def get_rewards_for_event(self, event_id: UUID) -> List[EventReward]:
        return self.db.execute(
            select(EventReward).where(EventReward.event_id == event_id).order_by(EventReward.tier.asc())
        ).scalars().all()

    def update_event_reward_id(self, event_id: UUID, reward_id: UUID) -> None:
        """Update the reward_id column in the event table."""
        stmt = (
            sa_update(Event)
            .where(Event.id == event_id)
            .values(reward_id=reward_id)
        )
        try:
            self.db.execute(stmt)
            self.db.commit()
            self.logger.info("Event reward_id updated: event_id=%s reward_id=%s", event_id, reward_id)
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("update_event_reward_id integrity error: %s", exc.orig)
            raise ValidationError("Failed to update event reward_id.") from exc

    def get_event_rewards_details_map(self, event_ids: List[UUID]) -> Dict[UUID, List[dict]]:
        """Return mapping of event_id -> reward detail objects."""
        if not event_ids:
            return {}
        rows = self.db.execute(
            select(EventReward, Reward)
            .join(Reward, Reward.id == EventReward.reward_id)
            .where(EventReward.event_id.in_(event_ids))
            .order_by(EventReward.tier.asc(), Reward.created_at.desc())
        ).all()
        data: Dict[UUID, List[dict]] = {event_id: [] for event_id in event_ids}
        for row in rows:
            mapping = {
                "reward_id": str(row.EventReward.reward_id),
                "tier": row.EventReward.tier,
                "name": row.Reward.name,
                "type": row.Reward.type,
                "payload": row.Reward.payload,
                "is_active": row.Reward.is_active,
            }
            data.setdefault(row.EventReward.event_id, []).append(mapping)
        return data

    def count_rewards_by_ids_for_tenant(self, reward_ids: List[UUID], tenant_id: UUID) -> int:
        if not reward_ids:
            return 0
        return self.db.execute(
            select(func.count(Reward.id)).where(
                Reward.id.in_(reward_ids),
                Reward.tenant_id == tenant_id,
            )
        ).scalar_one()

    def create_event(self, payload: EventCreate) -> Event:
        """
        Create a new event.

        Raises:
            ValidationError: If a duplicate code/constraint is violated.
        """
        data = payload.model_dump()
        action_type = data.pop("action_type", None)
        equality = data.pop("equality", None)
        package_ids = data.pop("package_ids", None)
        qty = data.pop("qty", None)

        if not data.get("code"):
            data["code"] = uuid.uuid4().hex[:8]

        db_event = Event(**data)
        self.db.add(db_event)

        try:
            self.db.flush()

            if db_event.type == "action" and action_type:
                filters = None
                if action_type == "package_purchase" and package_ids:
                    filters = {"package_ids": [str(pid) for pid in package_ids]}
                self.db.add(
                    EventCondition(
                        event_id=db_event.id,
                        action_type=action_type,
                        equality=equality,
                        filters=filters,
                        qty=qty,
                    )
                )

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

        Raises:
            NotFoundError: If the event doesn't exist.
            ValidationError: If a constraint violation occurs.
        """
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
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
            # scalar_one_or_none() on a RETURNING clause yields the ORM object
            # directly; no expunge/refresh cycle is needed.
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Event {event_id} not found.")
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("update_event integrity error: %s", exc.orig)
            raise ValidationError("An event with this code already exists.") from exc

        self.logger.info("Event updated: id=%s fields=%s", event_id, list(update_data.keys()))
        return result

    def delete_event(self, event_id: UUID) -> Event:
        """
        Hard-delete an event from the database.

        Raises:
            NotFoundError: If the event doesn't exist.
            ValidationError: If the event is still referenced by another table.
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
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("delete_event integrity error: %s", exc.orig)
            raise ValidationError("Event cannot be deleted — it is still referenced.") from exc

        self.logger.info("Event deleted: id=%s", event_id)
        return result


# ─── Backward-compatibility shims (deprecated) ────────────────────────────────

def _get_service(db: Session) -> EventService:
    return EventService(db)


def get_events(
    db: Session,
    tenant_id: Optional[UUID] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Event], int]:
    """Deprecated: use EventService.list_events() instead."""
    return _get_service(db).list_events(tenant_id, status, location, page, page_size)


def get_event(db: Session, event_id: UUID) -> Optional[Event]:
    """Deprecated: use EventService.get_event() instead."""
    return _get_service(db).get_event(event_id)


def create_event(db: Session, payload: EventCreate) -> Event:
    """Deprecated: use EventService.create_event() instead."""
    return _get_service(db).create_event(payload)


def update_event(db: Session, event_id: UUID, payload: EventUpdate) -> Event:
    """Deprecated: use EventService.update_event() instead."""
    return _get_service(db).update_event(event_id, payload)


def delete_event(db: Session, event_id: UUID) -> Event:
    """Deprecated: use EventService.delete_event() instead."""
    return _get_service(db).delete_event(event_id)
