"""Embed dish photos through the configured image sidecar (port 8082).

The client mirrors ``backend/services/embeddings.py`` so image vectors go
through the same resilience layer (retry + circuit breaker + concurrency cap)
as text embeddings. Vectors are returned in input order via the ``index``
field of the sidecar response.
"""

import base64

from backend.config import settings
from backend.services.resilience import ResilientHttpClient

IMAGE_EMBEDDING_API = f"{settings.image_embed_url}/v1/image-embeddings"
TIMEOUT = 60.0
image_embedding_http_client = ResilientHttpClient(
    service="image_embedding",
    timeout_seconds=TIMEOUT,
    max_concurrency=settings.image_embed_max_concurrency,
)


async def embed_image(data: bytes) -> list[float]:
    """Return the configured L2-normalized vector for one image.

    Raises:
        httpx.HTTPError: The sidecar is unavailable or rejects the request.
    """
    vectors = await embed_images([data])
    return vectors[0]


async def embed_images(batch: list[bytes]) -> list[list[float]]:
    """Embed a batch of raw image bytes, preserving input order.

    Raises:
        httpx.HTTPError: The sidecar is unavailable or rejects the request.
        ValueError: The sidecar returned a malformed or incomplete batch.
    """
    if not batch:
        return []
    encoded = [base64.b64encode(item).decode("ascii") for item in batch]
    response = await image_embedding_http_client.post(
        IMAGE_EMBEDDING_API,
        json={"images": encoded},
    )
    response.raise_for_status()
    payload = response.json()
    reported_dim = payload.get("dim")
    if reported_dim != settings.image_embed_dim:
        raise ValueError(
            "Image embedding sidecar returned dimension "
            f"{reported_dim}; expected {settings.image_embed_dim}"
        )
    items = payload.get("data")
    if not isinstance(items, list):
        raise ValueError("Image embedding response is missing a data list")
    ordered = sorted(items, key=lambda item: item["index"])
    if [item["index"] for item in ordered] != list(range(len(batch))):
        raise ValueError(
            f"Image embedding response covers {len(ordered)} items "
            f"for a batch of {len(batch)}"
        )
    return [item["embedding"] for item in ordered]


async def close_image_embedding_client() -> None:
    await image_embedding_http_client.close()
