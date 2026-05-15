import uuid
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Integer, Text, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db import Base
from app.schemas.image_schema import GymImageOut


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
    location = Column(Text, nullable=False)
    description = Column(Text)
    btn_name = Column(Text)
    sort_order = Column(Integer, nullable=True)  # optional display ordering
    reward_id = Column(UUID(as_uuid=True), ForeignKey("rewards.id"), nullable=True)


class EventCondition(Base):
    __tablename__ = "event_conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String, nullable=False)
    equality = Column(String, nullable=True)
    filters = Column(JSONB, nullable=True)
    qty = Column(Integer, nullable=True)


class EventReward(Base):
    __tablename__ = "event_rewards"

    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    reward_id = Column(UUID(as_uuid=True), ForeignKey("rewards.id"), primary_key=True)
    tier = Column(Integer, nullable=False, default=1, primary_key=True)


def event_to_dict(
    event: "Event",
    condition: Optional["EventCondition"] = None,
    rewards: Optional[List[dict]] = None,
) -> dict:
    """Convert Event ORM object to API response dict."""
    image = GymImageOut(id=str(event.id), image=event.image_path)
    package_ids = None
    action_type = None
    equality = None
    qty = None
    if condition is not None:
        action_type = condition.action_type
        equality = condition.equality
        qty = condition.qty
        if isinstance(condition.filters, dict):
            package_ids = condition.filters.get("package_ids")

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
        "image_url": image.image_url,
        "action_type": action_type,
        "equality": equality,
        "package_ids": package_ids,
        "qty": qty,
        "rewards": rewards or [],
        "location": event.location,
        "description": event.description,
        "btn_name": event.btn_name,
        "sort_order": event.sort_order,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "reward_id": str(event.reward_id) if event.reward_id else None,
    }
