from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.tenants import Tenant
from app.schemas.tenants import TenantCreate, TenantUpdate

class TenantsServiceError(Exception):
    pass

class NotFoundError(TenantsServiceError):
    pass

class ValidationError(TenantsServiceError):
    pass

def get_tenants(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Tenant).offset(skip).limit(limit).all()

def get_tenant(db: Session, tenant_id: UUID):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

def create_tenant(db: Session, tenant: TenantCreate):
    db_tenant = Tenant(**tenant.dict())
    db.add(db_tenant)
    try:
        db.commit()
        db.refresh(db_tenant)
    except IntegrityError as exc:
        db.rollback()
        raise ValidationError(str(exc.orig)) from exc
    return db_tenant

def update_tenant(db: Session, tenant_id: UUID, tenant: TenantUpdate):
    db_tenant = get_tenant(db, tenant_id)
    if db_tenant:
        update_data = tenant.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_tenant, key, value)
        try:
            db.commit()
            db.refresh(db_tenant)
        except IntegrityError as exc:
            db.rollback()
            raise ValidationError(str(exc.orig)) from exc
    return db_tenant

def delete_tenant(db: Session, tenant_id: UUID):
    db_tenant = get_tenant(db, tenant_id)
    if db_tenant:
        try:
            db.delete(db_tenant)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValidationError(str(exc.orig)) from exc
    return db_tenant