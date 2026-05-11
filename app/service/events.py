from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.models.events import Event
from app.schemas.events import EventCreate, EventUpdate


class EventsServiceError(Exception):
    pass


class NotFoundError(EventsServiceError):
    pass


class ValidationError(EventsServiceError):
    pass


def get_events(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Event).offset(skip).limit(limit).all()

def get_event(db: Session, event_id: UUID):
    return db.query(Event).filter(Event.id == event_id).first()

def create_event(db: Session, event: EventCreate):
    tenant_exists = db.execute(
        text("SELECT 1 FROM tenants WHERE id = :tenant_id"),
        {"tenant_id": event.tenant_id},
    ).scalar()
    if not tenant_exists:
        raise NotFoundError("Tenant not found")

    db_event = Event(**event.dict())
    db.add(db_event)
    try:
        db.commit()
        db.refresh(db_event)
    except IntegrityError as exc:
        db.rollback()
        raise ValidationError(str(exc.orig)) from exc
    return db_event

def update_event(db: Session, event_id: UUID, event: EventUpdate):
    db_event = get_event(db, event_id)
    if db_event:
        update_data = event.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_event, key, value)
        try:
            db.commit()
            db.refresh(db_event)
        except IntegrityError as exc:
            db.rollback()
            raise ValidationError(str(exc.orig)) from exc
    return db_event

def delete_event(db: Session, event_id: UUID):
    db_event = get_event(db, event_id)
    if db_event:
        try:
            db.delete(db_event)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValidationError(str(exc.orig)) from exc
    return db_event
