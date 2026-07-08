"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FoodAI settings — all values can be overridden via .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # App
    app_name: str = "FoodAI"
    app_version: str = "0.1.0"
    debug: bool = True

    # Vision API (cloud — for food image recognition)
    # Dùng OpenCode API thay Gemini
    vision_api_key: str = ""
    vision_api_base: str = "https://opencode.ai/zen/go/v1"
    vision_model: str = "qwen3.7-plus"

    # RAG — Vector DB (keep Qdrant for now, may switch to pgvector)
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
