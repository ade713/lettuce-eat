from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import DraftMealAnalysis


async def test_draft_meal_analysis_record_can_be_created_and_retrieved():
    """Verify the draft meal table exists independently from legacy analyses."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        draft = DraftMealAnalysis()
        session.add(draft)
        await session.commit()

        retrieved = await session.scalar(
            select(DraftMealAnalysis).where(DraftMealAnalysis.id == draft.id)
        )

    await engine.dispose()

    assert retrieved is not None
    assert retrieved.id == draft.id
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None

async def test_draft_meal_analysis_persists_stage_three_payloads():
    """Verify draft storage preserves AI, meal, image, and correction payloads."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    validated_json = {
        "analysis_id": "analysis_test_123",
        "version": "v1",
        "items": [{"id": "item_1", "label": "chicken rice bowl"}],
        "meal_totals": {"calories": 640, "protein_g": 42, "carbs_g": 68, "fat_g": 18},
        "overall_confidence": 0.74,
        "suggestions": [],
    }
    detected_items = validated_json["items"]
    original_totals = validated_json["meal_totals"]
    corrected_totals = {"calories": 600, "protein_g": 39, "carbs_g": 63, "fat_g": 17}
    correction_history = [
        {
            "item_id": "item_1",
            "correction_type": "portion_scale",
            "value": "smaller",
            "resulting_meal_totals": corrected_totals,
        }
    ]
    image_metadata = {
        "storage_provider": "local",
        "image_storage_key": "meal-images/test.jpg",
        "image_content_type": "image/jpeg",
        "image_size_bytes": 16,
        "image_sha256": "abc123",
    }
    raw_response = {"output_text": validated_json}

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        draft = DraftMealAnalysis(
            status="analyzed",
            image_storage_metadata=image_metadata,
            validated_json=validated_json,
            detected_items=detected_items,
            original_meal_totals=original_totals,
            current_meal_totals=corrected_totals,
            correction_history=correction_history,
            ai_raw_response=raw_response,
        )
        session.add(draft)
        await session.commit()

        retrieved = await session.scalar(
            select(DraftMealAnalysis).where(DraftMealAnalysis.id == draft.id)
        )

    await engine.dispose()

    assert retrieved is not None
    assert retrieved.status == "analyzed"
    assert retrieved.image_storage_metadata == image_metadata
    assert retrieved.validated_json["analysis_id"] == "analysis_test_123"
    assert retrieved.detected_items == detected_items
    assert retrieved.original_meal_totals == original_totals
    assert retrieved.current_meal_totals == corrected_totals
    assert retrieved.correction_history == correction_history
    assert retrieved.ai_raw_response == raw_response

