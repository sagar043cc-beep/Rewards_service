import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.badges import Badge
from app.schemas.badges import BadgeCreate, BadgeUpdate, BadgeOut
from app.service.badges import (
    get_badges,
    get_badge,
    create_badge,
    update_badge,
    delete_badge,
    NotFoundError,
    ValidationError,
)
from app.utils.response import success_response, error_response, paginated_response

router = APIRouter(prefix="/badges", tags=["Badges"])
logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _badge_to_dict(b: Badge) -> dict:
    return {
        "id": str(b.id),
        "name": b.name,
        "icon_url": b.icon_url,
        "tenant_id": str(b.tenant_id) if b.tenant_id else None,
    }


def _raise_not_found(badge_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Badge {badge_id} not found.",
    )


def _raise_validation(exc: ValidationError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK)
def list_badges(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    """List all badges with cursor-safe offset pagination."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    items, total = get_badges(db, page=page, page_size=page_size)
    return paginated_response(
        message="Badges fetched successfully",
        data=[_badge_to_dict(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Get single ───────────────────────────────────────────────────────────────

@router.get("/{badge_id}", status_code=status.HTTP_200_OK)
def read_badge(badge_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single badge by ID."""
    db_badge = get_badge(db, badge_id)
    if not db_badge:
        _raise_not_found(badge_id)  # 404, not a 200 with error body

    return success_response(
        message="Badge fetched successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_new_badge(
    name: str = Form(...),
    icon_url: Optional[str] = Form(None),
    tenant_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
):
    """Create a new badge."""
    try:
        badge_in = BadgeCreate(name=name, icon_url=icon_url, tenant_id=tenant_id)
        db_badge = create_badge(db, badge_in)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge created successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.put("/{badge_id}", status_code=status.HTTP_200_OK)
def update_existing_badge(
    badge_id: UUID,
    name: Optional[str] = Form(None),
    icon_url: Optional[str] = Form(None),
    tenant_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
):
    """Partial update of a badge (only supplied fields are changed)."""
    try:
        badge_in = BadgeUpdate(name=name, icon_url=icon_url, tenant_id=tenant_id)
        db_badge = update_badge(db, badge_id, badge_in)
    except NotFoundError:
        _raise_not_found(badge_id)
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge updated successfully",
        data=_badge_to_dict(db_badge),
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{badge_id}", status_code=status.HTTP_200_OK)
def delete_existing_badge(badge_id: UUID, db: Session = Depends(get_db)):
    """Delete a badge by ID."""
    try:
        db_badge = delete_badge(db, badge_id)
    except NotFoundError:
        _raise_not_found(badge_id)  # was silently returning 200 before
    except ValidationError as exc:
        _raise_validation(exc)

    return success_response(
        message="Badge deleted successfully",
        data=_badge_to_dict(db_badge),
    )