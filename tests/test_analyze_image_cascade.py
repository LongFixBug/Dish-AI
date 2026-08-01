"""Tests cho nhánh image-knn cascade của analyze (album ảnh tham chiếu).

Cùng convention với test_analyze_dish_flow.py: gọi thẳng analyze_food với
FakeSession + monkeypatch các attribute trong module analyze.
"""

from io import BytesIO
import asyncio
import threading
from types import SimpleNamespace

import httpx
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from backend.api import analyze
from backend.config import settings
from backend.services import recognition_cascade
from backend.services.dish_image_index import DishCandidateScore
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


def _pho_bo_row() -> SimpleNamespace:
    return SimpleNamespace(
        id="dish-pho-bo",
        dish_name="Phở bò",
        typical_grams=500.0,
        total_calories=450.0,
        total_protein_g=30.0,
        total_fat_g=12.0,
        total_carbs_g=60.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )


def test_fusion_cv_gate_can_be_stricter_than_checkpoint_serving_threshold(
    monkeypatch,
) -> None:
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.996)
    monkeypatch.setattr(settings, "local_fusion_cv_threshold", 0.998)

    assert analyze._is_cv_fusion_high_conf(0.997, "Phở bò") is False
    assert analyze._is_cv_fusion_high_conf(0.998, "Phở bò") is True


async def test_local_recognizers_start_in_parallel(monkeypatch, tmp_path) -> None:
    """Album async và CV blocking phải cùng khởi động trước khi một bên xong."""
    album_started = asyncio.Event()
    cv_started = threading.Event()
    release = threading.Event()

    async def fake_image_candidates(_image_bytes):
        album_started.set()
        assert await asyncio.to_thread(release.wait, 1.0)
        return []

    def fake_predict(_path):
        cv_started.set()
        assert release.wait(1.0)
        return {
            "dish_name": None,
            "confidence": 0.0,
            "all_predictions": [],
            "source": "fallback_required",
        }

    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "predict", fake_predict)
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)

    task = asyncio.create_task(
        analyze._run_local_recognition(b"jpeg", tmp_path / "upload.jpg")
    )
    await asyncio.wait_for(album_started.wait(), timeout=1.0)
    for _ in range(100):
        if cv_started.is_set():
            break
        await asyncio.sleep(0.001)

    assert cv_started.is_set()
    assert not task.done()
    release.set()
    album_candidates, cv_result = await asyncio.wait_for(task, timeout=1.0)

    assert album_candidates == []
    assert cv_result["source"] == "fallback_required"


async def test_cv_failure_degrades_to_album_or_vision(monkeypatch, tmp_path) -> None:
    async def no_image_candidates(_image_bytes):
        return []

    def failing_predict(_path):
        raise RuntimeError("checkpoint inference failed")

    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "predict", failing_predict)
    monkeypatch.setattr(analyze, "image_candidates", no_image_candidates)

    album_candidates, cv_result = await analyze._run_local_recognition(
        b"jpeg",
        tmp_path / "upload.jpg",
    )

    assert album_candidates == []
    assert cv_result == {
        "dish_name": None,
        "confidence": 0.0,
        "all_predictions": [],
        "source": "fallback_required",
    }


async def test_fusion_consensus_uses_catalog_and_skips_vision(monkeypatch) -> None:
    db_dish = _pho_bo_row()

    async def fake_image_candidates(_image_bytes):
        return [DishCandidateScore(dish_name="Pho bo", best_score=0.97, votes=5)]

    async def fake_lookup(_session, name):
        assert name in {"Pho bo", "Phở bò"}
        return db_dish

    async def vision_must_not_run(*_args, **_kwargs):
        raise AssertionError("Vision không được gọi khi hai local model đồng thuận")

    captured: dict[str, object] = {}

    async def fake_record(_session, **kwargs):
        captured.update(kwargs)
        return "00000000-0000-0000-0000-000000000123"

    monkeypatch.setattr(settings, "local_fusion_enabled", True)
    monkeypatch.setattr(settings, "local_fusion_cv_threshold", 0.85)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.85)
    monkeypatch.setattr(analyze.cv_model, "model_version", "cv-test-v1")
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Phở bò",
            "confidence": 0.95,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", vision_must_not_run)
    monkeypatch.setattr(analyze, "record_recognition_event", fake_record)

    response = await analyze.analyze_food(
        _upload("pho-consensus.jpg"),
        FakeSession(),
        SimpleNamespace(id="00000000-0000-0000-0000-000000000001"),
    )

    assert response.source == "local_consensus"
    assert response.dish_name == "Phở bò"
    assert response.cv_confidence == 0.95
    assert response.recognition_confidence == 0.95
    assert response.model_version == f"cv-test-v1+{settings.image_embed_model}"
    assert response.nutrition is not None
    assert response.nutrition.total_calories == 450.0
    assert response.recognition_event_id == "00000000-0000-0000-0000-000000000123"
    assert captured["cv_dish_name"] == "Phở bò"
    assert captured["album_dish_name"] == "Pho bo"


