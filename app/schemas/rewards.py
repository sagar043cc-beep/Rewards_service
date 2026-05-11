from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Literal, Union
from uuid import UUID
from typing_extensions import Annotated

# ─── Payload Schemas ────────────────────────────────────────────────────────────

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

# Union of all valid payload types — discriminated by Reward.type
RewardPayload = Annotated[
    Union[WalletPayload, PackagePayload, BadgePayload, XpPayload],
    Field(discriminator='type')
]

# ─── Base Schema ───────────────────────────────────────────────────────────────

class RewardBase(BaseModel):
    tenant_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=128, strip_whitespace=True)
    type: Literal['WALLET', 'PACKAGE', 'BADGE', 'XP']
    is_active: bool = True
    payload: dict  # Raw dict; validated via root_validator using type

    @field_validator('name')
    @classmethod
    def validate_name_uppercase(cls, v: str) -> str:
        """Names are stored uppercase for consistency."""
        return v.upper().strip()

    @field_validator('type')
    @classmethod
    def validate_type_uppercase(cls, v: str) -> str:
        """Type must be uppercase."""
        return v.upper()

    @field_validator('payload', mode='before')
    @classmethod
    def validate_payload_structure(cls, v: dict, info) -> dict:
        """
        Validate payload structure based on the reward type.
        Uses Pydantic models per-type for strict validation.
        """
        if v is None:
            return v

        reward_type = info.data.get('type')
        if not reward_type:
            raise ValueError('type must be set before payload validation')

        # Map type to payload model
        payload_models = {
            'WALLET': WalletPayload,
            'PACKAGE': PackagePayload,
            'BADGE': BadgePayload,
            'XP': XpPayload,
        }

        model = payload_models.get(reward_type)
        if not model:
            raise ValueError(f'Unsupported reward type: {reward_type}')

        # Validate and return normalized dict
        try:
            validated = model(**v)
            return validated.model_dump()
        except Exception as exc:
            raise ValueError(f'Invalid payload for type {reward_type}: {str(exc)}') from exc


# ─── Create / Update ────────────────────────────────────────────────────────────

class RewardCreate(RewardBase):
    """All fields required except tenant_id (defaults from auth/session)."""
    pass


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
            # Type not being updated; we need the existing type from DB
            # This validator runs before DB fetch, so skip deep validation here
            # The service layer will re-validate with actual type
            return v

        # Same validation logic as RewardBase
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
            return validated.model_dump()
        except Exception as exc:
            raise ValueError(f'Invalid payload for type {reward_type}: {str(exc)}') from exc


# ─── Output Schema ──────────────────────────────────────────────────────────────

class RewardOut(RewardBase):
    id: UUID
    created_at: UUID  # datetime, will be serialized as ISO string

    model_config = ConfigDict(from_attributes=True)