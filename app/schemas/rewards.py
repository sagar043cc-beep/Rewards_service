from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Literal, Union
from typing_extensions import Annotated
from uuid import UUID
from datetime import datetime

# ─── Payload validation models (used in RewardUpdate) ───────────────────────────

class WalletPayload(BaseModel):
    amount: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3, strip_whitespace=True)

class PackagePayload(BaseModel):
    package_id: UUID
    quantity: int = Field(..., gt=0)

class BadgePayload(BaseModel):
    badge_slug: str = Field(..., min_length=1, max_length=128)

class XpPayload(BaseModel):
    points: int = Field(..., gt=0)

# ─── Create Schemas (flat structure per type) ───────────────────────────────────

class RewardInputBase(BaseModel):
    """Common fields for all reward creation requests."""
    name: str = Field(..., min_length=1, max_length=128, strip_whitespace=True)
    is_active: bool = True

    @field_validator('name')
    @classmethod
    def validate_name_uppercase(cls, v: str) -> str:
        return v.upper().strip()

class WalletCreate(RewardInputBase):
    type: Literal['WALLET'] = 'WALLET'
    amount: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3, strip_whitespace=True)

class PackageCreate(RewardInputBase):
    type: Literal['PACKAGE'] = 'PACKAGE'
    package_id: UUID
    quantity: int = Field(..., gt=0)

class BadgeCreate(RewardInputBase):
    type: Literal['BADGE'] = 'BADGE'
    badge_slug: str = Field(..., min_length=1, max_length=128)

class XpCreate(RewardInputBase):
    type: Literal['XP'] = 'XP'
    points: int = Field(..., gt=0)

# Union type for create endpoint (discriminated by 'type')
RewardCreate = Annotated[
    Union[WalletCreate, PackageCreate, BadgeCreate, XpCreate],
    Field(discriminator='type')
]

# ─── Update Schema ───────────────────────────────────────────────────────────────

class RewardUpdate(BaseModel):
    """Partial update — only supplied fields are modified."""
    name: Optional[str] = Field(None, min_length=1, max_length=128, strip_whitespace=True)
    type: Optional[Literal['WALLET', 'PACKAGE', 'BADGE', 'XP']] = None
    is_active: Optional[bool] = None
    payload: Optional[dict] = None

    @field_validator('name')
    @classmethod
    def validate_name_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.upper().strip()

    @field_validator('type')
    @classmethod
    def validate_type_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.upper()

    @field_validator('payload', mode='before')
    @classmethod
    def validate_payload_structure(cls, v: Optional[dict], info) -> Optional[dict]:
        """If payload provided, validate against current or new type."""
        if v is None:
            return v
        reward_type = info.data.get('type')
        if not reward_type:
            return v
        payload_models = {
            'WALLET': WalletPayload,
            'PACKAGE': PackagePayload,
            'BADGE': BadgePayload,
            'XP': XpPayload,
        }
        model = payload_models.get(reward_type)
        if not model:
            raise ValueError(f'Unsupported reward type: {reward_type}')
        try:
            validated = model(**v)
            return validated.model_dump(mode='json')
        except Exception as exc:
            raise ValueError(f'Invalid payload for type {reward_type}: {str(exc)}') from exc

# ─── Output Schema ───────────────────────────────────────────────────────────────

class RewardOut(BaseModel):
    id: UUID
    tenant_id: Optional[UUID] = None
    name: str
    type: str
    payload: dict
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
