from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class TenantBase(BaseModel):
    slug: str
    default_currency: str = 'INR'

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    slug: Optional[str] = None
    default_currency: Optional[str] = None

class Tenant(TenantBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True