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
    location = Column(Text)
    description = Column(Text)
    btn_name = Column(Text)
    sort_order = Column(Integer, nullable=True)  # optional display ordering


def event_to_dict(event: "Event") -> dict:
    """Convert Event ORM object to API response dict."""
    image_url = None
    if event.image_path:
        if event.image_path.startswith(("http://", "https://")):
            image_url = event.image_path
        else:
            image_url = f"/static/{event.image_path}"

    return {
        "id": str(event.id),
        "tenant_id": str(event.tenant_id),
        "code": event.code,
        "name": event.name,
        "type": event.type,
        "starts_at": event.starts_at.isoformat() if event.starts_at else None,
        "ends_at": event.ends_at.isoformat() if event.ends_at else None,
        "max_participants": event.max_participants,
        "per_user_cap": event.per_user_cap,
        "status": event.status,
        "image_url": image_url,
        "location": event.location,
        "description": event.description,
        "btn_name": event.btn_name,
        "sort_order": event.sort_order,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
