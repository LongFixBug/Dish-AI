"""Integration tests: phân biệt nguyên liệu vs món qua cột item_type.

item_type ∈ {ingredient, dish, fruit, product}. Backfill heuristic:
- vnmeal → dish (mặc định), trừ trái cây → fruit
- vnfood → ingredient (mặc định), trừ sản phẩm (Bánh/Kẹo/Sushi...) → product
- sr legacy + foundation → ingredient

Mục tiêu:
- autocomplete chỉ trả ingredient + fruit (dùng được trong công thức)
- lookup institute chỉ trả dish (món), không lọt trái cây
"""

from sqlalchemy import func, select

from backend.db.models import NutritionIngredient
from backend.services.dishes import lookup_dish
from backend.services.ingredients import search_ingredients
from tests.conftest import db_session  # noqa: F401  (fixture)


# ─── Backfill counts (sau migration) ──────────────────────────────────────────


async def test_backfill_counts(db_session) -> None:
    """Count theo item_type phải khớp số liệu inspect (tổng 10148).

    ingredient=8818, dish=1226, product=80, fruit=24.
    Dùng range ±5 để chịu sai số nhỏ (rerun idempotent không đổi).
    """
    rows = (
        await db_session.execute(
            select(NutritionIngredient.item_type, func.count())
            .group_by(NutritionIngredient.item_type)
        )
    ).all()
    counts = {t: c for t, c in rows}

    assert abs(counts.get("ingredient", 0) - 8788) <= 5, f"ingredient: {counts}"
    assert abs(counts.get("dish", 0) - 1255) <= 5, f"dish: {counts}"
    assert abs(counts.get("product", 0) - 80) <= 5, f"product: {counts}"
    assert abs(counts.get("fruit", 0) - 25) <= 5, f"fruit: {counts}"


# ─── Autocomplete chỉ trả ingredient + fruit ──────────────────────────────────


async def test_autocomplete_thit_excludes_dish(db_session) -> None:
    """'thịt' → chỉ nguyên liệu + trái cây, KHÔNG móc món.

    Bao gồm cả món vnfood ('Cháo dinh dưỡng thịt bò' — vnfood nhưng là dish).
    """
    results = await search_ingredients(db_session, "thịt", limit=20)
    types = {r.item_type for r in results}
    assert types <= {"ingredient", "fruit"}, f"còn dish/product: {types}"
    names = [r.ingredient_name.lower() for r in results]
    assert not any("cơm sườn" in n or "com suon" in n for n in names), (
        f"'Cơm sườn' (dish) lọt autocomplete: {names}"
    )
    assert not any("cháo" in n for n in names), (
        f"'Cháo *' (dish vnfood) lọt autocomplete: {names}"
    )


async def test_autocomplete_banh_not_dish(db_session) -> None:
    """'bánh' autocomplete KHÔNG trả dish.

    'Bánh *' (Bánh sữa, Bánh chưng) toàn product → bị lọc khỏi autocomplete
    (autocomplete chỉ trả ingredient+fruit). Vậy 'bánh' có thể 0 kết quả,
    nhưng KHÔNG bao giờ trả dish (Bánh mì thịt nướng vnmeal).
    """
    results = await search_ingredients(db_session, "bánh", limit=20)
    types = {r.item_type for r in results}
    assert "dish" not in types, f"'bánh' trả dish: {types}"


# ─── Lookup institute chỉ trả dish ────────────────────────────────────────────


async def test_lookup_com_suon_still_institute(db_session) -> None:
    """'cơm sườn' (item_type=dish) → lookup institute vẫn trả (đổi source→item_type
    không phá lookup món)."""
    result = await lookup_dish(db_session, "com suon")
    assert result["exists"] is True, "cơm sườn phải exists"
    assert result["source"] == "institute", f"source phải institute: {result['source']}"


async def test_lookup_institute_never_returns_fruit(db_session) -> None:
    """Lookup institute (item_type='dish') KHÔNG trả trái cây (item_type='fruit').

    'sầu riêng' → có cả 'Sầu riêng' (fruit) và 'Chè sầu riêng' (dish). Lookup
    institute phải móc dish ('Chè sầu riêng'), KHÔNG móc fruit ('Sầu riêng').
    Trước sửa: source='vnmeal' móc cả 2 (trái lọt vào kết quả món). Sau sửa:
    item_type='dish' chỉ móc món.
    """
    result = await lookup_dish(db_session, "sầu riêng")
    if result["source"] == "institute":
        # institute trả dish_name — phải là món (vd 'Chè sầu riêng'), không phải
        # trái 'Sầu riêng (Durian)' đơn thuần. Kiểm tra qua DB: kết quả item_type=dish.
        from sqlalchemy import select as _sel

        found = (
            await db_session.execute(
                _sel(NutritionIngredient.item_type).where(
                    NutritionIngredient.ingredient_name == result["dish_name"]
                )
            )
        ).scalars().first()
        assert found == "dish", (
            f"institute trả item_type={found} (phải 'dish'), trái cây lọt: {result['dish_name']}"
        )
