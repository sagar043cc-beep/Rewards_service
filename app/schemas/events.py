from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, root_validator

EventType = Literal["static", "action"]
EventStatus = Literal["active", "inactive", "draft"]


class EventBase(BaseModel):
    tenant_id: UUID
    code: str
    name: str = Field(..., min_length=1, max_length=256, strip_whitespace=True)
    type: EventType
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_participants: Optional[int] = None
    per_user_cap: int = 1
    status: EventStatus
    image_path: Optional[str] = Field(None, max_length=2048)
    location: str = Field(..., min_length=1, max_length=2048)
    description: Optional[str] = Field(None, max_length=5000)
    btn_name: Optional[str] = Field(None, max_length=128)
    sort_order: Optional[int] = None

    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return values


class EventCreate(BaseModel):
    tenant_id: UUID  # Provided from JWT, not from request body
    name: str = Field(..., min_length=1, max_length=256, strip_whitespace=True)
    description: Optional[str] = Field(None, max_length=5000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_participants: int = Field(..., ge=1)
    status: EventStatus
    type: EventType
    action_type: Optional[str] = Field(None, min_length=1, max_length=128)
    equality: Optional[str] = Field(None, min_length=1, max_length=128)
    package_ids: Optional[list[UUID]] = None
    qty: Optional[int] = Field(None, ge=1)
    image_path: Optional[str] = Field(None, max_length=2048)
    location: str = Field(..., min_length=1, max_length=2048)
    sort_order: Optional[int] = Field(None, ge=0)
    reward_id: Optional[UUID] = None

    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        event_type = values.get("type")
        action_type = values.get("action_type")
        package_ids = values.get("package_ids")
        if event_type == "action":
            if not action_type:
                raise ValueError("action_type is required when type is 'action'")
            if action_type == "package_purchase" and not package_ids:
                raise ValueError("package_ids is required when action_type is 'package_purchase'")
        return values


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256, strip_whitespace=True)
    description: Optional[str] = Field(None, max_length=5000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_participants: Optional[int] = Field(None, ge=1)
    per_user_cap: Optional[int] = Field(None, ge=1)
    status: Optional[EventStatus] = None
    type: Optional[EventType] = None
    image_path: Optional[str] = Field(None, max_length=2048)
    location: Optional[str] = Field(None, max_length=2048)
    btn_name: Optional[str] = Field(None, max_length=128)
    sort_order: Optional[int] = Field(None, ge=0)

    @root_validator(skip_on_failure=True)
    def validate_event_window(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return values


class EventOut(EventBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
