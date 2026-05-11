import logging
from uuid import UUID
from typing import Tuple, List, Optional

from sqlalchemy import select, func, update as sa_update, delete as sa_delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.badges import Badge
from app.schemas.badges import BadgeCreate, BadgeUpdate

logger = logging.getLogger(__name__)


# ─── Exceptions ───────────────────────────────────────────────────────────────

class BadgeServiceError(Exception):
    """Base for all badge service errors."""


class NotFoundError(BadgeServiceError):
    """Raised when a badge cannot be located."""


class ValidationError(BadgeServiceError):
    """Raised on constraint violations or invalid input."""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_expunge(db: Session, obj: Badge) -> Badge:
    """
    Eagerly load all mapped columns before expunging so the returned
    object is safe to use after the session is closed or committed.
    Avoids DetachedInstanceError on later attribute access.
    """
    # Access every column attribute to populate the instance __dict__
    db.refresh(obj)
    db.expunge(obj)
    return obj


# ─── Queries ──────────────────────────────────────────────────────────────────

def get_badges(
    db: Session,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Badge], int]:
    """
    Single-query pagination via window function.
    Returns (items, total_count) in ONE database round trip.
    """
    offset = (page - 1) * page_size
    count_col = func.count().over().label("total_count")

    stmt = (
        select(Badge, count_col)
        .order_by(Badge.name)
        .offset(offset)
        .limit(page_size)
    )
    rows = db.execute(stmt).all()

    if not rows:
        return [], 0

    return [row.Badge for row in rows], rows[0].total_count


def get_badge(db: Session, badge_id: UUID) -> Optional[Badge]:
    """Fetch a single badge by primary key; returns None if absent."""
    return db.execute(
        select(Badge).where(Badge.id == badge_id)
    ).scalar_one_or_none()


def create_badge(db: Session, payload: BadgeCreate) -> Badge:
    """Insert a new badge row and return the persisted instance."""
    db_badge = Badge(**payload.model_dump())
    db.add(db_badge)
    try:
        db.commit()
        db.refresh(db_badge)
    except IntegrityError as exc:
        db.rollback()
        logger.warning("create_badge integrity error: %s", exc.orig)
        # Don't expose raw DB error — translate to a clean message
        raise ValidationError("A badge with that name already exists.") from exc

    logger.info("Badge created: id=%s name=%r", db_badge.id, db_badge.name)
    return db_badge


def update_badge(db: Session, badge_id: UUID, payload: BadgeUpdate) -> Badge:
    """
    SET-based UPDATE with RETURNING — no prior SELECT needed.
    Raises NotFoundError when the badge doesn't exist.
    """
    update_data = payload.model_dump(exclude_unset=True)

    # Nothing to change — fetch and return as-is
    if not update_data:
        db_badge = get_badge(db, badge_id)
        if db_badge is None:
            raise NotFoundError(f"Badge {badge_id} not found.")
        return db_badge

    stmt = (
        sa_update(Badge)
        .where(Badge.id == badge_id)
        .values(**update_data)
        .returning(Badge)
    )
    try:
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            db.rollback()
            raise NotFoundError(f"Badge {badge_id} not found.")

        # Hydrate before commit so the object stays usable after expunge
        refreshed = _safe_expunge(db, result)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("update_badge integrity error: %s", exc.orig)
        raise ValidationError("A badge with that name already exists.") from exc

    logger.info("Badge updated: id=%s fields=%s", badge_id, list(update_data))
    return refreshed


def delete_badge(db: Session, badge_id: UUID) -> Badge:
    """
    DELETE with RETURNING — one round trip.
    Raises NotFoundError when the badge doesn't exist.
    """
    stmt = (
        sa_delete(Badge)
        .where(Badge.id == badge_id)
        .returning(Badge)
    )
    try:
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            db.rollback()
            raise NotFoundError(f"Badge {badge_id} not found.")

        refreshed = _safe_expunge(db, result)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("delete_badge integrity error: %s", exc.orig)
        raise ValidationError("Badge cannot be deleted — it is still referenced.") from exc

    logger.info("Badge deleted: id=%s", badge_id)
    return refreshed