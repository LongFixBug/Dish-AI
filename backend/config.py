"""Application settings loaded from environment variables and project ``.env``."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_AUTH_SECRET = "dev-only-foodai-secret-change-before-production"
DEVELOPMENT_DATABASE_URL = "postgresql+asyncpg://foodai:foodai@localhost:5432/foodai"


class Settings(BaseSettings):
    """Runtime configuration with deployment-safe environment precedence."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # USDA FoodData Central
    usda_api_key: str = ""

    # App
    app_name: str = "FoodAI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Authentication
    auth_secret_key: str = DEVELOPMENT_AUTH_SECRET
    auth_issuer: str = "foodai-api"
    auth_audience: str = "foodai-mobile"
    google_web_client_id: str = ""
    access_token_minutes: int = Field(default=15, ge=1, le=1_440)
    refresh_token_days: int = Field(default=30, ge=1, le=365)

    # Distributed rate limiting. Memory is for local development only.
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    trust_proxy_headers: bool = False

    # Runtime capabilities are explicit so readiness cannot hide fallbacks.
    vision_enabled: bool = True
    cv_enabled: bool = True
    qdrant_required: bool = True
    enable_dev_routes: bool = True
    log_level: str = "INFO"
    metrics_enabled: bool = True
    metrics_token: str = ""
    vision_max_concurrency: int = Field(default=4, ge=1, le=128)
    embedding_max_concurrency: int = Field(default=8, ge=1, le=128)

    # Feedback object storage. Filesystem is development-only.
    object_storage_backend: Literal["filesystem", "s3"] = "filesystem"
    object_storage_root: Path = PROJECT_ROOT / "data" / "feedback_objects"
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = "foodai-feedback"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    feedback_retention_days: int = Field(default=90, ge=1, le=3_650)

    # OpenAI-compatible cloud Vision API.
    vision_api_key: str = ""
    vision_api_base: str = "https://opencode.ai/zen/go/v1"
    vision_model: str = "qwen3.7-plus"

    # Derived semantic index. PostgreSQL remains the source of truth.
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_url: str = DEVELOPMENT_DATABASE_URL

    # LLM + Embedding (local with llama.cpp)
    llm_url: str = "http://localhost:8080"
    embedding_url: str = "http://localhost:8081"

    # Model names (as reported by llama-server)
    llm_model: str = "qwen2.5-7b-instruct-q4_k_m.gguf"
    embedding_model: str = "qwen3-embedding-0.6b-q8_0.gguf"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse to boot production with the checked-in development secret."""
        if self.environment.lower() == "production":
            if (
                self.auth_secret_key == DEVELOPMENT_AUTH_SECRET
                or len(self.auth_secret_key) < 32
                or _looks_like_placeholder(self.auth_secret_key)
            ):
                raise ValueError(
                    "AUTH_SECRET_KEY must be a unique value of at least 32 characters "
                    "in production"
                )
            if self.rate_limit_backend != "redis":
                raise ValueError(
                    "RATE_LIMIT_BACKEND must be 'redis' in production"
                )
            if self.vision_enabled and (
                not self.vision_api_key
                or _looks_like_placeholder(self.vision_api_key)
            ):
                raise ValueError(
                    "VISION_API_KEY is required when Vision is enabled in production"
                )
            if self.object_storage_backend != "s3":
                raise ValueError(
                    "OBJECT_STORAGE_BACKEND must be 's3' in production"
                )
            database = make_url(self.database_url)
            if (
                self.database_url == DEVELOPMENT_DATABASE_URL
                or not database.password
                or (database.username, database.password) == ("foodai", "foodai")
                or database.host in {"localhost", "127.0.0.1"}
            ):
                raise ValueError(
                    "DATABASE_URL must not use the checked-in development credential"
                )
            if self.metrics_enabled and (
                len(self.metrics_token) < 32
                or _looks_like_placeholder(self.metrics_token)
            ):
                raise ValueError(
                    "METRICS_TOKEN is required when metrics are enabled in production"
                )
        return self


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower().replace("-", "_")
    return any(
        marker in normalized
        for marker in (
            "replace_",
            "change_this",
            "your_",
            "example",
            "demo",
            "dev_only",
        )
    )


settings = Settings()