async def test_fusion_disagreement_sends_union_to_vision(monkeypatch) -> None:
    bun_rieu = SimpleNamespace(
        **{
            **_pho_bo_row().__dict__,
            "id": "dish-bun-rieu",
            "dish_name": "Bún riêu",
        }
    )
    bun_bo = SimpleNamespace(
        **{
            **_pho_bo_row().__dict__,
            "id": "dish-bun-bo-hue",
            "dish_name": "Bún bò Huế",
        }
    )
    vision_calls = 0

    async def fake_image_candidates(_image_bytes):
        return [DishCandidateScore(dish_name="Bún bò Huế", best_score=0.96, votes=4)]

    async def fake_lookup(_session, name):
        return {
            "Bún riêu": bun_rieu,
            "Bún bò Huế": bun_bo,
        }.get(name)

    async def fake_catalog_candidates(_session, _family_name):
        return [bun_rieu]

    async def fake_vision(_path, *, candidate_names):
        nonlocal vision_calls
        vision_calls += 1
        assert candidate_names[:2] == ["Bún bò Huế", "Bún riêu"]
        return {
            "dish_name": "Bún riêu",
            "confidence": 0.91,
            "dishes": [
                {
                    "dish_name": "Bún riêu",
                    "gram": 500.0,
                    "is_side": False,
                    "confidence": 0.91,
                    "total_calories": 0.0,
                    "total_protein_g": 0.0,
                    "total_fat_g": 0.0,
                    "total_carbs_g": 0.0,
                    "total_fiber_g": 0.0,
                }
            ],
            "reasoning": "Không thấy đặc trưng của bún bò Huế.",
        }

    monkeypatch.setattr(settings, "local_fusion_enabled", True)
    monkeypatch.setattr(settings, "local_fusion_cv_threshold", 0.85)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.85)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Bún riêu",
            "confidence": 0.92,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "lookup_dish_candidates", fake_catalog_candidates)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_food(_upload("bun-disagree.jpg"), FakeSession())

    assert vision_calls == 1
    assert response.dish_name == "Bún riêu"
    assert response.source == "cv_local_not_found_vision"


async def test_fusion_disagreement_does_not_elevate_cv_when_vision_fails(
    monkeypatch,
) -> None:
    rows = {
        "Bún riêu": SimpleNamespace(id="dish-bun-rieu", dish_name="Bún riêu"),
        "Bún bò Huế": SimpleNamespace(
            id="dish-bun-bo-hue",
            dish_name="Bún bò Huế",
        ),
    }

    async def fake_image_candidates(_image_bytes):
        return [DishCandidateScore(dish_name="Bún bò Huế", best_score=0.96, votes=4)]

    async def fake_lookup(_session, name):
        return rows.get(name)

    async def no_catalog_candidates(*_args, **_kwargs):
        return []

    async def failing_vision(_path, *, candidate_names):
        assert candidate_names == ["Bún bò Huế", "Bún riêu"]
        raise VisionError("cloud unavailable")

    monkeypatch.setattr(settings, "local_fusion_enabled", True)
    monkeypatch.setattr(settings, "local_fusion_cv_threshold", 0.85)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.85)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Bún riêu",
            "confidence": 0.92,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "lookup_dish_candidates", no_catalog_candidates)
    monkeypatch.setattr(analyze, "identify_dish", failing_vision)

    response = await analyze.analyze_food(_upload("vision-down.jpg"), FakeSession())

    assert response.source == "vision"
    assert response.dish_name is None
    assert response.error is not None


