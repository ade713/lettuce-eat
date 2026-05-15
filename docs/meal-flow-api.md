# Meal Flow API Contract

This document defines the target MVP backend contract for Lettuce Eat.

## Objective

Enable `photo -> corrected macros -> logged meal` in under 10 seconds.

The backend optimizes for a fast estimate and fast correction loop. It does not attempt perfect nutrition accuracy in the MVP.

## Flow

1. User captures a meal photo.
2. Backend analyzes the photo with AI.
3. Backend returns a structured v1 analysis response.
4. User applies quick corrections in the client.
5. Backend recalculates macros deterministically.
6. User saves the meal.
7. Backend stores the final logged meal and preserves the dataset trail.

## Existing Endpoint During Migration

Keep `/api/v1/nutrition/analyze` during MVP migration so the existing working endpoint remains available while the new meal flow is added step by step.

## Target Endpoint Sequence

### `POST /api/v1/meals/analyze-photo`

Accepts:

- multipart `image`
- optional `notes`

Returns the v1 client analysis response.

### `PATCH /api/v1/meals/{analysis_id}/corrections`

Accepts user correction values targeting stable item IDs or suggestion IDs from the v1 response.

Returns updated items, meal totals, confidence, and suggestions where appropriate.

### `POST /api/v1/meals/{analysis_id}/log`

Converts the corrected draft analysis into a logged meal.

Returns the logged meal ID and final macros.

## Canonical v1 Analysis Response

```json
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
        "fat_g": 23
      },
      "uncertainty": {
        "portion_size": "medium",
        "ingredient_composition": "high",
        "cooking_fat": "high"
      },
      "assumptions": [
        {
          "key": "portion_size",
          "label": "Portion size",
          "value": "medium"
        },
        {
          "key": "meat_vs_rice",
          "label": "Rice vs meat ratio",
          "value": "rice_heavy"
        },
        {
          "key": "oil_level",
          "label": "Oil level",
          "value": "normal"
        }
      ]
    }
  ],
  "meal_totals": {
    "calories": 690,
    "protein_g": 31,
    "carbs_g": 74,
    "fat_g": 23
  },
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
        "fat_g": -3
      }
    }
  ]
}
```

## Response Rules

- `version` is `v1` for the MVP contract.
- `analysis_id` identifies the persisted draft analysis.
- `items[].id` must remain stable across analyze, correction, and log steps.
- `suggestions[].target_id` must refer to an item ID when `target_type` is `item`.
- `meal_totals` must aggregate across all items.
- `preview_delta` shows the expected macro change before a correction is applied.
- Corrections and logged meal responses should preserve the same macro field names.

## Dataset Record

Each analyzed meal should preserve:

- original image storage metadata
- AI raw response
- validated v1 JSON
- correction history
- final logged meal when saved

## Image Storage Contract

Routes must not write files directly. They should call an image storage service.

MVP local storage result shape:

```json
{
  "storage_provider": "local",
  "image_storage_key": "meal-images/<uuid>.jpg",
  "image_content_type": "image/jpeg",
  "image_size_bytes": 123456,
  "image_sha256": "..."
}
```

Future S3/blob storage should return the same metadata shape with a different `storage_provider`.

## Manual Real-Image Test

Real-image tests are manual or opt-in integration tests, not default CI tests.

Acceptance flow:

1. Start the API with a real `OPENAI_API_KEY`.
2. Upload a local meal photo.
3. Confirm the response matches the v1 schema.
4. Apply at least one correction after the correction endpoint exists.
5. Log the meal after the log endpoint exists.
6. Confirm the total flow can complete in under 10 seconds.
7. Confirm dataset fields are persisted.

Stage 4 real-image curl:

```bash
curl -X POST "http://localhost:8000/api/v1/meals/analyze-photo" \
  -F "image=@/path/to/meal.jpg" \
  -F "notes=Manual real-image Stage 4 check"
```

Do not assert exact nutrition values from real-image output.
