"""Legacy migration v2: UPDATE item_type từ category gốc.

Bản cũ `migrate_item_type.py` dùng heuristic regex (source + tên) — USDA 8060 rows
toàn default 'ingredient' vì parse_usda.py bỏ foodCategory. Bản này re-parse lấy
lại category gốc (data/usda_with_category.json + data/vn_foods_with_category.json)
→ map sang item_type chính xác hơn.

IDEMPOTENT: set cùng giá trị, rerun không đổi. Chỉ UPDATE item_type, KHÔNG đụng
name/nutrition/embedding → FK an toàn.

Ưu tiên: category gốc (v2) ĐÈ heuristic cũ cho TẤT CẢ rows (USDA + VN) có trong
category map. Rows không có category trong map → GIỮ nguyên item_type hiện tại
(không hạ về default, tránh làm hỏng heuristic đã đúng cho rows category rỗng).

So với heuristic v1:
- USDA: cải thiện lớn — "Fruits and Fruit Juices" → fruit (trước = ingredient),
  "Baked Products"/"Beverages" → product (trước = ingredient).
- VN: cải thiện vừa — "Quả chín" → fruit, "Thức ăn truyền thống" → dish,
  "Đồ ngọt/Đồ hộp/Nước giải khát" → product (trước heuristic regex có thể miss).

Usage:
    DEBUG=false python scripts/migrate_item_type_v2.py
"""

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from backend.db.postgres import engine  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ─── Mapping USDA foodCategory → item_type (25 category chuẩn) ────────────────

USDA_CATEGORY_TO_ITEM_TYPE: dict[str, str] = {
    # fruit — trái cây (dùng như nguyên liệu trong công thức)
    "Fruits and Fruit Juices": "fruit",
    # ingredient — nguyên liệu thô (động vật/thực phẩm chế biến tối thiểu)
    "Vegetables and Vegetable Products": "ingredient",
    "Legumes and Legume Products": "ingredient",
    "Grains and Pasta": "ingredient",
    "Cereal Grains and Pasta": "ingredient",        # tên cũ
    "Nut and Seed Products": "ingredient",
    "Poultry Products": "ingredient",
    "Beef Products": "ingredient",
    "Pork Products": "ingredient",
    "Lamb, Veal, and Game Products": "ingredient",
    "Finfish and Shellfish Products": "ingredient",
    "Dairy and Egg Products": "ingredient",
    "Spices and Herbs": "ingredient",
    "Fats and Oils": "ingredient",
    "Sweets and Confectionery": "ingredient",       # tên cũ
    "Sweets": "ingredient",                         # tên USDA thực (đường/mật — nguyên liệu)
    "Soups, Sauces, and Gravies": "ingredient",     # broth/xì dầu — gia vị
    "Sausages and Luncheon Meats": "ingredient",    # xúc xích — nguyên liệu
    "American Indian/Alaska Native Foods": "ingredient",
    "Agricultural Inputs": "ingredient",
    # product — thành phẩm chế biến sẵn (không phải nguyên liệu thô)
    "Baked Products": "product",
    "Snacks": "product",
    "Fast Foods": "product",
    "Meals, Entrees, and Side Dishes": "product",
    "Beverages": "product",
    "Breakfast Cereals": "product",
    "Baby Foods": "product",
    "Restaurant Foods": "product",
}

# ─── Mapping VN category → item_type ──────────────────────────────────────────
# foodNatunal (vnfood) — 15 category
VNFOOD_CATEGORY_TO_ITEM_TYPE: dict[str, str] = {
    "Quả chín": "fruit",
    "Rau, quả, củ dùng làm rau": "ingredient",
    "Thịt và sản phẩm chế biến": "ingredient",
    "Thủy sản và sản phẩm chế biến": "ingredient",
    "Trứng và sản phẩm chế biến": "ingredient",
    "Sữa và sản phẩm chế biến": "ingredient",
    "Gia vị, nước chấm": "ingredient",
    "Hạt, quả giàu đạm, béo và sản phẩm chế biến": "ingredient",
    "Khoai củ và sản phẩm chế biến": "ingredient",
    "Ngũ cốc và sản phẩm chế biến": "ingredient",
    "Dầu, mỡ, bơ": "ingredient",
    "Đồ ngọt (đường, bánh, mứt, kẹo)": "product",   # bánh kẹo thành phẩm
    "Đồ hộp": "product",
    "Nước giải khát": "product",
    "Thức ăn truyền thống": "dish",                 # bánh chưng, xôi... món truyền thống
}

# tool (vnmeal) — 19 category. Phần lớn → dish (món ăn nấu sẵn), trừ trái cây + burger/pizza
VNMEAL_CATEGORY_TO_ITEM_TYPE: dict[str, str] = {
    "Các loại trái cây": "fruit",
    "Burger, pizza": "product",
    # phần còn lại mặc định dish (xem _map_vnmeal_category fallback)
}


