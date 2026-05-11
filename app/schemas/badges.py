from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID


class BadgeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, strip_whitespace=True)
    icon_path: Optional[str] = Field(None, max_length=2048)
    tenant_id: Optional[UUID] = None


class BadgeCreate(BadgeBase):
    pass


class BadgeUpdate(BaseModel):
    """All fields optional — only provided fields are applied."""
    name: Optional[str] = Field(None, min_length=1, max_length=128, strip_whitespace=True)
    icon_path: Optional[str] = Field(None, max_length=2048)
    tenant_id: Optional[UUID] = None


class BadgeOut(BadgeBase):
    id: UUID

    # Pydantic v2 — replaces class Config: orm_mode = True
    model_config = ConfigDict(from_attributes=True)