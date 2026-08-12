"""Application settings loaded from environment variables and project ``.env``."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
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
    # Legacy compatibility flag. EfficientNet is no longer part of the
    # runtime recognition flow; keep parsing old .env files without loading it.
    cv_enabled: bool = False
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
    # Food Gate là service local riêng.
    # disabled: không gọi Gate
    # shadow: gọi Gate nền, vẫn luôn gọi Vision
    # enforce: Gate block thì không gọi Vision
    food_gate_mode: Literal["disabled", "shadow", "enforce"] = "disabled"
    food_gate_url: AnyHttpUrl | None = None
    food_gate_timeout_seconds: float = Field(default=1.0, ge=0.1, le=10)
    food_gate_service_token: str = ""

    # SigLIP món nước: chỉ gợi ý cho Vision, không tự chốt món.
    # disabled: không gọi SigLIP
    # shadow: gọi nền để quan sát, chưa ảnh hưởng Vision
    # hint: gửi top-k gợi ý vào prompt Vision
    siglip_food_hint_mode: Literal["disabled", "shadow", "hint"] = "disabled"
    siglip_food_hint_url: AnyHttpUrl | None = None
    siglip_food_hint_timeout_seconds: float = Field(default=1.5, ge=0.1, le=10)
    siglip_food_hint_top_k: int = Field(default=3, ge=1, le=5)
    siglip_food_hint_min_score: float = Field(default=0.90, ge=0, le=1)


    # Derived semantic index. PostgreSQL remains the source of truth.
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_url: str = DEVELOPMENT_DATABASE_URL

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Use the asyncpg driver when a provider gives a generic URL."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
    @model_validator(mode="after")
    def validate_local_recognition_modes(self) -> "Settings":
        if self.food_gate_mode != "disabled" and self.food_gate_url is None:
            raise ValueError(
                "FOOD_GATE_URL is required when Food Gate is shadow or enforce"
            )

        if (
            self.siglip_food_hint_mode != "disabled"
            and self.siglip_food_hint_url is None
        ):
            raise ValueError(
                "SIGLIP_FOOD_HINT_URL is required when SigLIP food hint is shadow or hint"
            )

        return self

        return value

    # LLM + Embedding (local with llama.cpp)
    llm_url: str = "http://localhost:8080"
    embedding_url: str = "http://localhost:8081"
    chat_enabled: bool = True
    llm_max_concurrency: int = Field(default=2, ge=1, le=32)
    chat_request_timeout_seconds: float = Field(default=90, ge=5, le=300)

    # Model names (as reported by llama-server)
    llm_model: str = "qwen2.5-7b-instruct-q4_k_m.gguf"
    embedding_model: str = "qwen3-embedding-0.6b-q8_0.gguf"

    # Retired local image-matching settings. They remain parseable so an old
    # .env or offline evaluation script does not crash, but the API never reads
    # them and the default is deliberately disabled.
    image_embed_enabled: bool = False
    image_embed_url: str = "http://localhost:8082"
    image_embed_backend: Literal["siglip2", "dinov2"] = "siglip2"
    image_embed_model: str = "google/siglip2-base-patch16-224"
    image_embed_dim: int = Field(default=768, ge=1, le=4_096)
    image_embed_collection: str = "dish_images_siglip2_base"
    image_embed_max_concurrency: int = Field(default=4, ge=1, le=64)

    # Sidecar tách chủ thể thành sticker (ml/serving/segment_server.py).
    segment_enabled: bool = True
    segment_url: str = "http://localhost:8083"
    segment_max_concurrency: int = Field(default=2, ge=1, le=32)
    segment_max_side: int = Field(default=512, ge=64, le=2048)
    segment_outline_width: int = Field(default=10, ge=0, le=40)
    # Ngưỡng đo bằng ml/evaluation/tune_cascade.py trên data/images/golden
    # Ngưỡng album tham gia consensus; album không được tự chốt ở rollout hiện
    # tại vì runtime evaluation chưa đạt precision gate khi đứng một mình.
    image_match_threshold: float = Field(default=0.75, ge=0, le=1)
    image_match_margin: float = Field(default=0.04, ge=0, le=1)
    image_candidates_limit: int = Field(default=8, ge=1, le=20)

    # EfficientNet + album fusion rollout. Shadow computes/logs the new
    # decision while preserving the legacy response. Active rollout is a
    # separate kill switch. CV solo remains disabled until eval writes an
    # explicitly calibrated threshold into the environment.
    local_fusion_enabled: bool = False
    local_fusion_shadow_enabled: bool = False
    # Stricter than the calibrated CV serving threshold: used only when CV
    # participates in fusion consensus/disagreement, never for CV-only answers.
    local_fusion_cv_threshold: float | None = Field(default=0.999, ge=0, le=1)
    local_fusion_album_solo_enabled: bool = False
    cv_solo_confidence_threshold: float | None = Field(default=None, ge=0, le=1)

    @property
    def is_production(self) -> bool:
        """Cờ production duy nhất, để mọi nơi khỏi tự so sánh chuỗi mỗi kiểu."""
        return self.environment.strip().lower() == "production"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse to boot production with the checked-in development secret."""
        if self.is_production:
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
