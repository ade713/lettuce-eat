from app.schemas.nutrition import (
    MacroDelta,
    MacroEstimate,
    MealAnalysisResponse,
    MealCorrectionRequest,
    MealCorrectionResponse,
    MealItem,
    Suggestion,
)

# Some keys are intentional aliases during the MVP: UI controls, assumption values,
# and suggestion directions may use slightly different words for the same correction.
# Split or remove aliases later after observing real correction usage from clients.
_PORTION_SCALE_FACTORS = {
    "smaller": 0.85,
    "small": 0.85,
    "normal": 1.0,
    "larger": 1.15,
    "large": 1.15,
}
_COMPOSITION_DELTAS = {
    "more_meat": MacroDelta(calories=40, protein_g=6, carbs_g=-8, fat_g=2),
    "higher_protein": MacroDelta(calories=40, protein_g=6, carbs_g=-8, fat_g=2),
    "more_rice": MacroDelta(calories=35, protein_g=-4, carbs_g=12, fat_g=-1),
    "higher_carbs": MacroDelta(calories=35, protein_g=-4, carbs_g=12, fat_g=-1),
}
_OIL_LEVEL_DELTAS = {
    "light": MacroDelta(calories=-45, protein_g=0, carbs_g=0, fat_g=-5),
    "normal": MacroDelta(calories=0, protein_g=0, carbs_g=0, fat_g=0),
    "oily": MacroDelta(calories=70, protein_g=0, carbs_g=0, fat_g=8),
    "higher": MacroDelta(calories=70, protein_g=0, carbs_g=0, fat_g=8),
}


class UnknownCorrectionTargetError(ValueError):
    """Raise when a correction references an item that is not in the draft analysis."""


class UnknownCorrectionTypeError(ValueError):
    """Raise when a correction type is not supported by the deterministic engine."""


class UnknownCorrectionValueError(ValueError):
    """Raise when a correction value is unsupported for its correction type."""


class UnknownSuggestionError(ValueError):
    """Raise when a suggestion-based correction references a missing suggestion."""


