import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Body, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.rewards import Reward
from app.schemas.rewards import RewardCreate, RewardUpdate, RewardOut
from app.service.rewards import (
    get_rewards,
    get_reward,
    create_reward,
    update_reward,
    delete_reward,
    NotFoundError,
    ValidationError,
)
from app.utils.response import success_response, error_response, paginated_response

router = APIRouter(prefix="/rewards", tags=["Rewards"])
logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────────

def _reward_to_dict(r: Reward) -> dict:
    return {
        "id": str(r.id),
        "tenant_id": str(r.tenant_id) if r.tenant_id else None,
        "name": r.name,
        "type": r.type,
        "payload": r.payload,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _raise_not_found(reward_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Reward {reward_id} not found.",
    )


def _raise_validation(exc: ValidationError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


# ─── List ────────────────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK)
def list_rewards(
    tenant_id: Optional[UUID] = None,
    type: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    """
    List rewards with optional filters:
    - tenant_id: filter by tenant
    - type: filter by reward type (WALLET, PACKAGE, BADGE, XP)
    - is_active: filter by active status
    Pagination via offset.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    items, total = get_rewards(
        db,
        tenant_id=tenant_id,
        reward_type=type,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return paginated_response(
        message="Rewards fetched successfully",
        data=[_reward_to_dict(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Get Single ─────────────────────────────────────────────────────────────────

@router.get("/{reward_id}", status_code=status.HTTP_200_OK)
def read_reward(reward_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single reward by ID."""
    db_reward = get_reward(db, reward_id)
    if not db_reward:
        _raise_not_found(reward_id)

    return success_response(
        message="Reward fetched successfully",
        data=_reward_to_dict(db_reward),
    )


# ─── Create ──────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_new_reward(
    reward_in: RewardCreate = Body(...),
    db: Session = Depends(get_db),
):
    """
    Create a new reward.
    Send JSON body with fields appropriate to the reward type.
    """
    try:
        db_reward = create_reward(db, reward_in)
    except ValidationError as exc:
        _raise_validation(exc)
    return success_response(
        message="Reward created successfully",
        data=_reward_to_dict(db_reward),
    )


# ─── Update ──────────────────────────────────────────────────────────────────────

@router.put("/{reward_id}", status_code=status.HTTP_200_OK)
def update_existing_reward(
    reward_id: UUID,
    reward_in: RewardUpdate = Body(...),
    db: Session = Depends(get_db),
):
    """
    Partial update of a reward — only supplied fields are updated.
    Send JSON body with the fields to update.
    """
    try:
        db_reward = update_reward(db, reward_id, reward_in)
    except NotFoundError:
        _raise_not_found(reward_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Reward updated successfully",
        data=_reward_to_dict(db_reward),
    )


# ─── Delete ──────────────────────────────────────────────────────────────────────

@router.delete("/{reward_id}", status_code=status.HTTP_200_OK)
def delete_existing_reward(reward_id: UUID, db: Session = Depends(get_db)):
    """Delete a reward by ID."""
    try:
        db_reward = delete_reward(db, reward_id)
    except NotFoundError:
        _raise_not_found(reward_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Reward deleted successfully",
        data=_reward_to_dict(db_reward),
    )