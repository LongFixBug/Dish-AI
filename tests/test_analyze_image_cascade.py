"""Contract tests for the Vision-only image-analysis flow.

The old filename is kept so the retired local image-cascade coverage is
obviously replaced rather than silently disappearing.
"""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from starlette.datastructures import Headers, UploadFile

from backend.api import analyze
from ml.inference.vision import VisionError


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _jpeg_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), (180, 120, 60)).save(output, format="JPEG")
    return output.getvalue()


def _upload(filename: str = "mon-an.jpg") -> UploadFile:
    return UploadFile(
        BytesIO(_jpeg_bytes()),
        filename=filename,
        headers=Headers({"content-type": "image/jpeg"}),
    )


def test_analyze_module_has_no_retired_local_image_imports() -> None:
    source = Path(analyze.__file__).read_text(encoding="utf-8")

    assert "recognition_cascade" not in source
    assert "dish_image_index" not in source
    assert "ml.inference.cv" not in source


async def test_analyze_uses_vision_without_local_image_models(monkeypatch) -> None:
    calls: dict[str, object] = {}

    async def local_must_not_run(*_args, **_kwargs):
        raise AssertionError("Không được gọi EfficientNet/SigLIP trong /analyze")

    async def fake_vision(path, **kwargs):
        calls["path"] = path
        calls["kwargs"] = kwargs
        return {"dishes": []}

    async def fake_record(_session, **kwargs):
        calls["event"] = kwargs
        return "event-id"

    monkeypatch.setattr(analyze, "_run_local_recognition", local_must_not_run, raising=False)
    monkeypatch.setattr(analyze, "image_candidates", local_must_not_run, raising=False)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)
    monkeypatch.setattr(analyze, "record_recognition_event", fake_record)

    response = await analyze.analyze_food(
        _upload(),
        FakeSession(),
        SimpleNamespace(id="user-id"),
    )

    assert response.source == "vision"
    assert response.model_version == analyze.settings.vision_model
    assert response.recognition_event_id == "event-id"
    assert calls["kwargs"] == {}
    event = calls["event"]
    assert event["cv_dish_name"] is None
    assert event["album_dish_name"] is None
    assert event["album_score"] is None
    assert event["album_margin"] is None


async def test_analyze_vision_error_is_reported_without_local_fallback(monkeypatch) -> None:
    async def local_must_not_run(*_args, **_kwargs):
        raise AssertionError("Không được gọi local image matcher")

    async def failing_vision(*_args, **_kwargs):
        raise VisionError("vision unavailable")

    monkeypatch.setattr(analyze, "_run_local_recognition", local_must_not_run, raising=False)
    monkeypatch.setattr(analyze, "identify_dish", failing_vision)

    response = await analyze.analyze_food(_upload("vision-down.jpg"), FakeSession())

    assert response.source == "vision"
    assert response.dish_name is None
    assert response.cv_confidence is None
    assert response.error is not None


async def test_vision_only_endpoint_remains_direct_vision(monkeypatch) -> None:
    async def fake_vision(path, **kwargs):
        assert kwargs == {}
        return {"dishes": []}

    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_vision_only(
        _upload("direct-vision.jpg"),
        FakeSession(),
        SimpleNamespace(id="user-id"),
    )

    assert response.source == "vision"
    assert response.model_version == analyze.settings.vision_model
    assert response.error is not None
