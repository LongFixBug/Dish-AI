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

    # Gemini API (cloud — for food image recognition)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # RAG — Vector DB
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_url: str = (
        "postgresql+asyncpg://foodai:foodai@localhost:5432/foodai"
    )

    # Embedding (local with llama.cpp)
    llama_cpp_url: str = "http://localhost:8080"


settings = Settings()
