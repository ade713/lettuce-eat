from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import DraftMealAnalysis


def _analysis_payload() -> dict[str, object]:
    """Build validated v1 analysis JSON used by draft persistence tests."""

    return {
        "analysis_id": "analysis_test_123",
        "version": "v1",
        "items": [{"id": "item_1", "label": "chicken rice bowl"}],
        "meal_totals": {"calories": 640, "protein_g": 42, "carbs_g": 68, "fat_g": 18},
        "overall_confidence": 0.74,
        "suggestions": [],
    }


def _image_metadata_payload() -> dict[str, object]:
    """Build image storage metadata shaped like the future image service result."""

    return {
        "storage_provider": "local",
        "image_storage_key": "meal-images/test.jpg",
        "image_content_type": "image/jpeg",
        "image_size_bytes": 16,
        "image_sha256": "abc123",
    }


def _corrected_totals_payload() -> dict[str, object]:
    """Build current working meal totals after a sample user correction."""

    return {"calories": 600, "protein_g": 39, "carbs_g": 63, "fat_g": 17}


def _correction_history_payload() -> list[dict[str, object]]:
    """Build correction history that explains how current totals were produced."""

    return [
        {
            "item_id": "item_1",
            "correction_type": "portion_scale",
            "value": "smaller",
            "resulting_meal_totals": _corrected_totals_payload(),
        }
    ]


@pytest.fixture
async def draft_session() -> AsyncIterator[AsyncSession]:
    """Yield an in-memory database session with draft meal tables created."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()


async def test_draft_meal_analysis_record_can_be_created_and_retrieved(
    draft_session: AsyncSession,
):
    """Verify the draft meal table exists independently from legacy analyses."""

    draft = DraftMealAnalysis()
    draft_session.add(draft)
    await draft_session.commit()

    retrieved = await draft_session.scalar(
        select(DraftMealAnalysis).where(DraftMealAnalysis.id == draft.id)
    )

    assert retrieved is not None
    assert retrieved.id == draft.id
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


async def test_draft_meal_analysis_persists_stage_three_payloads(
    draft_session: AsyncSession,
):
    """Verify draft storage preserves AI, meal, image, and correction payloads."""

    validated_json = _analysis_payload()
    corrected_totals = _corrected_totals_payload()
    draft = DraftMealAnalysis(
        status="analyzed",
        image_storage_metadata=_image_metadata_payload(),
        validated_json=validated_json,
        detected_items=validated_json["items"],
        original_meal_totals=validated_json["meal_totals"],
        current_meal_totals=corrected_totals,
        correction_history=_correction_history_payload(),
        ai_raw_response={"output_text": validated_json},
    )
    draft_session.add(draft)
    await draft_session.commit()

    retrieved = await draft_session.scalar(
        select(DraftMealAnalysis).where(DraftMealAnalysis.id == draft.id)
    )

    assert retrieved is not None
    assert retrieved.status == "analyzed"
    assert retrieved.image_storage_metadata == _image_metadata_payload()
    assert retrieved.validated_json["analysis_id"] == "analysis_test_123"
    assert retrieved.detected_items == validated_json["items"]
    assert retrieved.original_meal_totals == validated_json["meal_totals"]
    assert retrieved.current_meal_totals == corrected_totals
    assert retrieved.correction_history == _correction_history_payload()
    assert retrieved.ai_raw_response == {"output_text": validated_json}
