import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from openai import AsyncOpenAI

from app.core.config import Settings
from app.schemas.nutrition import MealAnalysisResponse, NutritionEstimate


@dataclass(frozen=True)
class MealAnalysisAIResult:
    """Bundle the raw provider response with the validated v1 meal analysis."""

    ai_raw_response: dict[str, Any]
    validated_json: MealAnalysisResponse


@runtime_checkable
class _ModelDumpResponse(Protocol):
    """Describe SDK responses that can expose their raw payload as JSON-safe data."""

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        """Return a dictionary representation of the provider response."""

        ...


NUTRITION_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "food_name",
        "portion_description",
        "calories_kcal",
        "macros",
        "ingredients",
        "assumptions",
        "confidence",
    ],
    "properties": {
        "food_name": {"type": "string"},
        "portion_description": {"type": "string"},
        "calories_kcal": {"type": "integer", "minimum": 0},
        "macros": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "protein_g",
                "carbs_g",
                "fat_g",
                "fiber_g",
                "sugar_g",
                "sodium_mg",
            ],
            "properties": {
                "protein_g": {"type": "number", "minimum": 0},
                "carbs_g": {"type": "number", "minimum": 0},
                "fat_g": {"type": "number", "minimum": 0},
                "fiber_g": {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}]},
                "sugar_g": {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}]},
                "sodium_mg": {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}]},
            },
        },
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


MEAL_ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["analysis_id", "version", "items", "meal_totals", "overall_confidence", "suggestions"],
    "properties": {
        "analysis_id": {"type": "string"},
        "version": {"type": "string", "enum": ["v1"]},
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "label",
                    "category",
                    "estimated_grams",
                    "confidence",
                    "macro_estimate",
                    "uncertainty",
                    "assumptions",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "category": {"type": "string"},
                    "estimated_grams": {"type": "number", "minimum": 0},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "macro_estimate": {"$ref": "#/$defs/macro_estimate"},
                    "uncertainty": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["portion_size", "ingredient_composition", "cooking_fat"],
                        "properties": {
                            "portion_size": {"type": "string"},
                            "ingredient_composition": {"type": "string"},
                            "cooking_fat": {"type": "string"},
                        },
                    },
                    "assumptions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["key", "label", "value"],
                            "properties": {
                                "key": {"type": "string"},
                                "label": {"type": "string"},
                                "value": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "meal_totals": {"$ref": "#/$defs/macro_estimate"},
        "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "target_type",
                    "target_id",
                    "kind",
                    "direction",
                    "title",
                    "subtitle",
                    "preview_delta",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "target_type": {"type": "string"},
                    "target_id": {"type": "string"},
                    "kind": {"type": "string"},
                    "direction": {"type": "string"},
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "preview_delta": {"$ref": "#/$defs/macro_delta"},
                },
            },
        },
    },
    "$defs": {
        "macro_estimate": {
            "type": "object",
            "additionalProperties": False,
            "required": ["calories", "protein_g", "carbs_g", "fat_g"],
            "properties": {
                "calories": {"type": "integer", "minimum": 0},
                "protein_g": {"type": "number", "minimum": 0},
                "carbs_g": {"type": "number", "minimum": 0},
                "fat_g": {"type": "number", "minimum": 0},
            },
        },
        "macro_delta": {
            "type": "object",
            "additionalProperties": False,
            "required": ["calories", "protein_g", "carbs_g", "fat_g"],
            "properties": {
                "calories": {"type": "integer"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
            },
        },
    },
}

MEAL_ANALYSIS_SYSTEM_PROMPT = (
    "You estimate nutrition from meal photos for a fast logging workflow. Return only "
    "schema-valid JSON. Detect visible foods or dishes, estimate portions and macros, "
    "state uncertainty and assumptions, and provide quick correction suggestions. "
    "Optimize for fast estimate -> fast correction -> logged meal, not perfect accuracy."
)


def _image_data_url(*, image_bytes: bytes, content_type: str) -> str:
    """Encode uploaded image bytes as a data URL accepted by vision models."""

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{content_type};base64,{encoded_image}"


def parse_meal_analysis_output(output_text: str) -> MealAnalysisResponse:
    """Validate raw provider JSON text against the planned v1 meal analysis schema."""

    return MealAnalysisResponse.model_validate(json.loads(output_text))


def _provider_raw_response(response: Any) -> dict[str, Any]:
    """Convert an AI SDK response into a persistable raw response dictionary."""

    raw_response = response.model_dump(mode="json") if isinstance(response, _ModelDumpResponse) else {}

    output_text = getattr(response, "output_text", None)
    if output_text is not None:
        raw_response.setdefault("output_text", output_text)

    return raw_response


class NutritionAIService:
    """Analyze uploaded meal images with the configured OpenAI vision model."""

    def __init__(self, settings: Settings):
        """Create an OpenAI client using the configured API key and model settings."""

        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def analyze_meal_image(
        self, *, image_bytes: bytes, content_type: str, notes: str | None
    ) -> MealAnalysisAIResult:
        """Send a meal image and return raw plus validated v1 analysis output."""

        data_url = _image_data_url(image_bytes=image_bytes, content_type=content_type)
        notes_text = f"\nAdditional client notes: {notes}" if notes else ""

        response = await self._client.responses.create(
            model=self._settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": MEAL_ANALYSIS_SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Analyze this meal image for the Lettuce Eat v1 response schema. "
                                "Use stable item IDs like item_1 and suggestion IDs like "
                                "suggestion_1. Estimate the visible edible portion."
                                f"{notes_text}"
                            ),
                        },
                        {"type": "input_image", "image_url": data_url, "detail": "high"},
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "meal_analysis_v1",
                    "schema": MEAL_ANALYSIS_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )

        return MealAnalysisAIResult(
            ai_raw_response=_provider_raw_response(response),
            validated_json=parse_meal_analysis_output(response.output_text),
        )

    # Keep this legacy method separate from analyze_meal_image while the v1 meal-flow
    # contract is still being staged. Once the new endpoint replaces this response
    # shape, the duplicated OpenAI request flow can be collapsed around one contract.
    async def analyze_image(
        self, *, image_bytes: bytes, content_type: str, notes: str | None
    ) -> NutritionEstimate:
        """Send an uploaded food image to the AI model and validate the nutrition estimate."""

        data_url = _image_data_url(image_bytes=image_bytes, content_type=content_type)
        notes_text = f"\nAdditional client notes: {notes}" if notes else ""

        response = await self._client.responses.create(
            model=self._settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You estimate nutrition from meal photos. Be conservative, "
                                "state assumptions, and return only schema-valid JSON. "
                                "When portion size is unclear, make a reasonable estimate and "
                                "lower confidence."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Analyze this food or meal image and estimate nutritional "
                                f"values for the visible edible portion.{notes_text}"
                            ),
                        },
                        {"type": "input_image", "image_url": data_url, "detail": "high"},
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "nutrition_estimate",
                    "schema": NUTRITION_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )

        return NutritionEstimate.model_validate(json.loads(response.output_text))
