"""Integration tests: ILIKE không phân biệt dấu tiếng Việt qua vn_norm.

Test 4 điểm sửa:
  #1 search_ingredients (ingredients.py)
  #2 _lookup_institute (dishes.py)
  #3 _lookup_user_recipe (dishes.py)
  #4 contribute_dish check trùng tên equality (dishes.py)

Trước khi sửa: 'suon' không móc 'sườn' qua ILIKE → rơi vector fallback (kém).
Sau khi sửa: ILIKE + vn_norm móc đúng → không cần vector.

Lưu ý: test dùng món THẬT có trong DB ('sườn', 'sữa bò', 'cơm sườn').
Không dùng 'cơm chiên' (DB không có) hay 'bún chả' (sau item_type = dish,
bị lọc khỏi autocomplete).

Dùng DB thật (10K rows) + embedding server 8081 (cho vector fallback nếu dùng).
"""

import pytest

from backend.services.dishes import contribute_dish, lookup_dish
from backend.services.ingredients import search_ingredients
from schemas.dish import RecipeItemInput
from tests.conftest import client, db_session  # noqa: F401  (fixtures)


def _names(results) -> list[str]:
    """Lấy ingredient_name (lower) từ list ORM — tiện assert 'có chứa'."""
    return [r.ingredient_name.lower() for r in results]


def _has_substring(names: list[str], needle_lower: str) -> bool:
    """True nếu có tên nào (lower) chứa needle (đã normalize-không-dấu mong đợi)."""
    return any(needle_lower in n for n in names)


# ─── #1 search_ingredients — ILIKE không dấu móc đúng ─────────────────────────


async def test_search_suon_finds_suon_via_ilike(db_session) -> None:
    """'suon' (không dấu) phải móc nguyên liệu có 'sườn' qua ILIKE.

    Trước sửa: ILIKE 0 hit → rơi vector (kém). Sau sửa: ILIKE móc 'sườn'.
    """
    results = await search_ingredients(db_session, "suon", limit=8)
    assert len(results) > 0, "phải có ít nhất 1 kết quả cho 'suon'"
    # Có kết quả tên chứa 'sườn' (dấu) — ILIKE + vn_norm match
    assert _has_substring(_names(results), "sườn"), (
        f"không móc được 'sườn'; got {_names(results)}"
    )


async def test_search_sua_bo_finds_sua_bo(db_session) -> None:
    """'sua bo' (không dấu) phải móc 'Sữa bò tươi' qua ILIKE + vn_norm.

    Case quan trọng: trước sửa ILIKE phân biệt dấu → 'sua bo' không móc
    'Sữa bò' (chỉ vector fallback kém). Sau sửa: ILIKE móc đúng.
    Dùng 'sữa bò' (ingredient) thay vì 'bún chả' vì 'Bún chả' giờ = dish
    (bị lọc khỏi autocomplete sau khi thêm item_type).
    """
    results = await search_ingredients(db_session, "sua bo", limit=8)
    assert len(results) > 0, "phải có kết quả cho 'sua bo'"
    names = _names(results)
    assert _has_substring(names, "sữa bò") or _has_substring(
        names, "sua bo"
    ), f"không móc 'sữa bò'; got {names}"


# ─── #2 lookup_dish — institute móc không dấu ─────────────────────────────────


async def test_lookup_com_suon_finds_institute(db_session) -> None:
    """'com suon' (không dấu) → móc 'Cơm sườn' institute (source=vnmeal)."""
    result = await lookup_dish(db_session, "com suon")
    assert result["exists"] is True, "phải exists=True cho 'com suon'"
    assert result["source"] == "institute", (
        f"source phải là institute; got {result['source']}"
    )
    assert "sườn" in result["dish_name"].lower() or "suon" in result[
        "dish_name"
    ].lower()


# ─── #4 contribute_dish — check trùng tên không phân biệt dấu/hoa ─────────────


async def test_contribute_duplicate_case_diacritic_raises_409(db_session) -> None:
    """Contribute tên trùng (khác dấu/hoa) → ValueError (→ HTTP 409).

    Setup: contribute 1 món mới 'bun thit nac pytest uniq', rồi contribute lại
    bằng 'BÚN THỊT NẠC PYTEST UNIQ' (hoa + dấu) → phải raise ValueError.
    Cleanup: xóa món test sau khi xong.
    """
    # Lấy 1 ingredient_id thật để contribute hợp lệ
    found = await search_ingredients(db_session, "thịt nạc", limit=1)
    assert len(found) > 0, "cần ingredient 'thịt nạc' để test contribute"
    ing_id = str(found[0].id)

    unique = "bun thit nac pytest uniq 9f3k"
    items = [RecipeItemInput(ingredient_id=ing_id, amount=100, unit="g")]

    # 1. Contribute lần đầu — OK
    dish_id, _totals, _assumed = await contribute_dish(
        db_session,
        dish_name=unique,
        description="pytest cleanup me",
        items=items,
        contributor_id="pytest",
    )
    assert dish_id is not None

    # 2. Contribute lại tên trùng (HOA + dấu) → ValueError
    with pytest.raises(ValueError, match="đã tồn tại"):
        await contribute_dish(
            db_session,
            dish_name="BÚN THỊT NẠC PYTEST UNIQ 9F3K",
            description="dup",
            items=items,
            contributor_id="pytest",
        )

    # Cleanup: xóa món + dish_ingredients (FK cascade không setup → xóa tay)
    from sqlalchemy import delete
    from backend.db.models import Dish, DishIngredient

    await db_session.execute(
        delete(DishIngredient).where(DishIngredient.dish_id == dish_id)
    )
    await db_session.execute(delete(Dish).where(Dish.id == dish_id))
    await db_session.commit()


# ─── Endpoint qua TestClient ──────────────────────────────────────────────────


def test_endpoint_search_sua_bo(client) -> None:
    """GET /ingredients/search?q=sua bo → 200 + có 'sữa bò'."""
    resp = client.get("/api/v1/ingredients/search", params={"q": "sua bo"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) > 0
    names = [r["ingredient_name"].lower() for r in results]
    assert _has_substring(names, "sữa bò") or _has_substring(
        names, "sua bo"
    ), f"endpoint không móc 'sữa bò'; got {names}"
