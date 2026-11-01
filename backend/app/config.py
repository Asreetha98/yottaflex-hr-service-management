"""Application settings read from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "YottaFlex HR Service Management"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "sqlite:///./yottaflex_dev.db"

    # Security
    secret_key: str = "dev-only-secret-key-change-me-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # CORS (comma separated)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Business configuration
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_timezone: str = "UTC"
    classification_confidence_threshold: float = 0.40
    ambiguity_margin: float = 0.15

    # Bootstrap behaviour
    # Keep these False by default so a loaded database is never overwritten on restart.
    # Set SEED_REFERENCE_DATA=true only on a brand-new empty database.
    auto_create_tables: bool = True
    seed_reference_data: bool = False
    seed_demo_users: bool = False
    demo_user_password: str = "ChangeMe123!"

    # Evaluation (relative to the backend/ working dir when running uvicorn from backend/)
    ground_truth_path: str = "../generator/output/ground_truth.json"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