async def test_fusion_cv_solo_requires_configured_threshold(monkeypatch) -> None:
    db_dish = _pho_bo_row()

    async def no_image_candidates(_image_bytes):
        return []

    async def fake_lookup(_session, name):
        assert name == "Phở bò"
        return db_dish

    async def vision_must_not_run(*_args, **_kwargs):
        raise AssertionError("CV đã qua solo gate nên không gọi Vision")

    monkeypatch.setattr(settings, "local_fusion_enabled", True)
    monkeypatch.setattr(settings, "local_fusion_cv_threshold", 0.85)
    monkeypatch.setattr(settings, "cv_solo_confidence_threshold", 0.95)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.85)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Phở bò",
            "confidence": 0.97,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", no_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", vision_must_not_run)

    response = await analyze.analyze_food(_upload("pho-cv-solo.jpg"), FakeSession())

    assert response.source == "cv_local"
    assert response.dish_name == "Phở bò"
    assert response.cv_confidence == 0.97


async def test_album_only_match_defers_when_album_solo_is_disabled(monkeypatch) -> None:
    db_dish = _pho_bo_row()

    async def image_match(_image_bytes):
        return [DishCandidateScore(dish_name="Phở bò", best_score=0.95, votes=4)]

    async def fake_lookup(_session, name):
        return db_dish if name == "Phở bò" else None

    async def no_catalog_candidates(*_args, **_kwargs):
        return []

    async def fake_vision(_path, **_kwargs):
        return {
            "dish_name": "Phở bò",
            "confidence": 0.9,
            "dishes": [{"dish_name": "Phở bò", "gram": 0, "is_side": False}],
        }

    monkeypatch.setattr(settings, "local_fusion_enabled", True)
    monkeypatch.setattr(settings, "local_fusion_album_solo_enabled", False)
    monkeypatch.setattr(settings, "local_fusion_cv_threshold", 0.999)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {"dish_name": "Phở bò", "confidence": 0.90, "all_predictions": []},
    )
    monkeypatch.setattr(analyze, "image_candidates", image_match)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "lookup_dish_candidates", no_catalog_candidates)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_food(_upload(), FakeSession())

    assert response.source == "cv_local_not_found_vision"


async def test_shadow_disagreement_preserves_legacy_album_answer(monkeypatch) -> None:
    """Shadow chỉ log quyết định mới, chưa đổi response của user."""
    album_dish = _pho_bo_row()
    cv_dish = SimpleNamespace(
        **{
            **album_dish.__dict__,
            "id": "dish-bun-rieu",
            "dish_name": "Bún riêu",
        }
    )

    async def fake_image_candidates(_image_bytes):
        return [DishCandidateScore(dish_name="Phở bò", best_score=0.97, votes=5)]

    async def fake_lookup(_session, name):
        return {"Phở bò": album_dish, "Bún riêu": cv_dish}.get(name)

    async def vision_must_not_run(*_args, **_kwargs):
        raise AssertionError("Shadow phải giữ hành vi image_knn cũ")

    monkeypatch.setattr(settings, "local_fusion_enabled", False)
    monkeypatch.setattr(settings, "local_fusion_shadow_enabled", True)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.85)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Bún riêu",
            "confidence": 0.95,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", vision_must_not_run)

    response = await analyze.analyze_food(_upload("shadow.jpg"), FakeSession())

    assert response.source == "image_knn"
    assert response.dish_name == "Phở bò"


