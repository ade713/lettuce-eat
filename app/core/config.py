from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load and validate runtime configuration for the API process."""

    app_name: str = "Lettuce Eat"
    environment: str = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/meal_nutrition",
        alias="DATABASE_URL",
    )
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    max_upload_mb: int = Field(default=10, alias="MAX_UPLOAD_MB")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings loaded from environment variables and .env."""

    return Settings()
