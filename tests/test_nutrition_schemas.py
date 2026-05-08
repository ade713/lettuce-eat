from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.nutrition import (
    CorrectionEvent,
    ImageStorageMetadata,
    LoggedMealResponse,
    MacroEstimate,
    MealAnalysisResponse,
    MealCorrectionRequest,
    MealCorrectionResponse,
    MealDatasetMetadata,
)


def _analysis_payload() -> dict:
    """Return a complete v1 analysis payload matching the planned client contract."""

    return {
        "analysis_id": "analysis_123",
        "version": "v1",
        "items": [
            {
                "id": "item_1",
                "label": "beef pelau",
                "category": "composite_dish",
                "estimated_grams": 420,
                "confidence": 0.72,
                "macro_estimate": {
                    "calories": 690,
                    "protein_g": 31,
                    "carbs_g": 74,
                    "fat_g": 23,
                },
                "uncertainty": {
                    "portion_size": "medium",
                    "ingredient_composition": "high",
                    "cooking_fat": "high",
                },
                "assumptions": [
                    {"key": "portion_size", "label": "Portion size", "value": "medium"},
                    {"key": "meat_vs_rice", "label": "Rice vs meat ratio", "value": "rice_heavy"},
                    {"key": "oil_level", "label": "Oil level", "value": "normal"},
                ],
            }
        ],
        "meal_totals": {"calories": 690, "protein_g": 31, "carbs_g": 74, "fat_g": 23},
        "overall_confidence": 0.72,
        "suggestions": [
            {
                "id": "suggestion_1",
                "target_type": "item",
                "target_id": "item_1",
                "kind": "nudge_portion",
                "direction": "lower",
                "title": "Portion may be a bit high",
                "subtitle": "Try a slightly smaller serving",
                "preview_delta": {
                    "calories": -90,
                    "protein_g": -4,
                    "carbs_g": -10,
                    "fat_g": -3,
                },
            }
        ],
    }


def _correction_event() -> CorrectionEvent:
    """Build a correction event used by correction, dataset, and logged meal tests."""

    return CorrectionEvent(
        item_id="item_1",
        correction_type="portion_scale",
        value="smaller",
        suggestion_id="suggestion_1",
        resulting_meal_totals=MacroEstimate(calories=600, protein_g=27, carbs_g=64, fat_g=20),
        applied_at=datetime(2026, 5, 8, tzinfo=UTC),
    )


def test_meal_analysis_response_accepts_contract_payload():
    """Validate the planned v1 analysis response schema accepts the contract example."""

    analysis = MealAnalysisResponse.model_validate(_analysis_payload())

    assert analysis.analysis_id == "analysis_123"
    assert analysis.version == "v1"
    assert analysis.items[0].id == "item_1"
    assert analysis.items[0].macro_estimate.calories == 690
    assert analysis.meal_totals.protein_g == 31
    assert analysis.suggestions[0].preview_delta.calories == -90


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("overall_confidence",), 1.5),
        (("items", 0, "confidence"), -0.1),
        (("items", 0, "estimated_grams"), -1),
        (("items", 0, "macro_estimate", "calories"), -10),
    ],
)
def test_meal_analysis_response_rejects_invalid_ranges(path, value):
    """Validate confidence, gram, and macro fields reject impossible values."""

    payload = _analysis_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        MealAnalysisResponse.model_validate(payload)


def test_meal_analysis_response_requires_v1_version():
    """Validate the analysis response is pinned to the MVP v1 contract version."""

    payload = _analysis_payload()
    payload["version"] = "v2"

    with pytest.raises(ValidationError):
        MealAnalysisResponse.model_validate(payload)


def test_meal_correction_request_accepts_item_and_suggestion_targets():
    """Validate future correction requests can target an item and optional suggestion."""

    request = MealCorrectionRequest(
        item_id="item_1",
        correction_type="portion_scale",
        value="smaller",
        suggestion_id="suggestion_1",
    )

    assert request.item_id == "item_1"
    assert request.value == "smaller"


def test_meal_correction_response_extends_analysis_with_history():
    """Validate correction responses reuse the analysis contract plus correction history."""

    response = MealCorrectionResponse.model_validate(
        _analysis_payload() | {"correction_history": [_correction_event().model_dump()]}
    )

    assert response.items[0].id == "item_1"
    assert response.correction_history[0].resulting_meal_totals.calories == 600


def test_dataset_metadata_captures_image_ai_json_and_corrections():
    """Validate dataset metadata keeps the artifacts needed for future evaluation."""

    metadata = MealDatasetMetadata(
        image=ImageStorageMetadata(
            storage_provider="local",
            image_storage_key="meal-images/2026/05/image.jpg",
            image_content_type="image/jpeg",
            image_size_bytes=123456,
            image_sha256="abc123",
        ),
        ai_raw_response={"provider": "openai", "raw": {"id": "response_123"}},
        validated_json=MealAnalysisResponse.model_validate(_analysis_payload()),
        correction_history=[_correction_event()],
    )

    assert metadata.image.storage_provider == "local"
    assert metadata.validated_json.analysis_id == "analysis_123"
    assert metadata.correction_history[0].suggestion_id == "suggestion_1"


def test_image_storage_metadata_rejects_negative_size():
    """Validate image metadata cannot describe an impossible negative byte size."""

    with pytest.raises(ValidationError):
        ImageStorageMetadata(
            storage_provider="local",
            image_storage_key="meal-images/2026/05/image.jpg",
            image_content_type="image/jpeg",
            image_size_bytes=-1,
            image_sha256="abc123",
        )


def test_logged_meal_response_links_final_meal_to_dataset():
    """Validate logged meals carry final macros and the dataset linkage."""

    analysis = MealAnalysisResponse.model_validate(_analysis_payload())
    event = _correction_event()
    dataset = MealDatasetMetadata(
        image=ImageStorageMetadata(
            storage_provider="local",
            image_storage_key="meal-images/2026/05/image.jpg",
            image_content_type="image/jpeg",
            image_size_bytes=123456,
            image_sha256="abc123",
        ),
        ai_raw_response={"provider": "openai", "raw": {"id": "response_123"}},
        validated_json=analysis,
        correction_history=[event],
    )

    logged_meal = LoggedMealResponse(
        meal_id="meal_123",
        analysis_id=analysis.analysis_id,
        items=analysis.items,
        final_totals=event.resulting_meal_totals,
        correction_history=[event],
        saved_at=datetime(2026, 5, 8, tzinfo=UTC),
        dataset=dataset,
    )

    assert logged_meal.meal_id == "meal_123"
    assert logged_meal.final_totals.calories == 600
    assert logged_meal.dataset.validated_json.items[0].label == "beef pelau"
