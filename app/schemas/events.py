from pydantic import BaseModel
from pydantic import root_validator
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

TriggerType = Literal["SINGLE_TRIGGER", "RULE_BASED"]
EventStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED"]


class EventBase(BaseModel):
    tenant_id: UUID
    code: str
    name: str
    trigger_type: TriggerType
    starts_at: datetime
    ends_at: datetime
    max_participants: Optional[int] = None
    per_user_cap: int = 1
    image: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    btn_name: Optional[str] = None

class EventCreate(EventBase):
    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return values

class EventUpdate(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_participants: Optional[int] = None
    per_user_cap: Optional[int] = None
    status: Optional[EventStatus] = None
    image: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    btn_name: Optional[str] = None

    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return values

class Event(EventBase):
    id: UUID
    status: EventStatus
    created_at: datetime

    class Config:
        from_attributes = True
