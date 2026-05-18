import pytest

from app.schemas.nutrition import (
    MealAnalysisResponse,
    MealCorrectionRequest,
    MealCorrectionResponse,
)
from app.services.meal_correction import (
    MealCorrectionService,
    UnknownCorrectionTargetError,
    UnknownCorrectionTypeError,
    UnknownCorrectionValueError,
    UnknownSuggestionError,
)


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
    assert result.items[0].id == "item_1"
    assert result.meal_totals == analysis.meal_totals
    assert result.correction_history == []


def test_correction_service_rejects_unknown_item():
    """Verify correction requests must target an item from the draft analysis."""

    correction = MealCorrectionRequest(
        item_id="missing_item", correction_type="portion_scale", value="smaller"
    )

    with pytest.raises(UnknownCorrectionTargetError, match="missing_item"):
        MealCorrectionService().apply_correction(analysis=_draft_analysis(), correction=correction)


def test_correction_service_applies_portion_scale_control():
    """Verify portion controls scale the targeted item macro estimate."""

    correction = MealCorrectionRequest(
        item_id="item_1", correction_type="portion_scale", value="smaller"
    )

    result = MealCorrectionService().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 586
    assert result.items[0].macro_estimate.protein_g == pytest.approx(26.35)
    assert result.items[0].macro_estimate.carbs_g == pytest.approx(62.9)
    assert result.items[0].macro_estimate.fat_g == pytest.approx(19.55)
    assert result.meal_totals.calories == 690


def test_correction_service_applies_composition_ratio_control():
    """Verify composition controls nudge macros for rice-versus-meat assumptions."""

    correction = MealCorrectionRequest(
        item_id="item_1", correction_type="composition_ratio", value="more_meat"
    )

    result = MealCorrectionService().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 730
    assert result.items[0].macro_estimate.protein_g == 37
    assert result.items[0].macro_estimate.carbs_g == 66
    assert result.items[0].macro_estimate.fat_g == 25


def test_correction_service_applies_oil_level_control():
    """Verify oil controls nudge fat and calories for cooking-fat assumptions."""

    correction = MealCorrectionRequest(item_id="item_1", correction_type="oil_level", value="oily")

    result = MealCorrectionService().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 760
    assert result.items[0].macro_estimate.protein_g == 31
    assert result.items[0].macro_estimate.carbs_g == 74
    assert result.items[0].macro_estimate.fat_g == 31


def test_correction_service_applies_suggestion_preview_delta():
    """Verify suggestion corrections reuse the AI-provided preview delta."""

    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="suggestion_delta",
        value="apply",
        suggestion_id="suggestion_1",
    )

    result = MealCorrectionService().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 600
    assert result.items[0].macro_estimate.protein_g == 27
    assert result.items[0].macro_estimate.carbs_g == 64
    assert result.items[0].macro_estimate.fat_g == 20


@pytest.mark.parametrize(
    "correction",
    [
        MealCorrectionRequest(item_id="item_1", correction_type="portion_scale", value="tiny"),
        MealCorrectionRequest(
            item_id="item_1", correction_type="composition_ratio", value="all_meat"
        ),
        MealCorrectionRequest(item_id="item_1", correction_type="oil_level", value="swimming"),
    ],
)
def test_correction_service_rejects_unsupported_correction_values(
    correction: MealCorrectionRequest,
):
    """Verify unsupported values fail with a correction value error."""

    with pytest.raises(UnknownCorrectionValueError):
        MealCorrectionService().apply_correction(analysis=_draft_analysis(), correction=correction)


def test_correction_service_rejects_unsupported_correction_type():
    """Verify unknown correction types fail with a correction type error."""

    correction = MealCorrectionRequest(
        item_id="item_1", correction_type="unknown", value="anything"
    )

    with pytest.raises(UnknownCorrectionTypeError):
        MealCorrectionService().apply_correction(analysis=_draft_analysis(), correction=correction)


def test_correction_service_rejects_missing_suggestion():
    """Verify suggestion corrections fail when the suggestion ID is unknown."""

    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="suggestion_delta",
        value="apply",
        suggestion_id="missing_suggestion",
    )

    with pytest.raises(UnknownSuggestionError):
        MealCorrectionService().apply_correction(analysis=_draft_analysis(), correction=correction)
