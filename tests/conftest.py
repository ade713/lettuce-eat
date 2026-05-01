from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.nutrition import get_nutrition_ai_service
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app
from app.schemas.nutrition import MacroNutrients, NutritionEstimate


class FakeNutritionAIService:
    async def analyze_image(self, *, image_bytes: bytes, content_type: str, notes: str | None):
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


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_nutrition_ai_service] = lambda: FakeNutritionAIService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    await engine.dispose()
    get_settings.cache_clear()

