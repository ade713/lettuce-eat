from app.schemas.nutrition import (
    MealAnalysisResponse,
    MealCorrectionRequest,
    MealCorrectionResponse,
    MealItem,
)


class UnknownCorrectionTargetError(ValueError):
    """Raise when a correction references an item that is not in the draft analysis."""


class MealCorrectionService:
    """Apply deterministic user corrections to a draft meal analysis.

    Stage 5 starts with this pure-Python boundary so correction behavior can be
    developed and tested without FastAPI, database sessions, or AI provider calls.
    Later Stage 5 steps will add the actual macro math and correction history.
    """

    def apply_correction(
        self, *, analysis: MealAnalysisResponse, correction: MealCorrectionRequest
    ) -> MealCorrectionResponse:
        """Accept a draft analysis and correction request, returning a correction response.

        The first implementation step validates that the request targets an existing
        item and preserves the current analysis values. Later steps will update item
        macros, meal totals, and correction history from this same service method.
        """

        self._get_target_item(analysis=analysis, item_id=correction.item_id)
        return MealCorrectionResponse.model_validate(
            analysis.model_dump(mode="json") | {"correction_history": []}
        )

    def _get_target_item(self, *, analysis: MealAnalysisResponse, item_id: str) -> MealItem:
        """Return the item targeted by a correction request or raise a domain error."""

        for item in analysis.items:
            if item.id == item_id:
                return item

        raise UnknownCorrectionTargetError(f"Correction item not found: {item_id}")
