from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.draft_meal_analysis import DraftMealAnalysis
from app.schemas.nutrition import ImageStorageMetadata, MealAnalysisResponse
from app.services.image_storage import ImageStorageService, LocalImageStorageService
from app.services.nutrition_ai import NutritionAIService
from app.services.upload_validation import read_valid_image_upload

router = APIRouter(prefix="/meals", tags=["meals"])


def get_meal_nutrition_ai_service(settings: Settings = Depends(get_settings)) -> NutritionAIService:
    """Build the AI service used by the meal-flow analysis endpoint."""

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured.",
        )
    return NutritionAIService(settings)


def get_image_storage_service(
    settings: Settings = Depends(get_settings),
) -> ImageStorageService:
    """Build the image storage service used before meal photo analysis."""

    return LocalImageStorageService(storage_root=settings.local_storage_root)


@router.post(
    "/analyze-photo",
    response_model=MealAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_meal_photo(
    image: UploadFile = File(...),
    notes: str | None = Form(default=None, max_length=1000),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    image_storage: ImageStorageService = Depends(get_image_storage_service),
    nutrition_ai: NutritionAIService = Depends(get_meal_nutrition_ai_service),
) -> MealAnalysisResponse:
    """Store a meal photo, run AI analysis, persist a draft, and return v1 output."""

    upload = await read_valid_image_upload(image=image, settings=settings)
    image_metadata = await image_storage.store_image(
        image_bytes=upload.image_bytes, content_type=upload.content_type
    )
    ai_result = await nutrition_ai.analyze_meal_image(
        image_bytes=upload.image_bytes, content_type=upload.content_type, notes=notes
    )

    draft_id = uuid4()
    response = ai_result.validated_json.model_copy(update={"analysis_id": str(draft_id)})
    draft = _draft_from_analysis(
        analysis_id=draft_id,
        image_metadata=image_metadata,
        ai_raw_response=ai_result.ai_raw_response,
        analysis=response,
    )

    session.add(draft)
    await session.commit()

    return response


def _draft_from_analysis(
    *,
    analysis_id: UUID,
    image_metadata: ImageStorageMetadata,
    ai_raw_response: dict[str, object],
    analysis: MealAnalysisResponse,
) -> DraftMealAnalysis:
    """Build a draft meal analysis record from image metadata and validated AI output."""

    analysis_payload = analysis.model_dump(mode="json")
    meal_totals = analysis.meal_totals.model_dump(mode="json")
    return DraftMealAnalysis(
        id=analysis_id,
        status="analyzed",
        image_storage_provider=image_metadata.storage_provider,
        image_storage_key=image_metadata.image_storage_key,
        image_content_type=image_metadata.image_content_type,
        image_size_bytes=image_metadata.image_size_bytes,
        image_sha256=image_metadata.image_sha256,
        image_storage_metadata=image_metadata.model_dump(mode="json"),
        validated_json=analysis_payload,
        detected_items=[item.model_dump(mode="json") for item in analysis.items],
        original_meal_totals=meal_totals,
        current_meal_totals=meal_totals,
        correction_history=[],
        ai_raw_response=ai_raw_response,
    )
