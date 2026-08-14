"""Client contract for the image-embedding sidecar (offline, HTTP mocked)."""

import base64

import httpx
import pytest

from backend.services import image_embeddings


def _sidecar_response(
    items: list[dict],
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={
            "model": "fake-dinov2",
            "dim": image_embeddings.settings.image_embed_dim,
            "data": items,
        },
        request=httpx.Request("POST", image_embeddings.IMAGE_EMBEDDING_API),
    )


def _patch_post(
    monkeypatch: pytest.MonkeyPatch,
    response: httpx.Response,
) -> dict:
    """Replace the resilient client's post; return the captured call."""
    captured: dict = {}

    async def fake_post(url: str, **kwargs) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return response

    monkeypatch.setattr(
        image_embeddings.image_embedding_http_client,
        "post",
        fake_post,
    )
    return captured


async def test_embed_image_sends_base64_and_returns_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b"jpeg-bytes"
    captured = _patch_post(
        monkeypatch,
        _sidecar_response([{"index": 0, "embedding": [0.6, 0.8]}]),
    )

    vector = await image_embeddings.embed_image(raw)

    assert vector == [0.6, 0.8]
    assert captured["url"] == image_embeddings.IMAGE_EMBEDDING_API
    assert captured["json"] == {
        "images": [base64.b64encode(raw).decode("ascii")],
    }


async def test_embed_images_orders_results_by_index_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(
        monkeypatch,
        _sidecar_response([
            {"index": 2, "embedding": [3.0]},
            {"index": 0, "embedding": [1.0]},
            {"index": 1, "embedding": [2.0]},
        ]),
    )

    vectors = await image_embeddings.embed_images([b"a", b"b", b"c"])

    assert vectors == [[1.0], [2.0], [3.0]]


async def test_embed_images_encodes_each_item_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = [b"first", b"second"]
    captured = _patch_post(
        monkeypatch,
        _sidecar_response([
            {"index": 0, "embedding": [0.1]},
            {"index": 1, "embedding": [0.2]},
        ]),
    )

    await image_embeddings.embed_images(batch)

    assert captured["json"]["images"] == [
        base64.b64encode(item).decode("ascii") for item in batch
    ]


async def test_empty_batch_short_circuits_without_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_post(url: str, **kwargs) -> httpx.Response:
        raise AssertionError("HTTP must not be called for an empty batch")

    monkeypatch.setattr(
        image_embeddings.image_embedding_http_client,
        "post",
        fail_post,
    )

    assert await image_embeddings.embed_images([]) == []


async def test_http_error_status_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(monkeypatch, _sidecar_response([], status_code=400))

    with pytest.raises(httpx.HTTPStatusError):
        await image_embeddings.embed_images([b"bad"])


async def test_incomplete_response_batch_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(
        monkeypatch,
        _sidecar_response([{"index": 0, "embedding": [1.0]}]),
    )

    with pytest.raises(ValueError):
        await image_embeddings.embed_images([b"a", b"b"])


async def test_embed_images_rejects_a_sidecar_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        json={
            "model": "fake-siglip2",
            "dim": 384,
            "data": [{"index": 0, "embedding": [0.1]}],
        },
        request=httpx.Request("POST", image_embeddings.IMAGE_EMBEDDING_API),
    )
    _patch_post(monkeypatch, response)

    with pytest.raises(ValueError, match="dimension 384"):
        await image_embeddings.embed_images([b"a"])
