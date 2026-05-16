import pytest

from app.schemas.nutrition import (
    MealAnalysisResponse,
    MealCorrectionRequest,
    MealCorrectionResponse,
)
from app.services.meal_correction import MealCorrectionService, UnknownCorrectionTargetError


def _draft_analysis() -> MealAnalysisResponse:
    """Build a deterministic v1 draft analysis for correction service tests."""

    return MealAnalysisResponse.model_validate(
        {
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
                        {
                            "key": "meat_vs_rice",
                            "label": "Rice vs meat ratio",
                            "value": "rice_heavy",
                        },
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
    )


def test_correction_service_accepts_analysis_and_request():
    """Verify the correction service accepts draft analysis data without endpoint wiring."""

    analysis = _draft_analysis()
    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="portion_scale",
        value="smaller",
        suggestion_id="suggestion_1",
    )

    result = MealCorrectionService().apply_correction(analysis=analysis, correction=correction)

    assert isinstance(result, MealCorrectionResponse)
    assert result.analysis_id == analysis.analysis_id
    assert result.items == analysis.items
    assert result.meal_totals == analysis.meal_totals
    assert result.correction_history == []


def test_correction_service_rejects_unknown_item():
    """Verify correction requests must target an item from the draft analysis."""

    correction = MealCorrectionRequest(
        item_id="missing_item", correction_type="portion_scale", value="smaller"
    )

    with pytest.raises(UnknownCorrectionTargetError, match="missing_item"):
        MealCorrectionService().apply_correction(analysis=_draft_analysis(), correction=correction)
