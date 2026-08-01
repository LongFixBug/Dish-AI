"""Unit tests cho hai nhánh DB-first / Vision-fallback của analyze."""

from io import BytesIO
from types import SimpleNamespace

from PIL import Image
from starlette.datastructures import Headers, UploadFile

from backend.api import analyze
from ml.inference.vision import UNKNOWN_CONFIDENCE, _normalize_dishes
from schemas.analyze import AnalyzeResponse
from schemas.nutrition import calculate_totals


def test_analyze_response_does_not_expose_retired_auto_add_field() -> None:
    response = AnalyzeResponse(source="vision")

    assert "auto_added_dishes" not in response.model_dump()


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


def test_cv_family_queries_include_a_plausible_second_prediction() -> None:
    queries = analyze._cv_family_queries(
        "Com Tam",
        [
            {"class_name": "Com Tam", "probability": 0.68},
            {"class_name": "Banh Mi Kep Thit", "probability": 0.2797},
            {"class_name": "Banh Xeo", "probability": 0.0144},
        ],
    )

    assert queries == ["Cơm tấm", "Bánh mì"]


async def test_high_confidence_cv_uses_db_and_skips_vision(monkeypatch) -> None:
    """CV chỉ tạo prior; Vision chốt tên trong shortlist catalog."""
    offloaded: list[str] = []
    db_dish = SimpleNamespace(
        dish_name="Bánh mì thập cẩm",
        typical_grams=150.0,
        total_calories=678.8,
        total_protein_g=25.0,
        total_fat_g=24.0,
        total_carbs_g=80.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )

    async def fake_candidates(_session, family_name):
        assert family_name == "Bánh mì"
        return [db_dish]

    async def fake_lookup(_session, name):
        assert name == "Bánh mì thập cẩm"
        return db_dish

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

    monkeypatch.setattr(analyze.cv_model, "_loaded", True)

    async def fake_to_thread(function, /, *args, **kwargs):
        offloaded.append(function.__name__)
        return function(*args, **kwargs)

    monkeypatch.setattr(analyze.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Bánh mì chảo",
            "confidence": 0.95,
            "all_predictions": [],
            "source": "local",
        },
    )
    monkeypatch.setattr(analyze, "lookup_dish_candidates", fake_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    upload = UploadFile(
        BytesIO(_jpeg_bytes()),
        filename="banh-mi.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    response = await analyze.analyze_food(upload, FakeSession())

    assert response.source == "cv_local_not_found_vision"
    assert response.dish_name == "Bánh mì thập cẩm"
    assert response.cv_confidence == 0.95
    assert response.recognition_confidence == 0.93
    assert response.nutrition is not None
    assert response.nutrition.total_grams == 150.0
    assert response.nutrition.total_calories == 678.8
    assert response.dishes[0].dish_name == "Bánh mì thập cẩm"
    assert "<lambda>" in offloaded


async def test_high_confidence_cv_falls_back_when_db_misses(monkeypatch) -> None:
    """CV chắc chắn nhưng DB miss thì Vision vẫn chịu trách nhiệm kết quả."""
    vision_dish = SimpleNamespace(
        dish_name="Phở bò",
        typical_grams=500.0,
        total_calories=450.0,
        total_protein_g=30.0,
        total_fat_g=12.0,
        total_carbs_g=60.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )
    vision_calls = 0

    async def fake_lookup(_session, name):
        return vision_dish if name == "Phở bò" else None

    async def fake_vision(_path):
        nonlocal vision_calls
        vision_calls += 1
        return {
            "dish_name": "Phở bò",
            "confidence": 0.88,
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

    monkeypatch.setattr(analyze.cv_model, "_loaded", True)
    monkeypatch.setattr(
        analyze.cv_model,
        "predict",
        lambda _path: {
            "dish_name": "Mon La",
            "confidence": 0.95,
            "all_predictions": [],
            "source": "local",
        },
    )
    async def no_candidates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(analyze, "lookup_dish_candidates", no_candidates)
    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "identify_dish", fake_vision)

    upload = UploadFile(
        BytesIO(_jpeg_bytes()),
        filename="unknown.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    response = await analyze.analyze_food(upload, FakeSession())

    assert vision_calls == 1
    assert response.source == "cv_local_not_found_vision"
    assert response.dish_name == "Phở bò"
    assert response.recognition_confidence == 0.88
    assert response.dishes[0].recognition_confidence == 0.9
    assert response.dishes[0].portion_source == "catalog_default"
    assert response.nutrition is not None


async def test_db_match_uses_canonical_name_and_ignores_vision_nutrition(
    monkeypatch,
) -> None:
    db_dish = SimpleNamespace(
        dish_name="Bánh mì thịt nướng",
        typical_grams=200.0,
        total_calories=600.0,
        total_protein_g=30.0,
        total_fat_g=20.0,
        total_carbs_g=80.0,
        total_fiber_g=6.0,
        source="vnmeal",
    )

    async def fake_lookup(_session, _name):
        return db_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)

    items, dishes, auto_added, missing = await analyze._analyze_vision_dishes(
        FakeSession(),
        [
            {
                "dish_name": "Bánh mì kẹp thịt",
                "gram": 180,
                "gram_confidence": 0.9,
                "is_side": False,
                "total_calories": 999,
                "total_protein_g": 99,
                "total_fat_g": 99,
                "total_carbs_g": 99,
                "total_fiber_g": 99,
            }
        ],
    )

    assert items[0].item_name == "Bánh mì thịt nướng"
    assert items[0].calories == 540.0
    assert items[0].protein_g == 27.0
    assert items[0].found_in_db is True
    assert dishes[0].dish_name == "Bánh mì thịt nướng"
    assert dishes[0].vision_dish_name == "Bánh mì kẹp thịt"
    assert dishes[0].found_in_db is True
    assert dishes[0].portion_source == "vision"
    assert auto_added == []
    assert missing == []


async def test_db_miss_uses_vision_values_and_stages_candidate(monkeypatch) -> None:
    saved: dict = {}

    async def fake_lookup(_session, _name):
        return None

    async def fake_stage(_session, dish_name, typical_grams, *, nutrition):
        saved.update(
            dish_name=dish_name,
            typical_grams=typical_grams,
            nutrition=nutrition,
        )
        return SimpleNamespace(id="candidate-id")

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "stage_dish_candidate", fake_stage)
    session = FakeSession()

    items, dishes, staged, missing = await analyze._analyze_vision_dishes(
        session,
        [
            {
                "dish_name": "Món mới",
                "gram": 250,
                "is_side": False,
                "total_calories": 420,
                "total_protein_g": 18,
                "total_fat_g": 12,
                "total_carbs_g": 55,
                "total_fiber_g": 4,
            }
        ],
    )

    assert items[0].model_dump() == {
        "item_name": "Món mới",
        "grams": 250.0,
        "calories": 420.0,
        "protein_g": 18.0,
        "fat_g": 12.0,
        "carbs_g": 55.0,
        "fiber_g": 4.0,
        "found_in_db": False,
        "nutrition_basis": "vision_estimate",
    }
    assert saved["dish_name"] == "Món mới"
    assert saved["typical_grams"] == 250
    assert saved["nutrition"] == items[0]
    assert dishes[0].found_in_db is False
    assert staged == ["Món mới"]
    assert missing == []
    assert session.commits == 1


async def test_empty_db_record_sends_vision_values_to_staging(monkeypatch) -> None:
    empty_dish = SimpleNamespace(
        id="existing-dish-id",
        dish_name="Bánh mì thịt",
        typical_grams=200.0,
        total_calories=0.0,
        total_protein_g=0.0,
        total_fat_g=0.0,
        total_carbs_g=0.0,
        total_fiber_g=0.0,
        source="vnmeal",
    )
    saved: dict = {}

    async def fake_lookup(_session, _name):
        return empty_dish

    async def fake_stage(_session, dish_name, typical_grams, *, nutrition):
        saved.update(dish_name=dish_name, nutrition=nutrition)
        return empty_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "stage_dish_candidate", fake_stage)

    items, dishes, staged, _ = await analyze._analyze_vision_dishes(
        FakeSession(),
        [
            {
                "dish_name": "Bánh mì kẹp thịt",
                "gram": 180,
                "total_calories": 500,
                "total_protein_g": 22,
                "total_fat_g": 18,
                "total_carbs_g": 62,
                "total_fiber_g": 4,
            }
        ],
    )

    assert items[0].item_name == "Bánh mì thịt"
    assert items[0].calories == 500.0
    assert items[0].found_in_db is False
    assert dishes[0].dish_name == "Bánh mì thịt"
    assert dishes[0].vision_dish_name == "Bánh mì kẹp thịt"
    assert saved["dish_name"] == "Bánh mì thịt"
    assert saved["nutrition"] == items[0]
    assert staged == ["Bánh mì thịt"]


