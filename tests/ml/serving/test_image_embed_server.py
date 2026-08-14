"""Contract tests for the image-embedding sidecar.

Model thật không bao giờ được load trong test: ``_load_backend`` được thay
bằng fake trả vector deterministic, nên toàn bộ suite chạy offline.
"""

import base64
import io
from types import SimpleNamespace

import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

from ml.serving import image_embed_server
from ml.serving.image_embed_server import (
    EMBED_DIM,
    MAX_BATCH_SIZE,
    EmbeddingBackend,
)


def _png_base64(color: tuple[int, int, int] = (200, 30, 30)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _fake_vector(seed: int) -> list[float]:
    return [float(seed)] + [0.0] * (EMBED_DIM - 1)


@pytest.fixture
def sidecar(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client with the model loader replaced by a deterministic fake."""

    def encode(images: list[Image.Image]) -> list[list[float]]:
        return [_fake_vector(index + 1) for index in range(len(images))]

    fake_backend = EmbeddingBackend(
        model_name="fake-siglip2",
        device="cpu",
        encode=encode,
    )
    monkeypatch.setattr(image_embed_server, "_backend", None)
    monkeypatch.setattr(image_embed_server, "_load_backend", lambda: fake_backend)
    return TestClient(image_embed_server.app)


def test_health_reports_unloaded_before_first_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(image_embed_server, "_backend", None)

    response = TestClient(image_embed_server.app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["device"] == "unloaded"
    assert payload["dim"] == EMBED_DIM
    assert payload["model"] == image_embed_server.MODEL_NAME
    assert payload["image_embed_loaded"] is False


def test_image_embed_device_can_be_forced_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_EMBED_DEVICE", "cpu")

    assert image_embed_server.resolve_image_embed_device(mps_available=True) == "cpu"


def test_warmup_loads_only_image_encoder(sidecar: TestClient) -> None:
    response = sidecar.post("/v1/warmup")

    assert response.status_code == 200
    assert response.json() == {
        "image_embed_loaded": True,
        "image_embed_model": "fake-siglip2",
        "dim": EMBED_DIM,
    }


def test_classifier_endpoint_is_removed(sidecar: TestClient) -> None:
    response = sidecar.post(
        "/v1/classify",
        json={"image": _png_base64()},
    )

    assert response.status_code == 404


def test_extracts_pooler_output_from_a_vision_only_model() -> None:
    expected = object()

    class VisionOnlyModel:
        def __call__(self, **_inputs):
            return SimpleNamespace(pooler_output=expected)

    result = image_embed_server._extract_image_features(
        VisionOnlyModel(),
        {"pixel_values": object()},
    )

    assert result is expected


def test_extracts_cls_feature_when_dino_returns_hidden_states() -> None:
    hidden = torch.arange(1 * 3 * 4, dtype=torch.float32).reshape(1, 3, 4)

    class DinoModel:
        def __call__(self, **_inputs):
            return SimpleNamespace(last_hidden_state=hidden)

    result = image_embed_server._extract_image_features(
        DinoModel(),
        {"pixel_values": object()},
    )

    assert torch.equal(result, hidden[:, 0])


def test_dinov2_backend_defaults_to_small_model() -> None:
    assert image_embed_server.default_model_for_backend("dinov2") == (
        "facebook/dinov2-small"
    )


def test_dinov2_backend_has_a_separate_vector_dimension() -> None:
    assert image_embed_server.default_embedding_dim_for_backend("dinov2") == 384


def test_sidecar_default_flow_uses_siglip2() -> None:
    assert image_embed_server.IMAGE_EMBED_BACKEND == "siglip2"
    assert image_embed_server.MODEL_NAME == "google/siglip2-base-patch16-224"
    assert image_embed_server.EMBED_DIM == 768


def test_embeds_a_single_image(sidecar: TestClient) -> None:
    response = sidecar.post(
        "/v1/image-embeddings",
        json={"images": [_png_base64()]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "fake-siglip2"
    assert payload["dim"] == EMBED_DIM
    assert len(payload["data"]) == 1
    assert payload["data"][0]["index"] == 0
    assert len(payload["data"][0]["embedding"]) == EMBED_DIM


def test_batch_preserves_input_order(sidecar: TestClient) -> None:
    images = [_png_base64((r, 0, 0)) for r in (10, 20, 30)]

    response = sidecar.post("/v1/image-embeddings", json={"images": images})

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["index"] for item in data] == [0, 1, 2]
    assert [item["embedding"][0] for item in data] == [1.0, 2.0, 3.0]


def test_health_reports_device_after_model_load(sidecar: TestClient) -> None:
    sidecar.post("/v1/image-embeddings", json={"images": [_png_base64()]})

    payload = sidecar.get("/health").json()

    assert payload["device"] == "cpu"
    assert payload["model"] == "fake-siglip2"


def test_loaded_backend_dimension_is_reported_by_health_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vector = [0.5] * 384
    fake_backend = EmbeddingBackend(
        model_name="fake-dinov2",
        device="cpu",
        encode=lambda _images: [vector],
        dim=384,
    )
    monkeypatch.setattr(image_embed_server, "_backend", None)
    monkeypatch.setattr(image_embed_server, "_load_backend", lambda: fake_backend)
    client = TestClient(image_embed_server.app)

    response = client.post(
        "/v1/image-embeddings",
        json={"images": [_png_base64()]},
    )

    assert response.status_code == 200
    assert response.json()["dim"] == 384
    assert len(response.json()["data"][0]["embedding"]) == 384
    assert client.get("/health").json()["dim"] == 384


def test_invalid_base64_returns_400_with_bad_index(sidecar: TestClient) -> None:
    response = sidecar.post(
        "/v1/image-embeddings",
        json={"images": [_png_base64(), "!!!not-base64!!!"]},
    )

    assert response.status_code == 400
    assert "[1]" in response.json()["detail"]


def test_valid_base64_but_not_an_image_returns_400(sidecar: TestClient) -> None:
    not_an_image = base64.b64encode(b"plain text bytes").decode("ascii")

    response = sidecar.post(
        "/v1/image-embeddings",
        json={"images": [not_an_image, _png_base64()]},
    )

    assert response.status_code == 400
    assert "[0]" in response.json()["detail"]


def test_oversized_batch_returns_413(sidecar: TestClient) -> None:
    images = [_png_base64()] * (MAX_BATCH_SIZE + 1)

    response = sidecar.post("/v1/image-embeddings", json={"images": images})

    assert response.status_code == 413


def test_empty_image_list_is_rejected_by_validation(sidecar: TestClient) -> None:
    response = sidecar.post("/v1/image-embeddings", json={"images": []})

    assert response.status_code == 422


def test_backend_failure_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_loader() -> EmbeddingBackend:
        raise RuntimeError("model download failed")

    monkeypatch.setattr(image_embed_server, "_backend", None)
    monkeypatch.setattr(image_embed_server, "_load_backend", broken_loader)

    response = TestClient(image_embed_server.app).post(
        "/v1/image-embeddings",
        json={"images": [_png_base64()]},
    )

    assert response.status_code == 503
