import os
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import PyJWTError

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Security scheme
security = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_tenant_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UUID:
    """
    FastAPI dependency that extracts and validates the JWT token,
    returning the tenant_id from the token claims as a UUID.

    Raises HTTPException(401) if token is missing or invalid.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required 'tenant_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant_id format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_tenant(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Returns the tenant_id extracted from the JWT token.
    Use this to identify which tenant is making the request.
    """
    return {
        "tenant_id": str(tenant_id),
    }


def decode_jwt(token: str) -> dict:
    """
    Decode a JWT token without raising HTTP exceptions.
    Returns the payload dict or raises PyJWTError on failure.
    Useful for non-request contexts.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def get_tenant_id_from_token(token: str) -> str:
    """
    Extract tenant_id from a JWT token string.
    Returns the tenant_id or raises ValueError on failure.
    """
    try:
        payload = decode_jwt(token)
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise ValueError("Token missing 'tenant_id' claim")
        return tenant_id
    except PyJWTError as e:
        raise ValueError(f"Invalid JWT token: {e}") from e


def decode_jwt(token: str) -> dict:
    """
    Decode a JWT token without raising HTTP exceptions.
    Returns the payload dict or raises PyJWTError on failure.
    Useful for non-request contexts.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def get_tenant_id_from_token(token: str) -> str:
    """
    Extract tenant_id from a JWT token string.
    Returns the tenant_id or raises ValueError on failure.
    """
    try:
        payload = decode_jwt(token)
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise ValueError("Token missing 'tenant_id' claim")
        return tenant_id
    except PyJWTError as e:
        raise ValueError(f"Invalid JWT token: {e}") from e
