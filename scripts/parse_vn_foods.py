"""Parse dữ liệu dinh dưỡng từ Viện Dinh Dưỡng VN (viendinhduong.vn).

Cào 2 API ẩn (SPA) của trang web:
  1. /api/fe/foodNatunal/getPageFoodData  — 853 thực phẩm (nguyên liệu thô)
  2. /api/fe/tool/getPageFoodData          — 1250 món ăn (nấu sẵn)

Vì API thực phẩm không trả về Energy, tự tính calo từ macro (Atwater):
    calories = protein×4 + fat×9 + carb×4

API nguyên liệu trả dữ liệu theo 100 g nên được đổi sang per-gram. API món ăn
trả tổng dinh dưỡng của một khẩu phần món ăn; các giá trị này được giữ nguyên
với hậu tố ``_per_serving`` để không nhầm với dữ liệu nguyên liệu.

Usage:
    python scripts/parse_vn_foods.py

Output:
    data/vn_foods.json — list[dict] cùng cấu trúc usda_ingredients.json
"""

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.ingredient_names import clean_ingredient_name  # noqa: E402

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://viendinhduong.vn"

# API 1: thực phẩm (nguyên liệu thô) — 853 món, 15/page
FOOD_API = "/api/fe/foodNatunal/getPageFoodData"
FOOD_PER_PAGE = 15

# API 2: món ăn (nấu sẵn) — 1250 món, 10/page, có sẵn total_energy
MEAL_API = "/api/fe/tool/getPageFoodData"
MEAL_PER_PAGE = 10

# Hệ số Atwater: kcal/g cho từng macro
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_FAT = 9
KCAL_PER_G_CARB = 4

# Rate limit — tôn trọng server, 1 request/giây
REQUEST_DELAY = 1.0
TIMEOUT = 30.0

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ─── HTTP client (dùng lại cho toàn bộ script) ────────────────────────────────

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}


# ─── Helpers ───────────────────────────────────────────────────────────────────

_NUTRIENT_FIELD_MAP = {
    "protein": "protein_per_g",
    "total lipid (fat)": "fat_per_g",
    "carbohydrate by difference": "carbs_per_g",
    "fiber, total dietary": "fiber_per_g",
    "fiber": "fiber_per_g",
}


def _extract_nutrient_value(nutrients: list[dict], name_en_substring: str) -> float:
    """Tìm nutơrient theo name_en (case-insensitive), trả về value (per 100g)."""
    needle = name_en_substring.lower()
    for n in nutrients:
        if needle in n.get("name_en", "").lower():
            value = n.get("value", 0) or 0.0
            # Chuyển mg thành g (1 g = 1000 mg)
            if n.get("unit", "").lower() == "mg":
                value = value / 1000
            return value
    return 0.0


def _calc_calories_per_g(protein_g: float, fat_g: float, carb_g: float) -> float:
    """Tính calo per gram từ macro (Atwater). Đầu vào per 100g, ra per gram."""
    kcal_per_100g = (
        protein_g * KCAL_PER_G_PROTEIN
        + fat_g * KCAL_PER_G_FAT
        + carb_g * KCAL_PER_G_CARB
    )
    return round(kcal_per_100g / 100, 6)


def _clamp_tiny_negative(value: float) -> float:
    """Clamp at most 0.1 g/100 g of source noise; retain larger errors."""
    return 0.0 if -0.1 <= value < 0 else value


# ─── API 1: Thực phẩm (nguyên liệu thô) ────────────────────────────────────────

def parse_food_item(item: dict) -> dict | None:
    """Chuyển 1 thực phẩm (per 100g) → NutritionPerGram record.

    API không trả Energy → tự tính từ Protein + Fat + Carb.
    """
    nutrients = item.get("nutrition", [])
    if not nutrients:
        return None

    protein = _extract_nutrient_value(nutrients, "Protein")
    fat = _extract_nutrient_value(nutrients, "Total lipid (Fat)")
    carb = _extract_nutrient_value(nutrients, "Carbohydrate by difference")
    fiber = _extract_nutrient_value(nutrients, "Fiber")
    protein, fat, carb, fiber = (
        _clamp_tiny_negative(value) for value in (protein, fat, carb, fiber)
    )

    # Bỏ qua món không có dữ liệu dinh dưỡng
    if protein == 0 and fat == 0 and carb == 0:
        return None

    name = clean_ingredient_name(item.get("name_vi") or item.get("name_en") or "")
    if not name:
        return None

    return {
        "ingredient_name": name,
        "calories_per_g": _calc_calories_per_g(protein, fat, carb),
        "protein_per_g": round(protein / 100, 6),
        "fat_per_g": round(fat / 100, 6),
        "carbs_per_g": round(carb / 100, 6),
        "fiber_per_g": round(fiber / 100, 6),
        "gram": 100.0,
        "source": "vnfood",
    }


