from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DraftMealAnalysis


async def test_analyze_meal_photo_returns_v1_response_and_persists_draft(
    client,
    session_factory: async_sessionmaker[AsyncSession],
):
    """Verify valid uploads store a draft analysis and return canonical v1 JSON."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"notes": "Dinner plate"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == "v1"
    assert body["items"][0]["label"] == "chicken rice bowl"
    assert body["meal_totals"]["calories"] == 640

    async with session_factory() as session:
        draft = await session.scalar(
            select(DraftMealAnalysis).where(DraftMealAnalysis.id == UUID(body["analysis_id"]))
        )

    assert draft is not None
    assert draft.status == "analyzed"
    assert draft.image_storage_key == "meal-images/test.jpg"
    assert draft.image_content_type == "image/jpeg"
    assert draft.image_size_bytes == len(b"fake-image-bytes")
    assert draft.validated_json["analysis_id"] == body["analysis_id"]
    assert draft.detected_items[0]["label"] == "chicken rice bowl"
    assert draft.original_meal_totals == body["meal_totals"]
    assert draft.current_meal_totals == body["meal_totals"]
    assert draft.correction_history == []
    raw_output = draft.ai_raw_response["output_text"]
    assert isinstance(raw_output, dict)
    assert raw_output["analysis_id"] == "analysis_test_123"


async def test_analyze_meal_photo_rejects_non_image_upload(client):
    """Verify unsupported upload content types are rejected before staged work runs."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Upload must be a JPEG, PNG, WEBP, or non-animated GIF image."


async def test_analyze_meal_photo_rejects_empty_image(client):
    """Verify empty image uploads are rejected before storage or AI analysis."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Image is empty."


async def test_analyze_meal_photo_rejects_oversized_image(client):
    """Verify uploads over the configured max size are rejected before storage."""

    oversized_image = b"0" * (10 * 1024 * 1024 + 1)

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", oversized_image, "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Image exceeds 10 MB limit."
