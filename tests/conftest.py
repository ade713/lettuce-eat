import hashlib
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.meals import get_image_storage_service, get_meal_nutrition_ai_service
from app.api.v1.nutrition import get_nutrition_ai_service
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app
from app.schemas.nutrition import ImageStorageMetadata, MealAnalysisResponse, MacroNutrients, NutritionEstimate
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


class FakeImageStorageService:
    """Return deterministic image metadata in tests without writing local files."""

    async def store_image(self, *, image_bytes: bytes, content_type: str) -> ImageStorageMetadata:
        """Pretend to store image bytes and return stable metadata."""

        return ImageStorageMetadata(
            storage_provider="local",
            image_storage_key="meal-images/test.jpg",
            image_content_type=content_type,
            image_size_bytes=len(image_bytes),
            image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        )


@pytest.fixture
def fake_nutrition_ai_service() -> FakeNutritionAIService:
    """Provide the shared fake AI service with legacy and v1 analysis methods."""

    return FakeNutritionAIService()


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Provide an in-memory database session factory for API tests."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield factory

    await engine.dispose()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """Provide a test HTTP client with in-memory database and fake dependencies."""

    get_settings.cache_clear()

    async def override_db_session():
        """Yield database sessions from the in-memory test database."""

        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_nutrition_ai_service] = lambda: FakeNutritionAIService()
    app.dependency_overrides[get_meal_nutrition_ai_service] = lambda: FakeNutritionAIService()
    app.dependency_overrides[get_image_storage_service] = lambda: FakeImageStorageService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    get_settings.cache_clear()