def fetch_all_foods(client: httpx.Client) -> list[dict]:
    """Cào toàn bộ 853 thực phẩm qua phân trang."""
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


# ─── API 2: Món ăn (nấu sẵn) ─────────────────────────────────────────────────

def parse_meal_item(item: dict) -> dict | None:
    """Chuyển một món ăn thành tổng dinh dưỡng của một khẩu phần.

    ``tool/getPageFoodData`` trả ``total_energy`` và các thành phần dinh dưỡng
    cho cả món, không phải cho 100 g. Khối lượng khẩu phần chưa có trong nguồn
    nên được ước lượng riêng khi nạp vào ``vn_dishes``.
    """
    name = item.get("name_vi") or item.get("name_en") or ""
    if not name:
        return None

    # total_energy có thể là số hoặc chuỗi rỗng → ép float an toàn
    try:
        energy = float(item.get("total_energy") or 0)
    except (TypeError, ValueError):
        energy = 0.0
    if energy <= 0:
        return None

    # nutritional_components dùng key "amount" + "nameEn" (khác food API!)
    # unit có thể là: Kcal, g, mg, μg
    protein = fat = carb = fiber = 0.0
    components = item.get("nutritional_components") or item.get("dish_components") or []
    for comp in components:
        comp_name = (comp.get("nameEn") or comp.get("name_en") or comp.get("name") or "").lower()
        try:
            value = float(comp.get("amount", comp.get("value", 0)) or 0)
        except (TypeError, ValueError):
            continue

        # Quy về gram: mg→g (/1000), μg→g (/1e6)
        unit = (comp.get("unit_name") or comp.get("unit") or "").lower()
        if unit in ("mg",):
            value = value / 1000
        elif unit in ("μg", "ug", "mcg"):
            value = value / 1_000_000
        elif unit == "kcal":
            continue  # energy đã có riêng

        if "protein" in comp_name or "chat-dam" in comp.get("key",""):
            protein = value
        elif "lipid" in comp_name or "fat" in comp_name or ("chat-beo" in comp.get("key","") and "trans" not in comp_name):
            fat = value
        elif "carbohyd" in comp_name or "chat-bot-duong" in comp.get("key",""):
            carb = value
        elif "fiber" in comp_name or "dietary" in comp_name:
            fiber = value

    if item.get("name_en"):
        name = f"{name} ({item['name_en']})"

    return {
        "ingredient_name": name,
        "calories_per_serving": round(energy, 3),
        "protein_per_serving_g": round(protein, 3),
        "fat_per_serving_g": round(fat, 3),
        "carbs_per_serving_g": round(carb, 3),
        "fiber_per_serving_g": round(fiber, 3),
        "source": "vnmeal",
    }


def fetch_all_meals(client: httpx.Client) -> list[dict]:
    """Cào toàn bộ 1250 món ăn qua phân trang."""
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "vn_foods.json"

    with httpx.Client() as client:
        foods = fetch_all_foods(client)
        meals = fetch_all_meals(client)

    all_items = foods + meals
    print(f"📦 Tổng cộng {len(all_items)} thực phẩm + món ăn VN")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    size = output_path.stat().st_size / 1024
    print(f"✅ Đã lưu vào {output_path} ({size:.1f} KB)\n")

    # In 5 bản ghi mẫu, giữ rõ đơn vị của nguyên liệu và món ăn.
    print("Mẫu 5 items đầu:")
    for item in all_items[:5]:
        if item["source"] == "vnmeal":
            print(
                f"  [vnmeal] {item['ingredient_name']}: "
                f"cal={item['calories_per_serving']:.1f}/khẩu phần, "
                f"protein={item['protein_per_serving_g']:.1f}g/khẩu phần"
            )
        else:
            print(
                f"  [{item['source']}] {item['ingredient_name']}: "
                f"cal={item['calories_per_g']:.4f}/g, "
                f"protein={item['protein_per_g']:.4f}/g"
            )


if __name__ == "__main__":
    main()
