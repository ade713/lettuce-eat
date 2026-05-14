from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.schemas.nutrition import MealAnalysisResponse
from app.services.upload_validation import read_valid_image_upload

router = APIRouter(prefix="/meals", tags=["meals"])



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

    await read_valid_image_upload(image=image, settings=settings)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Meal photo analysis endpoint is not implemented yet.",
    )

