from uuid import UUID

from pydantic import BaseModel, model_validator

from app.utils.gcs import build_signed_url


class GymImageOut(BaseModel):
    id: int | str | UUID
    image: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def attach_image_url(self):
        """Auto-build the image URL whenever this schema is serialized."""
        if self.image:
            self.image_url = build_signed_url(self.image)
        return self
