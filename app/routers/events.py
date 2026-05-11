from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db import get_db
from app.schemas.events import Event as EventSchema, EventCreate, EventUpdate
from app.service.events import (
    get_events,
    get_event,
    create_event,
    update_event,
    delete_event,
    NotFoundError,
    ValidationError,
)

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/", response_model=List[EventSchema])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    events = get_events(db, skip=skip, limit=limit)
    return events

@router.get("/{event_id}", response_model=EventSchema)
def read_event(event_id: UUID, db: Session = Depends(get_db)):
    db_event = get_event(db, event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@router.post("/", response_model=EventSchema)
def create_new_event(event: EventCreate, db: Session = Depends(get_db)):
    try:
        return create_event(db, event)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.put("/{event_id}", response_model=EventSchema)
def update_existing_event(event_id: UUID, event: EventUpdate, db: Session = Depends(get_db)):
    try:
        db_event = update_event(db, event_id, event)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@router.delete("/{event_id}")
def delete_existing_event(event_id: UUID, db: Session = Depends(get_db)):
    try:
        db_event = delete_event(db, event_id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "Event deleted successfully"}
