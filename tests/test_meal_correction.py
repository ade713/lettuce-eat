import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.schemas.nutrition import (
    MacroEstimate,
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

_FORBIDDEN_CORRECTION_SERVICE_IMPORT_PREFIXES = (
    "fastapi",
    "sqlalchemy",
    "app.api",
    "app.db",
    "app.models",
    "app.services.nutrition_ai",
)


def _clock() -> datetime:
    """Return a stable timestamp for correction history assertions."""

    return datetime(2026, 5, 19, 12, 30, tzinfo=UTC)


def _service() -> MealCorrectionService:
    """Build a correction service with a deterministic test clock."""

    return MealCorrectionService(clock=_clock)


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


def test_correction_service_has_no_endpoint_database_or_ai_dependencies():
    """Verify correction logic stays independent from routes, persistence, and AI calls."""

    source = Path("app/services/meal_correction.py").read_text()
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not {
        module
        for module in imported_modules
        if module.startswith(_FORBIDDEN_CORRECTION_SERVICE_IMPORT_PREFIXES)
    }


def test_correction_service_returns_correction_response():
    """Verify corrections return updated totals and a history event."""

    analysis = _draft_analysis()
    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="portion_scale",
        value="smaller",
        suggestion_id="suggestion_1",
    )

    result = _service().apply_correction(analysis=analysis, correction=correction)

    assert isinstance(result, MealCorrectionResponse)
    assert result.analysis_id == analysis.analysis_id
    assert result.items[0].id == "item_1"
    assert result.meal_totals.calories == 586
    assert len(result.correction_history) == 1


def test_correction_service_rejects_unknown_item():
    """Verify correction requests must target an item from the draft analysis."""

    correction = MealCorrectionRequest(
        item_id="missing_item", correction_type="portion_scale", value="smaller"
    )

    with pytest.raises(UnknownCorrectionTargetError, match="missing_item"):
        _service().apply_correction(analysis=_draft_analysis(), correction=correction)


def test_correction_service_applies_portion_scale_control():
    """Verify portion controls scale the targeted item macro estimate."""

    correction = MealCorrectionRequest(
        item_id="item_1", correction_type="portion_scale", value="smaller"
    )

    result = _service().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 586
    assert result.items[0].macro_estimate.protein_g == pytest.approx(26.35)
    assert result.items[0].macro_estimate.carbs_g == pytest.approx(62.9)
    assert result.items[0].macro_estimate.fat_g == pytest.approx(19.55)
    assert result.meal_totals.calories == 586
    assert result.meal_totals.protein_g == pytest.approx(26.35)
    assert result.meal_totals.carbs_g == pytest.approx(62.9)
    assert result.meal_totals.fat_g == pytest.approx(19.55)


def test_correction_service_applies_composition_ratio_control():
    """Verify composition controls nudge macros for rice-versus-meat assumptions."""

    correction = MealCorrectionRequest(
        item_id="item_1", correction_type="composition_ratio", value="more_meat"
    )

    result = _service().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 730
    assert result.items[0].macro_estimate.protein_g == 37
    assert result.items[0].macro_estimate.carbs_g == 66
    assert result.items[0].macro_estimate.fat_g == 25


def test_correction_service_applies_oil_level_control():
    """Verify oil controls nudge fat and calories for cooking-fat assumptions."""

    correction = MealCorrectionRequest(item_id="item_1", correction_type="oil_level", value="oily")

    result = _service().apply_correction(
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

    result = _service().apply_correction(
        analysis=_draft_analysis(), correction=correction
    )

    assert result.items[0].macro_estimate.calories == 600
    assert result.items[0].macro_estimate.protein_g == 27
    assert result.items[0].macro_estimate.carbs_g == 64
    assert result.items[0].macro_estimate.fat_g == 20


def test_correction_service_appends_correction_history_event():
    """Verify correction history records the request and resulting totals."""

    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="suggestion_delta",
        value="apply",
        suggestion_id="suggestion_1",
    )

    result = _service().apply_correction(analysis=_draft_analysis(), correction=correction)

    event = result.correction_history[0]
    assert event.item_id == "item_1"
    assert event.correction_type == "suggestion_delta"
    assert event.value == "apply"
    assert event.suggestion_id == "suggestion_1"
    assert event.resulting_meal_totals == result.meal_totals
    assert event.applied_at == _clock()


def test_correction_service_preserves_existing_correction_history():
    """Verify later corrections append a new event with a new timestamp."""

    correction_times = iter(
        [
            datetime(2026, 5, 19, 12, 30, tzinfo=UTC),
            datetime(2026, 5, 19, 12, 31, tzinfo=UTC),
        ]
    )
    service = MealCorrectionService(clock=lambda: next(correction_times))

    first = service.apply_correction(
        analysis=_draft_analysis(),
        correction=MealCorrectionRequest(
            item_id="item_1", correction_type="oil_level", value="oily"
        ),
    )

    second = service.apply_correction(
        analysis=first,
        correction=MealCorrectionRequest(
            item_id="item_1", correction_type="portion_scale", value="larger"
        ),
    )

    assert len(second.correction_history) == 2
    assert second.correction_history[0].correction_type == "oil_level"
    assert second.correction_history[0].applied_at == datetime(2026, 5, 19, 12, 30, tzinfo=UTC)
    assert second.correction_history[1].correction_type == "portion_scale"
    assert second.correction_history[1].applied_at == datetime(2026, 5, 19, 12, 31, tzinfo=UTC)
    assert second.correction_history[1].applied_at != second.correction_history[0].applied_at
    assert second.correction_history[1].resulting_meal_totals == second.meal_totals


def test_correction_service_recalculates_totals_across_multiple_items():
    """Verify meal totals are summed from every item after the correction is applied."""

    analysis = _draft_analysis()
    side_item = analysis.items[0].model_copy(
        update={
            "id": "item_2",
            "macro_estimate": MacroEstimate(
                calories=100, protein_g=10, carbs_g=12, fat_g=4
            ),
        }
    )
    analysis = analysis.model_copy(
        update={
            "items": [analysis.items[0], side_item],
            "meal_totals": MacroEstimate(calories=790, protein_g=41, carbs_g=86, fat_g=27),
        }
    )
    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="suggestion_delta",
        value="apply",
        suggestion_id="suggestion_1",
    )

    result = _service().apply_correction(analysis=analysis, correction=correction)

    assert result.meal_totals.calories == 700
    assert result.meal_totals.protein_g == 37
    assert result.meal_totals.carbs_g == 76
    assert result.meal_totals.fat_g == 24


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
        _service().apply_correction(analysis=_draft_analysis(), correction=correction)


def test_correction_service_rejects_unsupported_correction_type():
    """Verify unknown correction types fail with a correction type error."""

    correction = MealCorrectionRequest(
        item_id="item_1", correction_type="unknown", value="anything"
    )

    with pytest.raises(UnknownCorrectionTypeError):
        _service().apply_correction(analysis=_draft_analysis(), correction=correction)


def test_correction_service_rejects_missing_suggestion():
    """Verify suggestion corrections fail when the suggestion ID is unknown."""

    correction = MealCorrectionRequest(
        item_id="item_1",
        correction_type="suggestion_delta",
        value="apply",
        suggestion_id="missing_suggestion",
    )

    with pytest.raises(UnknownSuggestionError):
        _service().apply_correction(analysis=_draft_analysis(), correction=correction)