async def test_side_item_does_not_use_semantic_dish_or_ingredient_match(
    monkeypatch,
) -> None:
    async def fake_exact_dish(_session, _name):
        return None

    async def fake_text_ingredient(_session, _name):
        return None

    async def semantic_lookup_must_not_run(_session, _name):
        raise AssertionError("Món phụ không được semantic-match sang món khác")

    monkeypatch.setattr(analyze, "lookup_dish_exact", fake_exact_dish)
    monkeypatch.setattr(analyze, "lookup_ingredient_text", fake_text_ingredient)
    monkeypatch.setattr(analyze, "lookup_dish", semantic_lookup_must_not_run)

    item, resolved_name, _ = await analyze._resolve_dish_item(
        FakeSession(), "Trứng ốp la", 50, True
    )

    assert item is None
    assert resolved_name == "Trứng ốp la"


async def test_known_dish_uses_catalog_portion_when_vision_omits_grams(
    monkeypatch,
) -> None:
    """A missing Vision weight must not turn trusted nutrition into zeroes."""
    db_dish = SimpleNamespace(
        dish_name="Cơm sườn",
        typical_grams=400.0,
        total_calories=640.0,
        total_protein_g=28.0,
        total_fat_g=20.0,
        total_carbs_g=90.0,
        total_fiber_g=4.0,
        source="vnmeal",
    )

    async def fake_lookup(_session, _name):
        return db_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)

    item, resolved_name, _ = await analyze._resolve_dish_item(
        FakeSession(), "Cơm sườn", 0.0, False
    )

    assert resolved_name == "Cơm sườn"
    assert item is not None
    assert item.grams == 400.0
    assert item.calories == 640.0
    assert item.nutrition_basis == "per_gram_scaled"


