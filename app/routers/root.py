from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "Hello World"}


@router.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Check whether the application can reach the database."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable", "detail": str(e)},
        )