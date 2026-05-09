from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.nutrition import get_nutrition_ai_service
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app
from app.schemas.nutrition import MealAnalysisResponse, MacroNutrients, NutritionEstimate
from app.services.nutrition_ai import MealAnalysisAIResult


def _fake_v1_meal_analysis_payload() -> dict:
    """Return deterministic v1 meal analysis data for future meal-flow tests."""

    return {
        "analysis_id": "analysis_test_123",
        "version": "v1",
        "items": [
            {
                "id": "item_1",
                "label": "chicken rice bowl",
                "category": "composite_dish",
                "estimated_grams": 430,
                "confidence": 0.74,
                "macro_estimate": {
                    "calories": 640,
                    "protein_g": 42,
                    "carbs_g": 68,
                    "fat_g": 18,
                },
                "uncertainty": {
                    "portion_size": "medium",
                    "ingredient_composition": "medium",
                    "cooking_fat": "medium",
                },
                "assumptions": [
                    {"key": "portion_size", "label": "Portion size", "value": "medium"},
                    {"key": "protein_ratio", "label": "Chicken amount", "value": "normal"},
                    {"key": "oil_level", "label": "Oil level", "value": "normal"},
                ],
            }
        ],
        "meal_totals": {"calories": 640, "protein_g": 42, "carbs_g": 68, "fat_g": 18},
        "overall_confidence": 0.74,
        "suggestions": [
            {
                "id": "suggestion_1",
                "target_type": "item",
                "target_id": "item_1",
                "kind": "nudge_portion",
                "direction": "lower",
                "title": "Portion may be a little high",
                "subtitle": "Try a slightly smaller bowl serving",
                "preview_delta": {
                    "calories": -80,
                    "protein_g": -5,
                    "carbs_g": -9,
                    "fat_g": -2,
                },
            }
        ],
    }


class FakeNutritionAIService:
    """Return deterministic nutrition estimates in tests without calling OpenAI."""

    async def analyze_image(
        self, *, image_bytes: bytes, content_type: str, notes: str | None
    ) -> NutritionEstimate:
        """Pretend to analyze an image and return a fixed validated estimate."""

        return NutritionEstimate(
            food_name="Chicken rice bowl",
            portion_description="One medium bowl",
            calories_kcal=640,
            macros=MacroNutrients(
                protein_g=42,
                carbs_g=68,
                fat_g=18,
                fiber_g=6,
                sugar_g=7,
                sodium_mg=820,
            ),
            ingredients=["chicken", "rice", "vegetables", "sauce"],
            assumptions=["Estimated from visible portion size."],
            confidence=0.74,
        )

    async def analyze_meal_image(
        self, *, image_bytes: bytes, content_type: str, notes: str | None
    ) -> MealAnalysisAIResult:
        """Pretend to analyze an image and return fixed v1 raw and validated output."""

        payload = _fake_v1_meal_analysis_payload()
        return MealAnalysisAIResult(
            ai_raw_response={"output_text": payload},
            validated_json=MealAnalysisResponse.model_validate(payload),
        )


@pytest.fixture
def fake_nutrition_ai_service() -> FakeNutritionAIService:
    """Provide the shared fake AI service with legacy and v1 analysis methods."""

    return FakeNutritionAIService()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide a test HTTP client with in-memory database and fake AI dependencies."""

    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db_session():
        """Yield database sessions from the in-memory test database."""

        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_nutrition_ai_service] = lambda: FakeNutritionAIService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    await engine.dispose()
    get_settings.cache_clear()