class MealCorrectionService:
    """Apply deterministic user corrections to a draft meal analysis.

    Stage 5 keeps this as a pure-Python boundary so correction behavior can be
    developed and tested without FastAPI, database sessions, or AI provider calls.
    """

    def apply_correction(
        self, *, analysis: MealAnalysisResponse, correction: MealCorrectionRequest
    ) -> MealCorrectionResponse:
        """Apply a supported MVP correction control to a draft analysis.

        Step 3 updates the targeted item macro estimate and recalculates meal
        totals from all item macro estimates. Later Stage 5 steps will append
        correction history.
        """

        target_item = self._require_target_item(analysis=analysis, item_id=correction.item_id)
        corrected_macro = self._correct_macro(
            analysis=analysis, correction=correction, current_macro=target_item.macro_estimate
        )
        return self._response_with_corrected_item(
            analysis=analysis, item_id=target_item.id, corrected_macro=corrected_macro
        )

    def _require_target_item(self, *, analysis: MealAnalysisResponse, item_id: str) -> MealItem:
        """Return the item targeted by a correction request or raise a domain error."""

        for item in analysis.items:
            if item.id == item_id:
                return item

        raise UnknownCorrectionTargetError(f"Correction item not found: {item_id}")

    def _correct_macro(
        self,
        *,
        analysis: MealAnalysisResponse,
        correction: MealCorrectionRequest,
        current_macro: MacroEstimate,
    ) -> MacroEstimate:
        """Dispatch a correction request to the deterministic control handler."""

        correction_type = correction.correction_type
        if correction_type == "portion_scale":
            return self._apply_portion_scale(current_macro=current_macro, value=correction.value)
        if correction_type == "composition_ratio":
            return self._apply_delta(
                current_macro=current_macro,
                delta=self._delta_for_value(
                    correction_type=correction_type,
                    value=correction.value,
                    deltas=_COMPOSITION_DELTAS,
                ),
            )
        if correction_type == "oil_level":
            return self._apply_delta(
                current_macro=current_macro,
                delta=self._delta_for_value(
                    correction_type=correction_type,
                    value=correction.value,
                    deltas=_OIL_LEVEL_DELTAS,
                ),
            )
        if correction_type == "suggestion_delta":
            suggestion = self._get_suggestion(analysis=analysis, correction=correction)
            return self._apply_delta(current_macro=current_macro, delta=suggestion.preview_delta)

        raise UnknownCorrectionTypeError(f"Unsupported correction type: {correction_type}")

    def _apply_portion_scale(self, *, current_macro: MacroEstimate, value: str | float) -> MacroEstimate:
        """Scale a macro estimate for smaller/larger portion controls."""

        factor = self._portion_factor(value=value)
        return MacroEstimate(
            calories=max(0, round(current_macro.calories * factor)),
            protein_g=max(0, current_macro.protein_g * factor),
            carbs_g=max(0, current_macro.carbs_g * factor),
            fat_g=max(0, current_macro.fat_g * factor),
        )

    def _portion_factor(self, *, value: str | float) -> float:
        """Return a deterministic multiplier for a portion correction value."""

        if isinstance(value, int | float):
            if value <= 0:
                raise UnknownCorrectionValueError("Portion scale must be greater than zero.")
            return float(value)

        factor = _PORTION_SCALE_FACTORS.get(value)
        if factor is None:
            raise UnknownCorrectionValueError(f"Unsupported portion scale value: {value}")
        return factor

    def _delta_for_value(
        self, *, correction_type: str, value: str | float, deltas: dict[str, MacroDelta]
    ) -> MacroDelta:
        """Return the configured macro delta for a named correction value."""

        if not isinstance(value, str):
            raise UnknownCorrectionValueError(
                f"{correction_type} corrections require a named string value."
            )

        delta = deltas.get(value)
        if delta is None:
            raise UnknownCorrectionValueError(
                f"Unsupported {correction_type} correction value: {value}"
            )
        return delta

    def _get_suggestion(
        self, *, analysis: MealAnalysisResponse, correction: MealCorrectionRequest
    ) -> Suggestion:
        """Return the suggestion referenced by a suggestion-based correction."""

        if correction.suggestion_id is None:
            raise UnknownSuggestionError("Suggestion correction requires suggestion_id.")

        for suggestion in analysis.suggestions:
            if suggestion.id == correction.suggestion_id and suggestion.target_id == correction.item_id:
                return suggestion

        raise UnknownSuggestionError(f"Suggestion not found: {correction.suggestion_id}")

    def _apply_delta(self, *, current_macro: MacroEstimate, delta: MacroDelta) -> MacroEstimate:
        """Add a macro delta while preventing negative macro values."""

        return MacroEstimate(
            calories=max(0, current_macro.calories + delta.calories),
            protein_g=max(0, current_macro.protein_g + delta.protein_g),
            carbs_g=max(0, current_macro.carbs_g + delta.carbs_g),
            fat_g=max(0, current_macro.fat_g + delta.fat_g),
        )

    def _response_with_corrected_item(
        self, *, analysis: MealAnalysisResponse, item_id: str, corrected_macro: MacroEstimate
    ) -> MealCorrectionResponse:
        """Build a correction response with the targeted item macro estimate updated."""

        corrected_items = [
            self._item_with_macro(item=item, corrected_macro=corrected_macro)
            if item.id == item_id
            else item
            for item in analysis.items
        ]
        payload = analysis.model_dump(mode="json")
        payload["items"] = [item.model_dump(mode="json") for item in corrected_items]
        payload["meal_totals"] = self._meal_totals_from_items(corrected_items).model_dump(
            mode="json"
        )
        payload["correction_history"] = []
        return MealCorrectionResponse.model_validate(payload)

    def _meal_totals_from_items(self, items: list[MealItem]) -> MacroEstimate:
        """Recalculate meal totals from typed item macro estimates."""

        macros = [item.macro_estimate for item in items]
        return MacroEstimate(
            calories=sum(macro.calories for macro in macros),
            protein_g=sum(macro.protein_g for macro in macros),
            carbs_g=sum(macro.carbs_g for macro in macros),
            fat_g=sum(macro.fat_g for macro in macros),
        )

    def _item_with_macro(self, *, item: MealItem, corrected_macro: MacroEstimate) -> MealItem:
        """Return an item model with a replaced macro estimate."""

        return item.model_copy(update={"macro_estimate": corrected_macro})