async def test_banh_mi_ignores_overweight_vision_portion(
    monkeypatch,
) -> None:
    db_dish = SimpleNamespace(
        dish_name="Bánh mì thập cẩm",
        typical_grams=200.0,
        total_calories=678.8,
        total_protein_g=25.0,
        total_fat_g=24.0,
        total_carbs_g=80.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )

    async def fake_lookup(_session, _name):
        return db_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)

    items, dishes, _, _ = await analyze._analyze_vision_dishes(
        FakeSession(),
        [
            {
                "dish_name": "Bánh mì thập cẩm",
                "gram": 250.0,
                "gram_confidence": 0.95,
                "is_side": False,
                "confidence": 0.95,
            }
        ],
    )

    assert items[0].grams == 200.0
    assert items[0].calories == 678.8
    assert dishes[0].portion_source == "catalog_default"


async def test_banh_mi_uses_visual_portion_inside_safe_range(
    monkeypatch,
) -> None:
    db_dish = SimpleNamespace(
        dish_name="Bánh mì thập cẩm",
        typical_grams=200.0,
        total_calories=678.8,
        total_protein_g=25.0,
        total_fat_g=24.0,
        total_carbs_g=80.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )

    async def fake_lookup(_session, _name):
        return db_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)

    items, dishes, _, _ = await analyze._analyze_vision_dishes(
        FakeSession(),
        [
            {
                "dish_name": "Bánh mì thập cẩm",
                "gram": 175.0,
                "gram_confidence": 0.9,
                "is_side": False,
                "confidence": 0.95,
            }
        ],
    )

    assert items[0].grams == 175.0
    assert items[0].calories == 593.9
    assert dishes[0].portion_source == "vision"


