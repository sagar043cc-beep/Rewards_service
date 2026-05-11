import uuid
from sqlalchemy import Column, String, Index
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base


class Badge(Base):
    __tablename__ = "badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    name = Column(String, nullable=True, index=True)
    icon_url = Column(String, nullable=True)

    __table_args__ = (
        # Composite index for tenant-scoped badge lookups
        Index("ix_badges_tenant_name", "tenant_id", "name"),
    )

