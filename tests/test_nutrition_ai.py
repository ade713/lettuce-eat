import json
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.nutrition_ai import (
    MEAL_ANALYSIS_JSON_SCHEMA,
    MealAnalysisAIResult,
    NutritionAIService,
    parse_meal_analysis_output,
)


def _meal_analysis_output() -> dict[str, Any]:
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


class _FakeResponse:
    """Return object that mimics the OpenAI SDK response shape used by the service."""

    output_text: str = json.dumps(_meal_analysis_output())


class _FakeResponsesClient:
    """Capture OpenAI request arguments while returning deterministic output."""

    def __init__(self) -> None:
        """Initialize a request capture slot for assertions."""

        self.kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _FakeResponse:
        """Store request kwargs and return a fake model response."""

        self.kwargs = kwargs
        return _FakeResponse()


class _FakeOpenAIClient:
    """Expose a responses client compatible with NutritionAIService."""

    def __init__(self) -> None:
        """Create the fake responses API surface."""

        self.responses: _FakeResponsesClient = _FakeResponsesClient()


def test_analyze_meal_image_uses_v1_prompt_schema_and_parser():
    """Validate the internal v1 analysis path requests and parses meal-flow output."""

    service = NutritionAIService(
        Settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model")
    )
    fake_client = _FakeOpenAIClient()
    cast(Any, service)._client = fake_client

    import anyio

    async def run_analysis() -> MealAnalysisAIResult:
        """Call the keyword-only service method from anyio.run."""

        return await service.analyze_meal_image(
            image_bytes=b"fake-image-bytes",
            content_type="image/jpeg",
            notes="Dinner plate",
        )

    result = anyio.run(run_analysis)

    request = fake_client.responses.kwargs
    assert request is not None
    assert result.validated_json.analysis_id == "analysis_123"
    assert result.ai_raw_response["output_text"] == _FakeResponse.output_text
    assert request["model"] == "test-model"
    assert request["text"]["format"]["name"] == "meal_analysis_v1"
    assert request["text"]["format"]["schema"] == MEAL_ANALYSIS_JSON_SCHEMA
    assert "fast logging workflow" in request["input"][0]["content"][0]["text"]
    assert "Dinner plate" in request["input"][1]["content"][0]["text"]
    assert request["input"][1]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")
