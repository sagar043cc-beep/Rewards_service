from pydantic import BaseModel, ConfigDict, Field, AnyHttpUrl, field_validator
from typing import Optional
from uuid import UUID


class BadgeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, strip_whitespace=True)
    icon_url: Optional[str] = Field(None, max_length=2048)
    tenant_id: Optional[UUID] = None

    @field_validator("icon_url")
    @classmethod
    def validate_icon_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("icon_url must be a valid HTTP/HTTPS URL")
        return v


class BadgeCreate(BadgeBase):
    pass


class BadgeUpdate(BaseModel):
    """All fields optional — only provided fields are applied."""
    name: Optional[str] = Field(None, min_length=1, max_length=128, strip_whitespace=True)
    icon_url: Optional[str] = Field(None, max_length=2048)
    tenant_id: Optional[UUID] = None

    @field_validator("icon_url")
    @classmethod
    def validate_icon_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("icon_url must be a valid HTTP/HTTPS URL")
        return v


class BadgeOut(BadgeBase):
    id: UUID

    # Pydantic v2 — replaces class Config: orm_mode = True
    model_config = ConfigDict(from_attributes=True)