async def test_shadow_does_not_change_legacy_vision_candidates(monkeypatch) -> None:
    """Shadow evidence is observable in logs, but must not steer Qwen yet."""
    cv_row = SimpleNamespace(id="dish-bun-rieu", dish_name="Bún riêu")

    async def weak_image_candidates(_image_bytes):
        return [
            DishCandidateScore(
                dish_name="Phở bò",
                best_score=settings.image_match_threshold - 0.1,
                votes=1,
            )
        ]

    async def fake_lookup(_session, name):
        return cv_row if name == "Bún riêu" else None

    async def no_catalog_candidates(*_args, **_kwargs):
        return []

    async def fake_vision(_path, *, candidate_names):
        assert candidate_names == ["Phở bò"]
        return {"dish_name": None, "confidence": 0.0, "dishes": []}

    monkeypatch.setattr(settings, "local_fusion_enabled", False)
    monkeypatch.setattr(settings, "local_fusion_shadow_enabled", True)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(analyze.cv_model, "serving_threshold", 0.85)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Bún riêu",
            "confidence": 0.92,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", weak_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "lookup_dish_candidates", no_catalog_candidates)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_food(_upload("shadow-vision.jpg"), FakeSession())

    assert response.source == "vision"
    assert response.error is not None


async def test_cascade_resolved_answers_without_vision_when_cv_unavailable(
    monkeypatch,
) -> None:
    """CV unavailable vẫn để album mạnh trả catalog mà không gọi Vision."""
    db_dish = _pho_bo_row()

    async def fake_image_candidates(_image_bytes):
        return [
            DishCandidateScore(dish_name="Phở bò", best_score=0.97, votes=5),
            DishCandidateScore(dish_name="Phở gà", best_score=0.82, votes=2),
        ]

    async def fake_lookup(_session, name):
        assert name == "Phở bò"
        return db_dish

    async def vision_must_not_run(*_args, **_kwargs):
        raise AssertionError("Vision không được gọi khi cascade đã resolve")

    monkeypatch.setattr(analyze.cv_model, "_loaded", False)
    monkeypatch.setattr(settings, "local_fusion_album_solo_enabled", True)
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", vision_must_not_run)

    response = await analyze.analyze_food(_upload("pho.jpg"), FakeSession())

    assert response.source == "image_knn"
    assert response.dish_name == "Phở bò"
    assert response.model_version == settings.image_embed_model
    assert response.recognition_confidence == 0.97
    assert response.cv_confidence is None
    assert response.nutrition is not None
    assert response.nutrition.total_grams == 500.0
    assert response.nutrition.total_calories == 450.0
    assert len(response.dishes) == 1
    assert response.dishes[0].dish_name == "Phở bò"
    assert response.dishes[0].found_in_db is True
    assert response.dishes[0].is_side is False
    assert response.dishes[0].portion_source == "catalog_default"
    assert response.dishes[0].recognition_confidence == 0.97


async def test_cascade_hit_without_catalog_row_falls_back_to_vision(
    monkeypatch,
) -> None:
    """Tên album không tra được trong catalog → KHÔNG tin, rơi về Vision."""
    db_dish = _pho_bo_row()
    vision_calls = 0

    async def fake_image_candidates(_image_bytes):
        return [DishCandidateScore(dish_name="Món ma", best_score=0.99, votes=3)]

    async def fake_lookup(_session, name):
        return db_dish if name == "Phở bò" else None

    async def fake_vision(_path, *, candidate_names):
        nonlocal vision_calls
        vision_calls += 1
        # Tên do album gợi ý vẫn được đưa vào prompt dù không resolve được.
        assert candidate_names == ["Món ma"]
        return {
            "dish_name": "Phở bò",
            "confidence": 0.9,
            "dishes": [
                {
                    "dish_name": "Phở bò",
                    "gram": 500.0,
                    "is_side": False,
                    "confidence": 0.9,
                    "total_calories": 0.0,
                    "total_protein_g": 0.0,
                    "total_fat_g": 0.0,
                    "total_carbs_g": 0.0,
                    "total_fiber_g": 0.0,
                }
            ],
            "reasoning": None,
        }

    monkeypatch.setattr(analyze.cv_model, "_loaded", False)
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_food(_upload(), FakeSession())

    assert vision_calls == 1
    assert response.source == "vision"
    assert response.dish_name == "Phở bò"


