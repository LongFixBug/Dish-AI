"""Embed one search query through the local llama.cpp server.

The query path uses the same model as ``scripts/reindex_qdrant.py`` so query
and catalog vectors remain in the same semantic space.
"""

from backend.config import settings
from backend.services.resilience import ResilientHttpClient


EMBEDDING_API = f"{settings.embedding_url}/v1/embeddings"
# Semantic vectors are an optional derived-index accelerator. Exact PostgreSQL
# lookup and Vision remain authoritative, so a contended local model must fail
# fast instead of holding an image request for minutes.
TIMEOUT = 3.0
embedding_http_client = ResilientHttpClient(
    service="embedding",
    timeout_seconds=TIMEOUT,
    max_concurrency=settings.embedding_max_concurrency,
    max_attempts=1,
)


async def embed_query(text: str) -> list[float]:
    """Return the 1024-dimensional semantic vector for one query.

    Raises:
        httpx.HTTPError: The embedding server is unavailable or rejects the request.
    """
    response = await embedding_http_client.post(
        EMBEDDING_API,
        json={"input": [text], "model": settings.embedding_model},
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["embedding"]


async def close_embedding_client() -> None:
    await embedding_http_client.close()
