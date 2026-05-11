import logging
from uuid import UUID
from typing import Tuple, List, Optional

from sqlalchemy import select, func, update as sa_update, delete as sa_delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.rewards import Reward
from app.schemas.rewards import RewardCreate, RewardUpdate, RewardPayload

logger = logging.getLogger(__name__)


# ─── Exceptions ────────────────────────────────────────────────────────────────

class RewardServiceError(Exception):
    """Base for all reward service errors."""


class NotFoundError(RewardServiceError):
    """Raised when a reward cannot be located."""


class ValidationError(RewardServiceError):
    """Raised on constraint violations or invalid input."""


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _safe_expunge(db: Session, obj: Reward) -> Reward:
    """
    Eagerly load all mapped columns before expunging so the returned
    object is safe to use after the session is closed or committed.
    """
    db.refresh(obj)
    db.expunge(obj)
    return obj


def _reward_to_dict(r: Reward) -> dict:
    """Convert Reward ORM object to API response dict."""
    return {
        "id": str(r.id),
        "tenant_id": str(r.tenant_id) if r.tenant_id else None,
        "name": r.name,
        "type": r.type,
        "payload": r.payload,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ─── Queries ────────────────────────────────────────────────────────────────────

def get_rewards(
    db: Session,
    tenant_id: Optional[UUID] = None,
    reward_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Reward], int]:
    """
    Paginated list of rewards with optional filters.
    Uses window function for single-query total count.
    """
    offset = (page - 1) * page_size
    count_col = func.count().over().label("total_count")

    stmt = select(Reward, count_col)

    # Apply filters
    if tenant_id is not None:
        stmt = stmt.where(Reward.tenant_id == tenant_id)
    if reward_type is not None:
        stmt = stmt.where(Reward.type == reward_type.upper())
    if is_active is not None:
        stmt = stmt.where(Reward.is_active == is_active)

    stmt = stmt.order_by(Reward.created_at.desc()).offset(offset).limit(page_size)

    rows = db.execute(stmt).all()

    if not rows:
        return [], 0

    return [row.Reward for row in rows], rows[0].total_count


def get_reward(db: Session, reward_id: UUID) -> Optional[Reward]:
    """Fetch a single reward by primary key."""
    return db.execute(
        select(Reward).where(Reward.id == reward_id)
    ).scalar_one_or_none()


# ─── Create ─────────────────────────────────────────────────────────────────────

def create_reward(db: Session, payload: RewardCreate) -> Reward:
    """Insert a new reward row."""
    db_reward = Reward(**payload.model_dump())
    db.add(db_reward)

    try:
        db.commit()
        db.refresh(db_reward)
    except IntegrityError as exc:
        db.rollback()
        logger.warning("create_reward integrity error: %s", exc.orig)
        raise ValidationError(
            "A reward with this name already exists for this tenant."
        ) from exc

    logger.info("Reward created: id=%s name=%r type=%s", db_reward.id, db_reward.name, db_reward.type)
    return db_reward


# ─── Update ─────────────────────────────────────────────────────────────────────

def update_reward(db: Session, reward_id: UUID, payload: RewardUpdate) -> Reward:
    """
    Partial update using SET-based UPDATE with RETURNING.
    Raises NotFoundError when reward doesn't exist.
    """
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        # Nothing to update — return existing
        db_reward = get_reward(db, reward_id)
        if db_reward is None:
            raise NotFoundError(f"Reward {reward_id} not found.")
        return db_reward

    stmt = (
        sa_update(Reward)
        .where(Reward.id == reward_id)
        .values(**update_data)
        .returning(Reward)
    )

    try:
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            db.rollback()
            raise NotFoundError(f"Reward {reward_id} not found.")

        refreshed = _safe_expunge(db, result)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("update_reward integrity error: %s", exc.orig)
        raise ValidationError("A reward with this name already exists.") from exc

    logger.info("Reward updated: id=%s fields=%s", reward_id, list(update_data.keys()))
    return refreshed


# ─── Delete ─────────────────────────────────────────────────────────────────────

def delete_reward(db: Session, reward_id: UUID) -> Reward:
    """
    Hard delete with RETURNING. Ensures one DB round-trip.
    Raises NotFoundError when reward doesn't exist.
    """
    stmt = (
        sa_delete(Reward)
        .where(Reward.id == reward_id)
        .returning(Reward)
    )

    try:
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            db.rollback()
            raise NotFoundError(f"Reward {reward_id} not found.")

        refreshed = _safe_expunge(db, result)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("delete_reward integrity error: %s", exc.orig)
        raise ValidationError("Reward cannot be deleted — it is still referenced.") from exc

    logger.info("Reward deleted: id=%s", reward_id)
    return refreshed