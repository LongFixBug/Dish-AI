"""Embed one search query through the local llama.cpp server.

The query path uses the same model as ``scripts/reindex_qdrant.py`` so query
and catalog vectors remain in the same semantic space.
"""

import httpx

from backend.config import settings


EMBEDDING_API = f"{settings.embedding_url}/v1/embeddings"
TIMEOUT = 30.0


async def embed_query(text: str) -> list[float]:
    """Return the 1024-dimensional semantic vector for one query.

    Raises:
        httpx.HTTPError: The embedding server is unavailable or rejects the request.
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
