import uuid
from sqlalchemy import Column, String, Boolean, Index, text ,DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db import Base



class Reward(Base):
    __tablename__ = "rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    __table_args__ = (
        Index("ix_rewards_tenant_name", "tenant_id", "name", unique=True),
        Index("idx_rewards_active", "tenant_id", "type", postgresql_where=(is_active == True)),
    )