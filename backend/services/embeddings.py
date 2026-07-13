"""Service sinh embedding cho query (đưa query text → vector).

Gọi llama.cpp embedding server (port 8081) — cùng server và API format
như scripts/generate_embeddings.py, nhưng cho 1 xâu query thay vì batch.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx

from backend.config import settings


EMBEDDING_API = f"{settings.embedding_url}/v1/embeddings"
TIMEOUT = 30.0


async def embed_query(text: str) -> list[float]:
    """Sinh embedding cho 1 text → vector 1024D.

    Dùng để tìm nguyên liệu theo nghĩa (vector search): query 'cơm chiên' có thể
    móc được 'cơm sườn', 'cơm gà' dù khác tên.

    Raises:
        httpx.HTTPError: nếu embedding server không chạy hoặc trả lỗi.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            EMBEDDING_API,
            json={"input": [text], "model": settings.embedding_model},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]