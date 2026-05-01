from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MacroNutrients(BaseModel):
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float | None = Field(default=None, ge=0)
    sugar_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)


class NutritionEstimate(BaseModel):
    food_name: str
    portion_description: str
    calories_kcal: int = Field(ge=0)
    macros: MacroNutrients
    ingredients: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class NutritionAnalysisResponse(NutritionEstimate):
    id: UUID
    created_at: datetime | None = None

