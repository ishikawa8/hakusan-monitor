"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hakusan_monitor"

    # Supabase (optional)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Auth
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Device API Keys
    device_api_keys: str = "hakusan_key_001,hakusan_key_002"

    # Open-Meteo
    open_meteo_latitude: float = 36.1533
    open_meteo_longitude: float = 136.7717
    open_meteo_elevation: int = 2702

    # AI
    ai_model_path: str = "./models/detectron2_config.yaml"
    ai_confidence_threshold: float = 0.5

    # CORS
    cors_origins: str = "https://ishikawa8.github.io,http://localhost:3000,http://localhost:8000"

    # Environment
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def device_api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.device_api_keys.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
