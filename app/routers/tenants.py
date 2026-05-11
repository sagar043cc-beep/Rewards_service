from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db import get_db
from app.schemas.tenants import Tenant as TenantSchema, TenantCreate, TenantUpdate
from app.service.tenants import (
    get_tenants,
    get_tenant,
    create_tenant,
    update_tenant,
    delete_tenant,
    NotFoundError,
    ValidationError,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.get("/", response_model=List[TenantSchema])
def read_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tenants = get_tenants(db, skip=skip, limit=limit)
    return tenants

@router.get("/{tenant_id}", response_model=TenantSchema)
def read_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    db_tenant = get_tenant(db, tenant_id)
    if db_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant

@router.post("/", response_model=TenantSchema)
def create_new_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    try:
        return create_tenant(db, tenant)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.put("/{tenant_id}", response_model=TenantSchema)
def update_existing_tenant(tenant_id: UUID, tenant: TenantUpdate, db: Session = Depends(get_db)):
    try:
        db_tenant = update_tenant(db, tenant_id, tenant)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if db_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant

@router.delete("/{tenant_id}")
def delete_existing_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    try:
        db_tenant = delete_tenant(db, tenant_id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if db_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"message": "Tenant deleted successfully"}