async def test_missing_weight_does_not_persist_vision_estimate(monkeypatch) -> None:
    """A single image estimate must not mutate an institute nutrition record."""
    db_dish = SimpleNamespace(
        dish_name="Canh rau",
        typical_grams=None,
        total_calories=80.0,
        total_protein_g=4.0,
        total_fat_g=2.0,
        total_carbs_g=12.0,
        total_fiber_g=3.0,
        source="vnmeal",
    )
    async def fake_lookup(_session, _name):
        return db_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    session = FakeSession()

    item, resolved_name, _ = await analyze._resolve_dish_item(
        session, "Canh rau", 350.0, False
    )

    assert resolved_name == "Canh rau"
    assert item is not None
    # Không gán 350 g của Vision vào đây: con số đó không tham gia phép tính,
    # gán vào sẽ ngụ ý mật độ 0.23 kcal/g và làm hỏng bộ chỉnh khẩu phần.
    assert item.grams == 0.0
    assert item.calories == 80.0
    assert item.nutrition_basis == "source_serving"
    totals = calculate_totals("Canh rau", [item])
    assert totals.per_100g_available is False
    assert totals.per_100g_calories == 0.0
    assert session.commits == 0


async def test_unknown_dish_without_usable_nutrition_is_not_staged(
    monkeypatch,
) -> None:
    """Zero-filled Vision output is not useful catalog evidence or a valid result."""

    async def fake_lookup(_session, _name):
        return None

    async def stage_must_not_run(*_args, **_kwargs):
        raise AssertionError("Không được stage candidate toàn số 0")

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "stage_dish_candidate", stage_must_not_run)

    items, dishes, staged, missing = await analyze._analyze_vision_dishes(
        FakeSession(),
        [
            {
                "dish_name": "Món chưa rõ",
                "gram": 0,
                "is_side": False,
                "confidence": 0.8,
                "total_calories": 0,
                "total_protein_g": 0,
                "total_fat_g": 0,
                "total_carbs_g": 0,
                "total_fiber_g": 0,
            }
        ],
    )

    assert items == []
    assert dishes[0].found_in_db is False
    assert staged == []
    assert missing == ["Món chưa rõ"]


def test_normalize_vision_dishes_keeps_nutrition_and_calorie_alias() -> None:
    dishes = _normalize_dishes(
        [
            {
                "dish_name": "Phở bò",
                "grams": "500",
                "is_main": True,
                "total_calories_g": "450",
                "total_protein_g": "30",
                "total_fat_g": "bad-value",
                "total_carbs_g": 60,
                "total_fiber_g": 3,
            }
        ]
    )

    assert dishes == [
        {
            "dish_name": "Phở bò",
            "gram": 500.0,
            "is_side": False,
            # Model không trả confidence → UNKNOWN_CONFIDENCE, KHÔNG phải 1.0.
            "confidence": UNKNOWN_CONFIDENCE,
            "total_calories": 450.0,
            "total_protein_g": 30.0,
            "total_fat_g": 0.0,
            "total_carbs_g": 60.0,
            "total_fiber_g": 3.0,
        }
    ]


async def test_side_ingredient_without_grams_is_not_a_zero_calorie_db_hit(
    monkeypatch,
) -> None:
    """Nguyên liệu không có gram phải rơi vào 'missing', không phải item 0 kcal.

    vn_ingredients chỉ có số liệu theo gram, không có khẩu phần chuẩn để
    fallback. Trả về item toàn số 0 nhưng gắn found_in_db=True khiến bữa ăn
    thiếu calo trong khi API vẫn báo phủ 100% catalog.
    """
    ingredient = SimpleNamespace(
        ingredient_name="Sữa tươi",
        calories_per_g=0.061,
        protein_per_g=0.0032,
        fat_per_g=0.0033,
        carbs_per_g=0.0047,
        fiber_per_g=0.0,
    )

    async def fake_exact_dish(_session, _name):
        return None

    async def fake_text_ingredient(_session, _name):
        return ingredient

    monkeypatch.setattr(analyze, "lookup_dish_exact", fake_exact_dish)
    monkeypatch.setattr(analyze, "lookup_ingredient_text", fake_text_ingredient)

    item, resolved_name, portion_source = await analyze._resolve_dish_item(
        FakeSession(), "Sữa tươi", 0.0, True
    )

    assert item is None
    assert resolved_name == "Sữa tươi"
    assert portion_source == "unknown"


