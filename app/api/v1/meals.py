from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.nutrition import MealAnalysisResponse

router = APIRouter(prefix="/meals", tags=["meals"])


@router.post(
    "/analyze-photo",
    response_model=MealAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_meal_photo(
    image: UploadFile = File(...),
    notes: str | None = Form(default=None, max_length=1000),
) -> MealAnalysisResponse:
    """Declare the meal-flow photo analysis endpoint before wiring storage and AI."""

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Meal photo analysis endpoint is not implemented yet.",
    )
