from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.schemas.nutrition import MealAnalysisResponse

router = APIRouter(prefix="/meals", tags=["meals"])

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post(
    "/analyze-photo",
    response_model=MealAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_meal_photo(
    image: UploadFile = File(...),
    notes: str | None = Form(default=None, max_length=1000),
    settings: Settings = Depends(get_settings),
) -> MealAnalysisResponse:
    """Validate a meal photo upload before storage, AI, and draft persistence are wired."""

    await _read_valid_image_bytes(image=image, settings=settings)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Meal photo analysis endpoint is not implemented yet.",
    )


async def _read_valid_image_bytes(*, image: UploadFile, settings: Settings) -> bytes:
    """Read uploaded image bytes after applying meal-photo upload constraints."""

    if image.content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload must be a JPEG, PNG, WEBP, or non-animated GIF image.",
        )

    image_bytes = await image.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is empty.")
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds {settings.max_upload_mb} MB limit.",
        )

    return image_bytes
