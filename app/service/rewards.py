import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.rewards import Reward
from app.schemas.rewards import RewardCreate, RewardUpdate

logger = logging.getLogger(__name__)


class RewardServiceError(Exception):
    """Base for all reward service errors."""


class NotFoundError(RewardServiceError):
    """Raised when a reward cannot be located."""


class ValidationError(RewardServiceError):
    """Raised on constraint violations or invalid input."""


class RewardService:
    """Object-oriented service class for reward management."""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    def _safe_expunge(self, obj: Reward) -> Reward:
        self.db.expunge(obj)
        return obj

    def list_rewards(
        self,
        tenant_id: Optional[UUID] = None,
        reward_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Reward], int]:
        offset = (page - 1) * page_size
        count_col = func.count().over().label("total_count")

        stmt = select(Reward, count_col)

        if tenant_id is not None:
            stmt = stmt.where(Reward.tenant_id == tenant_id)
        if reward_type is not None:
            stmt = stmt.where(Reward.type == reward_type.upper())
        if is_active is not None:
            stmt = stmt.where(Reward.is_active == is_active)

        stmt = stmt.order_by(Reward.created_at.desc()).offset(offset).limit(page_size)
        rows = self.db.execute(stmt).all()

        if not rows:
            return [], 0

        return [row.Reward for row in rows], rows[0].total_count

    def get_reward(self, reward_id: UUID) -> Optional[Reward]:
        return self.db.execute(
            select(Reward).where(Reward.id == reward_id)
        ).scalar_one_or_none()

    def create_reward(self, reward_in: RewardCreate, tenant_id: UUID) -> Reward:
        data = reward_in.model_dump()
        reward_type = data.get("type")
        data["tenant_id"] = tenant_id

        if reward_type == "WALLET":
            payload = {
                "amount": data.pop("amount"),
                "currency": data.pop("currency"),
            }
        elif reward_type == "PACKAGE":
            payload = {
                "package_id": str(data.pop("package_id")),
                "quantity": data.pop("quantity"),
            }
        elif reward_type == "BADGE":
            payload = {
                "badge_slug": data.pop("badge_slug"),
            }
        elif reward_type == "XP":
            payload = {
                "points": data.pop("points"),
            }
        else:
            raise ValidationError(f"Unsupported reward type: {reward_type}")

        data["payload"] = payload

        db_reward = Reward(**data)
        self.db.add(db_reward)

        try:
            self.db.commit()
            self.db.refresh(db_reward)
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("create_reward integrity error: %s", exc.orig)
            raise ValidationError(
                "A reward with this name already exists for this tenant."
            ) from exc

        self.logger.info(
            "Reward created: id=%s name=%r type=%s",
            db_reward.id,
            db_reward.name,
            db_reward.type,
        )
        return db_reward

    def update_reward(self, reward_id: UUID, payload: RewardUpdate) -> Reward:
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            db_reward = self.get_reward(reward_id)
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
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Reward {reward_id} not found.")

            refreshed = self._safe_expunge(result)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("update_reward integrity error: %s", exc.orig)
            raise ValidationError("A reward with this name already exists.") from exc

        self.logger.info("Reward updated: id=%s fields=%s", reward_id, list(update_data.keys()))
        return refreshed

    def delete_reward(self, reward_id: UUID) -> Reward:
        stmt = (
            sa_delete(Reward)
            .where(Reward.id == reward_id)
            .returning(Reward)
        )

        try:
            result = self.db.execute(stmt).scalar_one_or_none()
            if result is None:
                self.db.rollback()
                raise NotFoundError(f"Reward {reward_id} not found.")

            refreshed = self._safe_expunge(result)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self.logger.warning("delete_reward integrity error: %s", exc.orig)
            raise ValidationError("Reward cannot be deleted - it is still referenced.") from exc

        self.logger.info("Reward deleted: id=%s", reward_id)
        return refreshed


# Backward compatibility wrappers

def get_rewards(
    db: Session,
    tenant_id: Optional[UUID] = None,
    reward_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Reward], int]:
    return RewardService(db).list_rewards(tenant_id, reward_type, is_active, page, page_size)


def get_reward(db: Session, reward_id: UUID) -> Optional[Reward]:
    return RewardService(db).get_reward(reward_id)


def create_reward(db: Session, reward_in: RewardCreate, tenant_id: UUID) -> Reward:
    return RewardService(db).create_reward(reward_in, tenant_id)


def update_reward(db: Session, reward_id: UUID, payload: RewardUpdate) -> Reward:
    return RewardService(db).update_reward(reward_id, payload)


def delete_reward(db: Session, reward_id: UUID) -> Reward:
    return RewardService(db).delete_reward(reward_id)
