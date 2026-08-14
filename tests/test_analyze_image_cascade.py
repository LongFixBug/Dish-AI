"""Contract tests for the Vision-only image-analysis flow.

The old filename is kept so the retired local image-cascade coverage is
obviously replaced rather than silently disappearing.
"""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile
from starlette.background import BackgroundTasks

from backend.api import analyze
from backend.services.food_gate import FoodGateShadowResult
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


def _enforce_settings() -> SimpleNamespace:
    """Minimal settings surface used by the enforce-path contract tests."""
    return SimpleNamespace(
        food_gate_mode="enforce",
        siglip_food_hint_mode="disabled",
        vision_model=analyze.settings.vision_model,
    )


async def _record_event(*_args, **_kwargs) -> str:
    """Keep endpoint tests focused on Gate routing, not database persistence."""
    return "event-id"


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
        BackgroundTasks(),
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


async def test_analyze_food_schedules_food_gate_shadow_without_changing_vision(
    monkeypatch,
) -> None:
    shadow_calls: list[tuple[bytes, str]] = []

    async def fake_vision(path, **kwargs):
        assert kwargs == {}
        return {"dishes": []}

    async def fake_shadow(content: bytes, content_type: str) -> None:
        shadow_calls.append((content, content_type))

    monkeypatch.setattr(analyze.settings, "food_gate_mode", "shadow")
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)
    monkeypatch.setattr(analyze, "observe_food_gate_shadow", fake_shadow)
    background_tasks = BackgroundTasks()

    response = await analyze.analyze_food(
        background_tasks,
        _upload(),
        FakeSession(),
        SimpleNamespace(id="user-id"),
    )

    assert response.source == "vision"
    assert shadow_calls == []

    await background_tasks()

    assert len(shadow_calls) == 1
    assert shadow_calls[0][1] == "image/jpeg"


async def test_enforce_food_gate_blocks_non_food_before_vision(monkeypatch) -> None:
    vision_calls: list[Path] = []
    gate_calls: list[tuple[bytes, str]] = []

    async def fake_gate(content: bytes, content_type: str) -> FoodGateShadowResult:
        gate_calls.append((content, content_type))
        return FoodGateShadowResult(
            action="block",
            food_score=0.07,
            non_food_score=0.93,
            block_threshold=0.90,
        )

    async def vision_must_not_run(path: Path, **_kwargs):
        vision_calls.append(path)
        raise AssertionError("Gate block phải chặn trước khi gọi Vision")

    monkeypatch.setattr(analyze, "settings", _enforce_settings())
    monkeypatch.setattr(analyze, "predict_food_gate", fake_gate, raising=False)
    monkeypatch.setattr(analyze, "identify_dish", vision_must_not_run)
    monkeypatch.setattr(analyze, "record_recognition_event", _record_event)

    with pytest.raises(HTTPException) as exc_info:
        await analyze.analyze_food(
            BackgroundTasks(),
            _upload("cat.jpg"),
            FakeSession(),
            SimpleNamespace(id="user-id"),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "non_food_image",
        "message": "Ảnh này chưa thấy món ăn. Hãy chụp gần món hơn.",
    }
    assert len(gate_calls) == 1
    assert gate_calls[0][1] == "image/jpeg"
    assert vision_calls == []


async def test_enforce_food_gate_allows_food_to_call_vision_once(monkeypatch) -> None:
    vision_calls: list[Path] = []
    gate_calls: list[tuple[bytes, str]] = []

    async def fake_gate(content: bytes, content_type: str) -> FoodGateShadowResult:
        gate_calls.append((content, content_type))
        return FoodGateShadowResult(
            action="vision",
            food_score=0.93,
            non_food_score=0.07,
            block_threshold=0.90,
        )

    async def fake_vision(path: Path, **kwargs):
        assert kwargs == {}
        vision_calls.append(path)
        return {"dishes": []}

    monkeypatch.setattr(analyze, "settings", _enforce_settings())
    monkeypatch.setattr(analyze, "predict_food_gate", fake_gate, raising=False)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)
    monkeypatch.setattr(analyze, "record_recognition_event", _record_event)

    response = await analyze.analyze_food(
        BackgroundTasks(),
        _upload(),
        FakeSession(),
        SimpleNamespace(id="user-id"),
    )

    assert response.source == "vision"
    assert len(gate_calls) == 1
    assert len(vision_calls) == 1


async def test_enforce_food_gate_failure_fails_open_to_vision(monkeypatch) -> None:
    vision_calls: list[Path] = []
    gate_calls: list[tuple[bytes, str]] = []

    async def unavailable_gate(content: bytes, content_type: str) -> None:
        gate_calls.append((content, content_type))
        return None

    async def fake_vision(path: Path, **kwargs):
        assert kwargs == {}
        vision_calls.append(path)
        return {"dishes": []}

    monkeypatch.setattr(analyze, "settings", _enforce_settings())
    monkeypatch.setattr(analyze, "predict_food_gate", unavailable_gate, raising=False)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)
    monkeypatch.setattr(analyze, "record_recognition_event", _record_event)

    response = await analyze.analyze_food(
        BackgroundTasks(),
        _upload("gate-down.jpg"),
        FakeSession(),
        SimpleNamespace(id="user-id"),
    )

    assert response.source == "vision"
    assert len(gate_calls) == 1
    assert len(vision_calls) == 1


async def test_analyze_vision_error_is_reported_without_local_fallback(monkeypatch) -> None:
    async def local_must_not_run(*_args, **_kwargs):
        raise AssertionError("Không được gọi local image matcher")

    async def failing_vision(*_args, **_kwargs):
        raise VisionError("vision unavailable")

    monkeypatch.setattr(analyze, "_run_local_recognition", local_must_not_run, raising=False)
    monkeypatch.setattr(analyze, "identify_dish", failing_vision)

    response = await analyze.analyze_food(
        BackgroundTasks(),
        _upload("vision-down.jpg"),
        FakeSession(),
    )

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
