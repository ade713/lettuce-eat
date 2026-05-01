from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.nutrition_analysis import NutritionAnalysis
from app.schemas.nutrition import NutritionAnalysisResponse, NutritionEstimate
from app.services.nutrition_ai import NutritionAIService

router = APIRouter(prefix="/nutrition", tags=["nutrition"])

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def get_nutrition_ai_service(settings: Settings = Depends(get_settings)) -> NutritionAIService:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured.",
        )
    return NutritionAIService(settings)


@router.post("/analyze", response_model=NutritionAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_nutrition(
    image: UploadFile = File(...),
    notes: str | None = Form(default=None, max_length=1000),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    nutrition_ai: NutritionAIService = Depends(get_nutrition_ai_service),
) -> NutritionAnalysisResponse:
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
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {settings.max_upload_mb} MB limit.",
        )

    estimate = await nutrition_ai.analyze_image(
        image_bytes=image_bytes, content_type=image.content_type, notes=notes
    )
    record = _record_from_estimate(estimate, image.content_type, len(image_bytes), notes)

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return _response_from_record(record)


@router.get("/analyses/{analysis_id}", response_model=NutritionAnalysisResponse)
async def get_analysis(
    analysis_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> NutritionAnalysisResponse:
    record = await session.scalar(
        select(NutritionAnalysis).where(NutritionAnalysis.id == analysis_id)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")

    return _response_from_record(record)


def _record_from_estimate(
    estimate: NutritionEstimate, content_type: str, image_size_bytes: int, notes: str | None
) -> NutritionAnalysis:
    return NutritionAnalysis(
        image_content_type=content_type,
        image_size_bytes=image_size_bytes,
        notes=notes,
        food_name=estimate.food_name,
        calories_kcal=estimate.calories_kcal,
        protein_g=estimate.macros.protein_g,
        carbs_g=estimate.macros.carbs_g,
        fat_g=estimate.macros.fat_g,
        fiber_g=estimate.macros.fiber_g,
        sugar_g=estimate.macros.sugar_g,
        sodium_mg=estimate.macros.sodium_mg,
        confidence=estimate.confidence,
        raw_result=estimate.model_dump(),
    )


def _response_from_record(record: NutritionAnalysis) -> NutritionAnalysisResponse:
    payload = dict(record.raw_result)
    payload["id"] = record.id
    payload["created_at"] = record.created_at
    return NutritionAnalysisResponse.model_validate(payload)