def _map_usda(category: str) -> str | None:
    """Map USDA foodCategory → item_type. None nếu category rỗng/không match."""
    if not category:
        return None
    return USDA_CATEGORY_TO_ITEM_TYPE.get(category)


def _map_vnfood(category: str) -> str | None:
    """Map VN foodNatunal category → item_type."""
    if not category:
        return None
    return VNFOOD_CATEGORY_TO_ITEM_TYPE.get(category)


def _map_vnmeal(category: str) -> str | None:
    """Map VN tool category → item_type. Mặc định dish (món nấu sẵn)."""
    if not category:
        return None
    # category đặc biệt → map riêng; phần còn lại → dish
    return VNMEAL_CATEGORY_TO_ITEM_TYPE.get(category, "dish")


# ─── Load category map từ 2 file re-parse ─────────────────────────────────────


def _load_category_map() -> dict[str, str]:
    """Build {ingredient_name → item_type} — phân biệt vnfood vs vnmeal qua source."""
    name_to_type: dict[str, str] = {}

    # USDA
    path = DATA_DIR / "usda_with_category.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
        mapped = 0
        for r in rows:
            item_type = _map_usda(r.get("category", ""))
            if item_type:
                name_to_type[r["ingredient_name"]] = item_type
                mapped += 1
        print(f"  usda_with_category.json: {len(rows)} rows → {mapped} mapped")
    else:
        print("  ⚠ usda_with_category.json không tồn tại (chạy reparse_usda_category.py)")

    # VN (phân biệt vnfood vs vnmeal qua source field)
    path = DATA_DIR / "vn_foods_with_category.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
        mapped_f = mapped_m = 0
        for r in rows:
            src = r.get("source", "")
            cat = r.get("category", "")
            if src == "vnfood":
                t = _map_vnfood(cat)
                if t:
                    mapped_f += 1
            elif src == "vnmeal":
                t = _map_vnmeal(cat)
                if t:
                    mapped_m += 1
            else:
                t = None
            if t:
                name_to_type[r["ingredient_name"]] = t
        print(f"  vn_foods_with_category.json: {len(rows)} rows → "
              f"vnfood {mapped_f} + vnmeal {mapped_m} mapped")
    else:
        print("  ⚠ vn_foods_with_category.json không tồn tại (chạy reparse_vn_category.py)")

    return name_to_type


# ─── SQL helpers ──────────────────────────────────────────────────────────────


async def _count_by_item_type(conn) -> dict[str, int]:
    """Trả {item_type: count} từ DB."""
    result = await conn.execute(
        text("SELECT item_type, count(*) FROM nutrition_ingredients "
             "GROUP BY item_type ORDER BY 1;")
    )
    return {t: c for t, c in result.all()}


async def _update_by_type(conn, item_type: str, names: list[str]) -> int:
    """UPDATE item_type cho rows match tên (bất kỳ source — category map đã đúng nguồn)."""
    if not names:
        return 0
    result = await conn.execute(
        text(
            "UPDATE nutrition_ingredients SET item_type = :type "
            "WHERE ingredient_name = ANY(:names);"
        ),
        {"type": item_type, "names": names},
    )
    return result.rowcount or 0


# ─── Migration chính ──────────────────────────────────────────────────────────


async def migrate() -> None:
    """Load category map → group theo target item_type → UPDATE → in diff."""
    print("Load category map từ data/*.json...")
    name_to_type = _load_category_map()
    print(f"  → Tổng {len(name_to_type)} rows có mapping category→item_type\n")

    if not name_to_type:
        print("❌ Không có mapping nào. Chạy reparse_usda_category.py + "
              "reparse_vn_category.py trước.")
        return

    # Group tên theo target item_type
    grouped: dict[str, list[str]] = {"ingredient": [], "dish": [], "fruit": [], "product": []}
    unmapped_category = Counter()
    for name, t in name_to_type.items():
        if t in grouped:
            grouped[t].append(name)
        else:
            unmapped_category[t] += 1
    if unmapped_category:
        print(f"  ⚠ item_type ngoài 4 loại chuẩn: {dict(unmapped_category)}")

    async with engine.begin() as conn:
        before = await _count_by_item_type(conn)
        print("📊 Count TRƯỚC migration:")
        for t, c in before.items():
            print(f"   {t:12s} {c}")

        total_updated = 0
        for item_type, names in grouped.items():
            updated = await _update_by_type(conn, item_type, names)
            total_updated += updated
            print(f"  ✅ UPDATE → {item_type}: {updated} rows "
                  f"(từ {len(names)} tên trong map)")

        after = await _count_by_item_type(conn)
        print(f"\n📊 Count SAU migration (tổng update: {total_updated}):")
        for t, c in after.items():
            delta = c - before.get(t, 0)
            sign = "+" if delta >= 0 else ""
            print(f"   {t:12s} {c}  ({sign}{delta})")

    print("\n👉 So sánh before/after — fruit + product tăng, ingredient giảm.")
    print("👉 Chạy pytest tests/test_item_type.py để verify (cần cập nhật assert count).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
