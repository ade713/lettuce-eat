from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


def _json_column(*, default: Callable[[], Any]) -> MappedColumn[Any]:
    """Create a JSON column that uses JSONB when the database is Postgres."""

    return mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=default, nullable=False
    )


class DraftMealAnalysis(Base):
    """Persist a draft meal-analysis record before corrections and final logging."""

    __tablename__ = "draft_meal_analyses"

    # Draft lifecycle
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    # AI and validated analysis payloads
    image_storage_metadata: Mapped[dict[str, object]] = _json_column(default=dict)
    validated_json: Mapped[dict[str, object]] = _json_column(default=dict)
    detected_items: Mapped[list[dict[str, object]]] = _json_column(default=list)
    ai_raw_response: Mapped[dict[str, object]] = _json_column(default=dict)

    # Working correction state
    original_meal_totals: Mapped[dict[str, object]] = _json_column(default=dict)
    current_meal_totals: Mapped[dict[str, object]] = _json_column(default=dict)
    correction_history: Mapped[list[dict[str, object]]] = _json_column(default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
