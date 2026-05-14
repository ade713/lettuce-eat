from fastapi import APIRouter

from app.api.v1.meals import router as meals_router
from app.api.v1.nutrition import router as nutrition_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meals_router)
api_router.include_router(nutrition_router)

