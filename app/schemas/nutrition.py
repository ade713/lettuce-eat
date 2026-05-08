from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MacroNutrients(BaseModel):
    """Represent estimated macro and selected micronutrient values for a meal."""

    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float | None = Field(default=None, ge=0)
    sugar_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)


class NutritionEstimate(BaseModel):
    """Validate the structured nutrition payload returned by the AI service."""

    food_name: str
    portion_description: str
    calories_kcal: int = Field(ge=0)
    macros: MacroNutrients
    ingredients: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class NutritionAnalysisResponse(NutritionEstimate):
    """Extend a nutrition estimate with persistence metadata returned to clients."""

    id: UUID
    created_at: datetime | None = None


# Keep the legacy nutrition schemas alongside the v1 meal-flow schemas during the staged
# migration. The current /api/v1/nutrition/analyze endpoint still depends on the legacy
# shape, while new meal-flow endpoints will gradually adopt the v1 schemas below. Once
# the meal flow fully replaces the legacy endpoint, these older schemas can be retired.


class MacroEstimate(BaseModel):
    """Represent calories and core macros for a detected item or meal total."""

    calories: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class MacroDelta(BaseModel):
    """Represent the macro change preview for a suggested correction."""

    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


class Uncertainty(BaseModel):
    """Describe meal-analysis uncertainty dimensions that drive quick corrections."""

    portion_size: str
    ingredient_composition: str
    cooking_fat: str


class Assumption(BaseModel):
    """Represent an editable AI assumption surfaced to the correction UI."""

    key: str
    label: str
    value: str


class MealItem(BaseModel):
    """Represent one food or dish detected in a meal photo analysis."""

    id: str
    label: str
    category: str
    estimated_grams: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    macro_estimate: MacroEstimate
    uncertainty: Uncertainty
    assumptions: list[Assumption] = Field(default_factory=list)


class Suggestion(BaseModel):
    """Represent a client-facing nudge for fast macro correction."""

    id: str
    target_type: str
    target_id: str
    kind: str
    direction: str
    title: str
    subtitle: str
    preview_delta: MacroDelta


class MealAnalysisResponse(BaseModel):
    """Define the v1 client response for a meal photo analysis draft."""

    analysis_id: str
    version: Literal["v1"] = "v1"
    items: list[MealItem]
    meal_totals: MacroEstimate
    overall_confidence: float = Field(ge=0, le=1)
    suggestions: list[Suggestion] = Field(default_factory=list)


class MealCorrectionRequest(BaseModel):
    """Represent a future correction request targeting an analyzed meal item or suggestion."""

    item_id: str
    correction_type: str
    value: str | float
    suggestion_id: str | None = None


class CorrectionEvent(BaseModel):
    """Record one user correction and the macro totals produced by applying it."""

    item_id: str
    correction_type: str
    value: str | float
    resulting_meal_totals: MacroEstimate
    applied_at: datetime
    suggestion_id: str | None = None


class MealCorrectionResponse(MealAnalysisResponse):
    """Represent the future response after deterministic correction math updates a draft."""

    correction_history: list[CorrectionEvent] = Field(default_factory=list)


class ImageStorageMetadata(BaseModel):
    """Describe where the original meal image is stored for future dataset use."""

    storage_provider: str
    image_storage_key: str
    image_content_type: str
    image_size_bytes: int = Field(ge=0)
    image_sha256: str


class MealDatasetMetadata(BaseModel):
    """Preserve the analysis artifacts needed for later evaluation datasets."""

    image: ImageStorageMetadata
    ai_raw_response: dict
    validated_json: MealAnalysisResponse
    correction_history: list[CorrectionEvent] = Field(default_factory=list)


class LoggedMealResponse(BaseModel):
    """Represent a future saved meal created from a corrected analysis draft."""

    meal_id: str
    analysis_id: str
    version: Literal["v1"] = "v1"
    items: list[MealItem]
    final_totals: MacroEstimate
    correction_history: list[CorrectionEvent] = Field(default_factory=list)
    saved_at: datetime
    dataset: MealDatasetMetadata
