import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.badges import Badge
from app.schemas.badges import BadgeCreate, BadgeUpdate

logger = logging.getLogger(__name__)


class BadgeServiceError(Exception):
    """Base for all badge service errors."""


class NotFoundError(BadgeServiceError):
    """Raised when a badge cannot be located."""


class ValidationError(BadgeServiceError):
    """Raised on constraint violations or invalid input."""


class BadgeService:
    """Object-oriented service class for badge management."""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    def _safe_expunge(self, obj: Badge) -> Badge:
        self.db.expunge(obj)
        return obj

    def list_badges(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Badge], int]:
        offset = (page - 1) * page_size
        count_col = func.count().over().label("total_count")

        stmt = (
            select(Badge, count_col)
            .where(Badge.tenant_id == tenant_id)
            .order_by(Badge.name)
            .offset(offset)
            .limit(page_size)
        )
        rows = self.db.execute(stmt).all()

        if not rows:
            return [], 0

        return [row.Badge for row in rows], rows[0].total_count

    def get_badge(self, badge_id: UUID) -> Optional[Badge]:
        return self.db.execute(
            select(Badge).where(Badge.id == badge_id)
        ).scalar_one_or_none()

    def create_badge(self, payload: BadgeCreate, tenant_id: UUID) -> Badge:
        data = payload.model_dump()
        data["tenant_id"] = tenant_id

        db_badge = Badge(**data)
        self.db.add(db_badge)
        try:
            self.db.commit()
            self.db.refresh(db_badge)
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("create_badge integrity error: %s", exc.orig)
            raise ValidationError("A badge with that name already exists.") from exc

        self.logger.info("Badge created: id=%s name=%r", db_badge.id, db_badge.name)
        return db_badge

    def update_badge(self, badge_id: UUID, payload: BadgeUpdate) -> Badge:
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            db_badge = self.get_badge(badge_id)
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
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Badge {badge_id} not found.")

            refreshed = self._safe_expunge(result)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("update_badge integrity error: %s", exc.orig)
            raise ValidationError("A badge with that name already exists.") from exc

        self.logger.info("Badge updated: id=%s fields=%s", badge_id, list(update_data))
        return refreshed

    def delete_badge(self, badge_id: UUID) -> Badge:
        stmt = (
            sa_delete(Badge)
            .where(Badge.id == badge_id)
            .returning(Badge)
        )
        try:
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Badge {badge_id} not found.")

            refreshed = self._safe_expunge(result)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("delete_badge integrity error: %s", exc.orig)
            raise ValidationError("Badge cannot be deleted - it is still referenced.") from exc

        self.logger.info("Badge deleted: id=%s", badge_id)
        return refreshed


def get_badges(
    db: Session,
    tenant_id: UUID,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Badge], int]:
    return BadgeService(db).list_badges(tenant_id, page, page_size)


def get_badge(db: Session, badge_id: UUID) -> Optional[Badge]:
    return BadgeService(db).get_badge(badge_id)


def create_badge(db: Session, payload: BadgeCreate, tenant_id: UUID) -> Badge:
    return BadgeService(db).create_badge(payload, tenant_id)


def update_badge(db: Session, badge_id: UUID, payload: BadgeUpdate) -> Badge:
    return BadgeService(db).update_badge(badge_id, payload)


def delete_badge(db: Session, badge_id: UUID) -> Badge:
    return BadgeService(db).delete_badge(badge_id)
