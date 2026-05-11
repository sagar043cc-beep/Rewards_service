"""
Common API response models and helper functions.

Usage in any router:
    from app.utils.response import success_response, error_response, paginated_response

Response shapes
───────────────
Success / Error:
    {
        "success": true | false,
        "message": "...",
        "data": { ... } | [ ... ] | null
    }

Paginated:
    {
        "success": true,
        "message": "...",
        "data": [ ... ],
        "pagination": {
            "total":       100,
            "page":        1,
            "page_size":   10,
            "total_pages": 10,
            "has_next":    true,
            "has_prev":    false
        }
    }
"""

from typing import Any, Optional
from pydantic import BaseModel


# ─── Reusable Pydantic models (use as response_model= in routers) ─────────────

class PaginationMeta(BaseModel):
    """Pagination metadata block — nested inside paginated responses."""
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ApiResponse(BaseModel):
    """Standard single-item or empty response."""
    success: bool
    message: str
    data: Optional[Any] = None


class PaginatedApiResponse(BaseModel):
    """Standard paginated list response."""
    success: bool
    message: str
    data: Optional[Any] = None
    pagination: PaginationMeta


# ─── Helper functions (return plain dicts for fast serialization) ─────────────

def success_response(message: str, data: Any = None) -> dict:
    """Return a successful API response."""
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_response(message: str, data: Any = None) -> dict:
    """Return a failed API response."""
    return {
        "success": False,
        "message": message,
        "data": data,
    }


def paginated_response(
    message: str,
    data: Any,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Return a paginated API response with full pagination metadata."""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }

