import uuid
from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String, nullable=False, index=True, unique=True)
    default_currency = Column(String(3), nullable=False, default='INR')
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))