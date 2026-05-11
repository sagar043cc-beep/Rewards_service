from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, root_validator

TriggerType = Literal["SINGLE_TRIGGER", "RULE_BASED"]
EventStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED"]


class EventBase(BaseModel):
    tenant_id: UUID
    code: str = Field(..., min_length=1, max_length=128, strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=256, strip_whitespace=True)
    trigger_type: TriggerType
    starts_at: datetime
    ends_at: datetime
    max_participants: Optional[int] = Field(None, ge=1)
    per_user_cap: int = Field(1, ge=1)
    image_path: Optional[str] = Field(None, max_length=2048)
    url: Optional[str] = Field(None, max_length=2048)
    description: Optional[str] = Field(None, max_length=5000)
    btn_name: Optional[str] = Field(None, max_length=128)

    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return values

    @root_validator(skip_on_failure=True)
    def validate_trigger_type(cls, values):
        trigger = values.get("trigger_type")
        if trigger not in ("SINGLE_TRIGGER", "RULE_BASED"):
            raise ValueError("trigger_type must be SINGLE_TRIGGER or RULE_BASED")
        return values


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256, strip_whitespace=True)
    trigger_type: Optional[TriggerType] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_participants: Optional[int] = Field(None, ge=1)
    per_user_cap: Optional[int] = Field(None, ge=1)
    status: Optional[EventStatus] = None
    image_path: Optional[str] = Field(None, max_length=2048)
    url: Optional[str] = Field(None, max_length=2048)
    description: Optional[str] = Field(None, max_length=5000)
    btn_name: Optional[str] = Field(None, max_length=128)

    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return values


class EventOut(EventBase):
    id: UUID
    status: EventStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
