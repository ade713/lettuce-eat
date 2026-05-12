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
