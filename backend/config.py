"""Application settings loaded from environment variables and project ``.env``."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime configuration with deployment-safe environment precedence."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # USDA FoodData Central
    usda_api_key: str = ""

    # App
    app_name: str = "FoodAI"
    app_version: str = "0.1.0"
    debug: bool = False

    # OpenAI-compatible cloud Vision API.
    vision_api_key: str = ""
    vision_api_base: str = "https://opencode.ai/zen/go/v1"
    vision_model: str = "qwen3.7-plus"

    # Derived semantic index. PostgreSQL remains the source of truth.
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_url: str = (
        "postgresql+asyncpg://foodai:foodai@localhost:5432/foodai"
    )

    # LLM + Embedding (local with llama.cpp)
    llm_url: str = "http://localhost:8080"
    embedding_url: str = "http://localhost:8081"

    # Model names (as reported by llama-server)
    llm_model: str = "qwen2.5-7b-instruct-q4_k_m.gguf"
    embedding_model: str = "qwen3-embedding-0.6b-q8_0.gguf"


settings = Settings()
