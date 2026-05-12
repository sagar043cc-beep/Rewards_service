from fastapi import APIRouter, File, UploadFile, status

from app.service.gcs_upload import upload_image_to_gcs
from app.utils.response import success_response

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_image(image: UploadFile = File(...)):
    """Upload an image to GCS and return upload metadata."""
    result = upload_image_to_gcs(file=image)
    return success_response(
        message="Image uploaded successfully",
        data=result,
    )