async def test_side_ingredient_with_grams_still_resolves(monkeypatch) -> None:
    ingredient = SimpleNamespace(
        ingredient_name="Sữa tươi",
        calories_per_g=0.061,
        protein_per_g=0.0032,
        fat_per_g=0.0033,
        carbs_per_g=0.0047,
        fiber_per_g=0.0,
        source="usda",
    )

    async def fake_exact_dish(_session, _name):
        return None

    async def fake_text_ingredient(_session, _name):
        return ingredient

    monkeypatch.setattr(analyze, "lookup_dish_exact", fake_exact_dish)
    monkeypatch.setattr(analyze, "lookup_ingredient_text", fake_text_ingredient)

    item, _, portion_source = await analyze._resolve_dish_item(
        FakeSession(), "Sữa tươi", 200.0, True
    )

    assert item is not None
    assert item.grams == 200.0
    assert item.calories > 0
    assert portion_source == "vision"


async def test_staging_failure_counts_the_item_once(monkeypatch) -> None:
    """Item hỏng lúc stage chỉ được đếm một lần, nếu không confidence_score sai."""

    async def fake_lookup(_session, _name):
        return None

    async def failing_stage(*_args, **_kwargs):
        raise RuntimeError("unique key race")

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "stage_dish_candidate", failing_stage)

    items, _, staged, missing = await analyze._analyze_vision_dishes(
        FakeSession(),
        [
            {
                "dish_name": "Món lạ",
                "gram": 200.0,
                "is_side": False,
                "confidence": 0.9,
                "total_calories": 300.0,
                "total_protein_g": 10.0,
                "total_fat_g": 5.0,
                "total_carbs_g": 40.0,
                "total_fiber_g": 2.0,
            }
        ],
    )

    assert staged == []
    assert len(items) == 1
    assert missing == []
    totals = calculate_totals("Món lạ", items, missing)
    # 1 item, 0 missing → mẫu số là 1 chứ không phải 2.
    assert totals.confidence_score == 0.0


async def test_vision_dish_rejects_catalog_row_that_morphs_the_name(monkeypatch) -> None:
    """Nhánh Vision cũng phải soi tên như nhánh album, không tin bừa catalog.

    Semantic search trả "Bánh cuốn thịt" cho "Bánh mì kẹp thịt": tên rơi mất
    "mì", tức món khác hẳn. Nhánh album đã chặn bằng is_name_refinement, nhánh
    Vision thì chưa nên số liệu bánh cuốn từng hiện lên app kèm nhãn
    "Dữ liệu catalog: 100%".
    """
    morphed = SimpleNamespace(
        dish_name="Bánh cuốn thịt",
        typical_grams=150.0,
        total_calories=440.0,
        total_protein_g=16.7,
        total_fat_g=18.5,
        total_carbs_g=51.5,
        total_fiber_g=1.0,
        source="vnmeal",
    )

    async def fake_lookup(_session, name):
        assert name == "Bánh mì kẹp thịt"
        return morphed

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)

    item, resolved_name, portion_source = await analyze._resolve_dish_item(
        FakeSession(),
        "Bánh mì kẹp thịt",
        gram=150.0,
        is_side=False,
    )

    assert item is None
    assert resolved_name == "Bánh mì kẹp thịt"
    assert portion_source == "unknown"


async def test_vision_dish_keeps_catalog_row_that_only_refines_the_name(monkeypatch) -> None:
    """Ngược lại, mở rộng hợp lệ vẫn phải dùng số liệu catalog."""
    refined = SimpleNamespace(
        dish_name="Phở bò chín",
        typical_grams=400.0,
        total_calories=440.0,
        total_protein_g=25.0,
        total_fat_g=10.0,
        total_carbs_g=60.0,
        total_fiber_g=2.0,
        source="vnmeal",
    )

    async def fake_lookup(_session, _name):
        return refined

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)

    item, resolved_name, _ = await analyze._resolve_dish_item(
        FakeSession(),
        "Phở bò",
        gram=400.0,
        is_side=False,
    )

    assert item is not None
    assert resolved_name == "Phở bò chín"
