"""Application configuration — .env là nguồn thật (override env shell).

Mặc định pydantic-settings ưu tiên biến môi trường shell > file .env →
nếu shell có export cũ (VD VISION_MODEL=qwen3.5-plus) sẽ đè giá trị .env mới.
Đảo lại: nạp .env vào os.environ với override=True TRƯỚC khi Settings()
chạy, để .env luôn thắng. User đổi key/model trong .env → áp dụng ngay.
"""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Nạp .env vào os.environ với override=True → .env thắng env shell cũ.
# Phải chạy TRƯỚC khi Settings() khởi tạo (nằm dưới) thì mới effect.
load_dotenv(".env", override=True)


class Settings(BaseSettings):
    """FoodAI settings — .env là nguồn thật (override env shell)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    # USDA FoodData Central
    usda_api_key: str = ""

    # App
    app_name: str = "FoodAI"
    app_version: str = "0.1.0"
    debug: bool = True

    # Vision API (cloud — for food image recognition)
    # Dùng OpenCode API thay Gemini
    vision_api_key: str = ""
    vision_api_base: str = "https://opencode.ai/zen/go/v1"
    vision_model: str = "qwen3.6-plus"

    # RAG — Vector DB
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_url: str = (
        "postgresql+asyncpg://foodai:foodai@localhost:5433/foodai"
    )

    # LLM + Embedding (local with llama.cpp)
    llm_url: str = "http://localhost:8080"
    embedding_url: str = "http://localhost:8081"

    # Model names (as reported by llama-server)
    llm_model: str = "qwen2.5-7b-instruct-q4_k_m.gguf"
    embedding_model: str = "qwen3-embedding-0.6b-q8_0.gguf"


settings = Settings()
