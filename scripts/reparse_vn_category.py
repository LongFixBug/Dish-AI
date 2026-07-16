"""Re-parse dữ liệu VN — giữ field `category` bị bỏ trong parse_vn_foods.py cũ.

parse_vn_foods.py cũ chỉ giữ 7 field {ingredient_name, *_per_g, source} — BỎ
field phân loại gốc:
  - foodNatunal (nguyên liệu): `category` / `categoryEn`
        VD "Sữa và sản phẩm chế biến" / "Milk and processed products"
  - tool (món ăn): `category_name` / `category_name_en`
        VD "Các món khác"

Probe (scripts/probe_vn_api.py) đã xác nhận CẢ 2 endpoint đều có field category.
Script này re-crawl, giữ nguyên logic tính nutrition (Atwater cho food, total_energy
cho meal — KHÔNG đổi nutrition đã seed trong DB), chỉ THÊM field `category` vào
output để migrate_item_type_v2.py map sang item_type chính xác hơn heuristic.

Output: data/vn_foods_with_category.json (schema cũ + `category`, KHÔNG đè
data/vn_foods.json). Tái dùng pattern parse_vn_foods.py.

Usage:
    python scripts/reparse_vn_category.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Constants (copy từ parse_vn_foods.py) ────────────────────────────────────

BASE_URL = "https://viendinhduong.vn"
FOOD_API = "/api/fe/foodNatunal/getPageFoodData"
FOOD_PER_PAGE = 15
MEAL_API = "/api/fe/tool/getPageFoodData"
MEAL_PER_PAGE = 10

KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_FAT = 9
KCAL_PER_G_CARB = 4

REQUEST_DELAY = 1.0
TIMEOUT = 30.0
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

_NUTRIENT_FIELD_MAP = {
    "protein": "protein_per_g",
    "total lipid (fat)": "fat_per_g",
    "carbohydrate by difference": "carbs_per_g",
    "fiber, total dietary": "fiber_per_g",
    "fiber": "fiber_per_g",
}


def _extract_nutrient_value(nutrients: list[dict], name_en_substring: str) -> float:
    """Tìm nutrient theo name_en (case-insensitive), trả value (per 100g)."""
    needle = name_en_substring.lower()
    for n in nutrients:
        if needle in n.get("name_en", "").lower():
            value = n.get("value", 0) or 0.0
            if n.get("unit", "").lower() == "mg":
                value = value / 1000
            return value
    return 0.0


def _calc_calories_per_g(protein_g: float, fat_g: float, carb_g: float) -> float:
    """Atwater: kcal per gram từ macro (đầu vào per 100g)."""
    kcal_per_100g = protein_g * KCAL_PER_G_PROTEIN + fat_g * KCAL_PER_G_FAT + carb_g * KCAL_PER_G_CARB
    return round(kcal_per_100g / 100, 6)


# ─── API 1: Thực phẩm (nguyên liệu thô) ────────────────────────────────────────


def parse_food_item(item: dict) -> dict | None:
    """Chuyển 1 thực phẩm → NutritionPerGram record + `category`.

    Giữ nguyên logic tính calo (Atwater) như parse_vn_foods.py cũ để nutrition
    khớp DB đã seed. Chỉ thêm field `category` từ item gốc.
    """
    nutrients = item.get("nutrition", [])
    if not nutrients:
        return None

    protein = _extract_nutrient_value(nutrients, "Protein")
    fat = _extract_nutrient_value(nutrients, "Total lipid (Fat)")
    carb = _extract_nutrient_value(nutrients, "Carbohydrate by difference")
    fiber = _extract_nutrient_value(nutrients, "Fiber")

    if protein == 0 and fat == 0 and carb == 0:
        return None

    name = item.get("name_vi") or item.get("name_en") or ""
    if not name:
        return None

    if item.get("name_en") and item["name_en"] != name:
        name = f"{name} ({item['name_en']})"

    return {
        "ingredient_name": name,
        "calories_per_g": _calc_calories_per_g(protein, fat, carb),
        "protein_per_g": round(protein / 100, 6),
        "fat_per_g": round(fat / 100, 6),
        "carbs_per_g": round(carb / 100, 6),
        "fiber_per_g": round(fiber / 100, 6),
        "source": "vnfood",
        "category": item.get("category", ""),  # ← THÊM (bị bỏ trong parse cũ)
    }


# ─── API 2: Món ăn (nấu sẵn) ─────────────────────────────────────────────────


def parse_meal_item(item: dict) -> dict | None:
    """Chuyển 1 món ăn → NutritionPerGram record + `category`.

    Giữ nguyên logic (total_energy + nutritional_components/dish_components) như
    parse_vn_foods.py cũ. Chỉ thêm field `category` (= category_name).
    """
    name = item.get("name_vi") or item.get("name_en") or ""
    if not name:
        return None

    try:
        energy = float(item.get("total_energy") or 0)
    except (TypeError, ValueError):
        energy = 0.0
    if energy <= 0:
        return None

    protein = fat = carb = fiber = 0.0
    components = item.get("nutritional_components") or item.get("dish_components") or []
    for comp in components:
        comp_name = (comp.get("nameEn") or comp.get("name_en") or comp.get("name") or "").lower()
        try:
            value = float(comp.get("amount", comp.get("value", 0)) or 0)
        except (TypeError, ValueError):
            continue

        unit = (comp.get("unit_name") or comp.get("unit") or "").lower()
        if unit in ("mg",):
            value = value / 1000
        elif unit in ("μg", "ug", "mcg"):
            value = value / 1_000_000
        elif unit == "kcal":
            continue

        if "protein" in comp_name or "chat-dam" in comp.get("key", ""):
            protein = value
        elif "lipid" in comp_name or "fat" in comp_name or ("chat-beo" in comp.get("key", "") and "trans" not in comp_name):
            fat = value
        elif "carbohyd" in comp_name or "chat-bot-duong" in comp.get("key", ""):
            carb = value
        elif "fiber" in comp_name or "dietary" in comp_name:
            fiber = value

    if item.get("name_en"):
        name = f"{name} ({item['name_en']})"

    return {
        "ingredient_name": name,
        "calories_per_g": round(energy / 100, 6),
        "protein_per_g": round(protein / 100, 6),
        "fat_per_g": round(fat / 100, 6),
        "carbs_per_g": round(carb / 100, 6),
        "fiber_per_g": round(fiber / 100, 6),
        "source": "vnmeal",
        "category": item.get("category_name", ""),  # ← THÊM (bị bỏ trong parse cũ)
    }


def fetch_all_foods(client: httpx.Client) -> list[dict]:
    """Cào toàn bộ 853 thực phẩm qua phân trang, giữ `category`."""
    results: list[dict] = []
    page = 1

    print("[A] Cào thực phẩm (foodNatunal)...")
    while True:
        response = client.get(
            f"{BASE_URL}{FOOD_API}",
            params={"page": page},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            parsed = parse_food_item(item)
            if parsed:
                results.append(parsed)

        total = data.get("total", 0)
        print(f"  page {page}: +{len(items)} raw / {len(results)} valid (total API: {total})")

        if page * FOOD_PER_PAGE >= total:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    print(f"  → {len(results)} thực phẩm VN\n")
    return results


def fetch_all_meals(client: httpx.Client) -> list[dict]:
    """Cào toàn bộ 1250 món ăn qua phân trang, giữ `category_name`."""
    results: list[dict] = []
    page = 1

    print("[B] Cào món ăn (tool/getPageFoodData)...")
    while True:
        response = client.get(
            f"{BASE_URL}{MEAL_API}",
            params={"page": page},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            parsed = parse_meal_item(item)
            if parsed:
                results.append(parsed)

        total = data.get("total", 0)
        print(f"  page {page}: +{len(items)} raw / {len(results)} valid (total API: {total})")

        if page * MEAL_PER_PAGE >= total:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    print(f"  → {len(results)} món ăn VN\n")
    return results


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    """Pipeline: cào food + meal → lưu vn_foods_with_category.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "vn_foods_with_category.json"

    with httpx.Client() as client:
        foods = fetch_all_foods(client)
        meals = fetch_all_meals(client)

    all_items = foods + meals
    print(f"📦 Tổng cộng {len(all_items)} thực phẩm + món ăn VN (có category)")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    size = output_path.stat().st_size / 1024
    print(f"✅ Đã lưu vào {output_path} ({size:.1f} KB)\n")

    # Phân bố category (xem nhanh)
    from collections import Counter
    cats_food = Counter(i["category"] for i in foods if i["category"])
    cats_meal = Counter(i["category"] for i in meals if i["category"])
    empty = sum(1 for i in all_items if not i["category"])
    print(f"Phân bố category foodNatunal ({len(cats_food)} loại):")
    for k, v in cats_food.most_common():
        print(f"  {v:4d}  {k}")
    print(f"Phân bố category tool ({len(cats_meal)} loại):")
    for k, v in cats_meal.most_common():
        print(f"  {v:4d}  {k}")
    print(f"Rows category rỗng: {empty}")


if __name__ == "__main__":
    main()
