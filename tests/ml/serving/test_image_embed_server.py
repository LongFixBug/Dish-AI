"""Contract tests for the SigLIP 2 image-embedding sidecar.

Model thật không bao giờ được load trong test: ``_load_backend`` được thay
bằng fake trả vector deterministic, nên toàn bộ suite chạy offline.
"""

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ml.serving import image_embed_server
from ml.serving.image_embed_server import EMBED_DIM, MAX_BATCH_SIZE, EmbeddingBackend


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
