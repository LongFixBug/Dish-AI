"""Tests cho nhánh image-knn cascade của analyze (album ảnh tham chiếu).

Cùng convention với test_analyze_dish_flow.py: gọi thẳng analyze_food với
FakeSession + monkeypatch các attribute trong module analyze.
"""

from io import BytesIO
from types import SimpleNamespace

import httpx
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from backend.api import analyze
from backend.config import settings
from backend.services import recognition_cascade
from backend.services.dish_image_index import DishCandidateScore


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
        dish_name="Phở bò",
        typical_grams=500.0,
        total_calories=450.0,
        total_protein_g=30.0,
        total_fat_g=12.0,
        total_carbs_g=60.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )


async def test_cascade_resolved_answers_without_vision_or_cv(monkeypatch) -> None:
    """Album match đủ tự tin → trả lời từ catalog, không gọi Vision lẫn CV."""
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
