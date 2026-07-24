"""Unit tests cho hai nhánh DB-first / Vision-fallback của analyze."""

from types import SimpleNamespace

from backend.api import analyze
from ml.inference.vision import _normalize_dishes


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


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
                "gram": 100,
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
    assert items[0].calories == 300.0
    assert items[0].protein_g == 15.0
    assert items[0].found_in_db is True
    assert dishes[0].dish_name == "Bánh mì thịt nướng"
    assert dishes[0].vision_dish_name == "Bánh mì kẹp thịt"
    assert dishes[0].found_in_db is True
    assert auto_added == []
    assert missing == []


async def test_db_miss_uses_and_saves_all_vision_values(monkeypatch) -> None:
    saved: dict = {}

    async def fake_lookup(_session, _name):
        return None

    async def fake_auto_add(_session, dish_name, typical_grams, *, nutrition):
        saved.update(
            dish_name=dish_name,
            typical_grams=typical_grams,
            nutrition=nutrition,
        )
        return SimpleNamespace(id="new-dish-id")

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "auto_add_dish", fake_auto_add)
    session = FakeSession()

    items, dishes, auto_added, missing = await analyze._analyze_vision_dishes(
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
    }
    assert saved["dish_name"] == "Món mới"
    assert saved["typical_grams"] == 250
    assert saved["nutrition"] == items[0]
    assert dishes[0].found_in_db is False
    assert auto_added == ["Món mới"]
    assert missing == []
    assert session.commits == 1


async def test_empty_db_record_is_refilled_from_vision(monkeypatch) -> None:
    empty_dish = SimpleNamespace(
        dish_name="Bánh mì thịt",
        typical_grams=200.0,
        total_calories=0.0,
        total_protein_g=0.0,
        total_fat_g=0.0,
        total_carbs_g=0.0,
        total_fiber_g=0.0,
        source="vision_auto",
    )
    saved: dict = {}

    async def fake_lookup(_session, _name):
        return empty_dish

    async def fake_auto_add(_session, dish_name, typical_grams, *, nutrition):
        saved.update(dish_name=dish_name, nutrition=nutrition)
        return empty_dish

    monkeypatch.setattr(analyze, "lookup_dish", fake_lookup)
    monkeypatch.setattr(analyze, "auto_add_dish", fake_auto_add)

    items, dishes, auto_added, _ = await analyze._analyze_vision_dishes(
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
    assert auto_added == ["Bánh mì thịt"]


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

    item, resolved_name = await analyze._resolve_dish_item(
        FakeSession(), "Trứng ốp la", 50, True
    )

    assert item is None
    assert resolved_name == "Trứng ốp la"


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
            "total_calories": 450.0,
            "total_protein_g": 30.0,
            "total_fat_g": 0.0,
            "total_carbs_g": 60.0,
            "total_fiber_g": 3.0,
        }
    ]
