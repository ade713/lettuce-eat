import json

import pytest
from pydantic import ValidationError

from app.services.nutrition_ai import parse_meal_analysis_output


def _meal_analysis_output() -> dict:
    """Return a raw provider-style payload for the planned v1 analysis contract."""

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


def test_parse_meal_analysis_output_validates_provider_json_text():
    """Validate raw provider JSON can be parsed into the v1 meal analysis schema."""

    parsed = parse_meal_analysis_output(json.dumps(_meal_analysis_output()))

    assert parsed.analysis_id == "analysis_123"
    assert parsed.items[0].id == "item_1"
    assert parsed.meal_totals.calories == 690
    assert parsed.suggestions[0].preview_delta.calories == -90


def test_parse_meal_analysis_output_rejects_incomplete_provider_json():
    """Validate malformed provider output fails before it can reach endpoint code."""

    payload = _meal_analysis_output()
    del payload["meal_totals"]

    with pytest.raises(ValidationError):
        parse_meal_analysis_output(json.dumps(payload))
