import base64
import json

from openai import AsyncOpenAI

from app.core.config import Settings
from app.schemas.nutrition import NutritionEstimate


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


class NutritionAIService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def analyze_image(
        self, *, image_bytes: bytes, content_type: str, notes: str | None
    ) -> NutritionEstimate:
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{content_type};base64,{encoded_image}"
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