async def test_low_score_candidates_lead_vision_prompt(monkeypatch) -> None:
    """Album chưa đủ điểm → tên album đứng TRƯỚC tên CV/Qdrant, khử trùng dấu."""
    banh_mi = SimpleNamespace(
        dish_name="Bánh mì thập cẩm",
        typical_grams=150.0,
        total_calories=678.8,
        total_protein_g=25.0,
        total_fat_g=24.0,
        total_carbs_g=80.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )

    async def fake_image_candidates(_image_bytes):
        # Điểm dưới settings.image_match_threshold để chắc chắn không resolve,
        # dù ngưỡng mặc định có được tune lại.
        low = settings.image_match_threshold - 0.10
        return [
            DishCandidateScore(dish_name="Phở bò", best_score=low, votes=3),
            DishCandidateScore(dish_name="Bún chả", best_score=low - 0.05, votes=1),
        ]

    async def fake_candidates(_session, family_name):
        assert family_name == "Bánh mì"
        # "Pho bo" (không dấu) phải bị khử vì trùng "Phở bò" từ album.
        return [banh_mi, SimpleNamespace(dish_name="Pho bo")]

    async def fake_lookup(_session, name):
        assert name == "Bánh mì thập cẩm"
        return banh_mi

    async def fake_vision(_path, *, candidate_names):
        assert candidate_names == ["Phở bò", "Bún chả", "Bánh mì thập cẩm"]
        return {
            "dish_name": "Bánh mì thập cẩm",
            "confidence": 0.93,
            "dishes": [
                {
                    "dish_name": "Bánh mì thập cẩm",
                    "gram": 150.0,
                    "is_side": False,
                    "confidence": 0.93,
                    "total_calories": 0.0,
                    "total_protein_g": 0.0,
                    "total_fat_g": 0.0,
                    "total_carbs_g": 0.0,
                    "total_fiber_g": 0.0,
                }
            ],
            "reasoning": None,
        }

    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Banh Mi Kep Thit",
            "confidence": 0.95,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "image_candidates", fake_image_candidates)
    monkeypatch.setattr(analyze, "lookup_dish_candidates", fake_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_food(_upload("banh-mi.jpg"), FakeSession())

    assert response.source == "cv_local_not_found_vision"
    assert response.dish_name == "Bánh mì thập cẩm"


async def test_sidecar_down_keeps_pre_cascade_behavior(monkeypatch) -> None:
    """Sidecar sập: Vision nhận đúng shortlist catalog như trước khi có cascade.

    Không patch image_candidates — để hàm thật nuốt lỗi ConnectError và trả [].
    """
    monkeypatch.setattr(settings, "image_embed_enabled", True)
    banh_mi = SimpleNamespace(
        dish_name="Bánh mì thập cẩm",
        typical_grams=150.0,
        total_calories=678.8,
        total_protein_g=25.0,
        total_fat_g=24.0,
        total_carbs_g=80.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )

    async def failing_embed(_data: bytes) -> list[float]:
        raise httpx.ConnectError("sidecar down")

    async def fake_candidates(_session, family_name):
        assert family_name == "Bánh mì"
        return [banh_mi]

    async def fake_lookup(_session, name):
        assert name == "Bánh mì thập cẩm"
        return banh_mi

    async def fake_vision(_path, *, candidate_names):
        assert candidate_names == ["Bánh mì thập cẩm"]
        return {
            "dish_name": "Bánh mì thập cẩm",
            "confidence": 0.93,
            "dishes": [
                {
                    "dish_name": "Bánh mì thập cẩm",
                    "gram": 150.0,
                    "is_side": False,
                    "confidence": 0.93,
                    "total_calories": 0.0,
                    "total_protein_g": 0.0,
                    "total_fat_g": 0.0,
                    "total_carbs_g": 0.0,
                    "total_fiber_g": 0.0,
                }
            ],
            "reasoning": None,
        }

    monkeypatch.setattr(recognition_cascade, "embed_image", failing_embed)
    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Banh Mi Kep Thit",
            "confidence": 0.95,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "lookup_dish_candidates", fake_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    response = await analyze.analyze_food(_upload("banh-mi.jpg"), FakeSession())

    assert response.source == "cv_local_not_found_vision"
    assert response.dish_name == "Bánh mì thập cẩm"
    assert response.cv_confidence == 0.95
    assert response.recognition_confidence == 0.93
    assert response.nutrition is not None
    assert response.nutrition.total_calories == 678.8
