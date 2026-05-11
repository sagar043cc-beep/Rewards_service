import uuid
from sqlalchemy import Column, String, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)  # 'static' | 'action'
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    max_participants = Column(Integer)
    per_user_cap = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default='DRAFT')
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    image_path = Column(Text)
    url = Column(Text)
    description = Column(Text)
    btn_name = Column(Text)
    sort_order = Column(Integer, nullable=True)  # optional display ordering
  