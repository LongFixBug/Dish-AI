"""Re-parse USDA — giữ field `foodCategory` bị bỏ trong parse_usda.py cũ.

parse_usda.py cũ chỉ giữ {ingredient_name, nutrition, source} — BỎ field
`foodCategory` (VD "Fruits and Fruit Juices", "Baked Products", "Poultry
Products"...). Đây là nguyên nhân 8060 rows USDA hiện toàn item_type=ingredient
(default) trong DB.

QUAN TRỌNG: foodCategory KHÔNG có ở endpoint `/foods/list` (chỉ trả fdcId,
description, dataType, foodNutrients). foodCategory chỉ có ở endpoint `/foods`
(detail) — dạng dict {id, code, description}. Script này lấy category từ
`/foods` detail (fetch_nutrients_batch), KHÔNG từ list.

Giữ nguyên logic tính nutrition (per-gram từ amount/100) như parse_usda.py cũ,
chỉ THÊM field `category` (= foodCategory.description). Nutrition trong DB
không đổi → embedding/FK an toàn.

Output: data/usda_with_category.json (schema cũ + `category`, KHÔNG đè
data/usda_ingredients.json). Tái dùng pattern parse_usda.py (httpx + retry +
rate limit).

Usage:
    DEBUG=false python scripts/reparse_usda_category.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402

# ─── Constants (copy từ parse_usda.py) ────────────────────────────────────────

BASE_URL = "https://api.nal.usda.gov/fdc/v1"
DATA_TYPES = ["Foundation", "SR Legacy"]
TARGET_NUTRIENTS: dict[str, str] = {
    "208": "calories_per_g",
    "203": "protein_per_g",
    "204": "fat_per_g",
    "205": "carbs_per_g",
    "291": "fiber_per_g",
}
RATE_LIMIT_DELAY = 0.3
BATCH_SIZE = 20
REQUEST_TIMEOUT = 60.0
MAX_RETRIES = 3
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ─── Helpers (copy từ parse_usda.py) ──────────────────────────────────────────


def _api_params() -> dict:
    """Trả query params chứa api_key cho mọi request."""
    return {"api_key": settings.usda_api_key}


def _post_with_retry(url: str, json_payload: dict) -> httpx.Response:
    """POST request với retry khi timeout hoặc lỗi server (5xx)."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = httpx.post(
                url,
                params=_api_params(),
                json=json_payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response
        except httpx.ReadTimeout as e:
            last_error = e
            wait = attempt * 5
            print(f"    ⚠ Timeout (attempt {attempt}/{MAX_RETRIES}), chờ {wait}s...")
            time.sleep(wait)
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                last_error = e
                wait = attempt * 5
                print(f"    ⚠ Server error {e.response.status_code} "
                      f"(attempt {attempt}/{MAX_RETRIES}), chờ {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise last_error  # type: ignore[misc]


# ─── Step 1: Lấy danh sách thực phẩm (kèm foodCategory) ───────────────────────


def fetch_food_list(page_size: int = 200, max_pages: int = 50) -> list[int]:
    """Gọi POST /foods/list, duyệt phân trang. Trả list fdcId.

    Lưu ý: /foods/list KHÔNG trả foodCategory (chỉ {fdcId, description, dataType,
    foodNutrients...}). foodCategory chỉ có ở endpoint /foods (detail) — lấy ở
    fetch_nutrients_batch. List step chỉ cần fdcId.
    """
    foods: list[dict] = []
    page = 1

    print("[1/3] Đang lấy danh sách thực phẩm (fdcId)...")

    while page <= max_pages:
        payload = {"dataType": DATA_TYPES, "pageSize": page_size, "pageNumber": page}
        response = _post_with_retry(f"{BASE_URL}/foods/list", payload)

        items = response.json()
        if not items:
            break

        foods.extend(items)
        print(f"    page {page}: +{len(items)} items (tổng: {len(foods)})")
        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    fdc_ids = [f["fdcId"] for f in foods]
    print(f"    → Tổng cộng {len(foods)} thực phẩm\n")
    return fdc_ids


# ─── Step 2: Lấy chi tiết dinh dưỡng (batch) ──────────────────────────────────


def extract_nutrients(food_detail: dict) -> dict[str, float]:
    """Từ 1 food detail JSON, extract 5 target nutrients (per gram)."""
    result: dict[str, float] = {}

    for fn in food_detail.get("foodNutrients", []):
        nutrient_info = fn.get("nutrient", fn)
        nutrient_number = str(nutrient_info.get("number", ""))

        if nutrient_number in TARGET_NUTRIENTS:
            field_name = TARGET_NUTRIENTS[nutrient_number]
            amount_per_100g = fn.get("amount", 0) or 0.0
            result[field_name] = round(amount_per_100g / 100, 6)

    return result


def _extract_category(food_detail: dict) -> str:
    """Lấy foodCategory description từ food_detail.

    /foods (detail) trả foodCategory dạng dict {id, code, description}:
        {"id": 9, "code": "0900", "description": "Fruits and Fruit Juices"}
    Lưu ý: /foods/list KHÔNG trả foodCategory → phải lấy từ detail (endpoint này).
    """
    cat = food_detail.get("foodCategory")
    if isinstance(cat, dict):
        return cat.get("description", "") or ""
    if isinstance(cat, str):
        return cat
    return ""


def fetch_nutrients_batch(fdc_ids: list[int]) -> list[dict]:
    """Gọi POST /foods batch ID, trả về list record kèm `category`.

    Lấy category trực tiếp từ food_detail["foodCategory"]["description"]
    (endpoint /foods detail trả — /foods/list KHÔNG trả).
    """
    response = _post_with_retry(f"{BASE_URL}/foods", {"fdcIds": fdc_ids})

    results: list[dict] = []
    for food_detail in response.json():
        nutrients = extract_nutrients(food_detail)
        if any(v > 0 for v in nutrients.values()):
            results.append({
                "ingredient_name": food_detail.get("description", ""),
                **nutrients,
                "source": food_detail.get("dataType", "unknown").lower(),
                "category": _extract_category(food_detail),  # ← THÊM (detail có, list không)
            })

    return results


# ─── Step 3: Batch loop + save ────────────────────────────────────────────────


def process_all_foods(fdc_ids: list[int]) -> list[dict]:
    """Duyệt toàn bộ fdc_ids theo batch, gọi API lấy nutrients + category từ detail."""
    all_results: list[dict] = []
    total = len(fdc_ids)

    print(f"[2/3] Đang lấy chi tiết dinh dưỡng cho {total} thực phẩm...")

    for i in range(0, total, BATCH_SIZE):
        batch = fdc_ids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        try:
            results = fetch_nutrients_batch(batch)
            all_results.extend(results)
            print(f"    batch {batch_num}/{total_batches}: "
                  f"+{len(results)} items (tổng: {len(all_results)})")
        except httpx.HTTPError as e:
            print(f"    batch {batch_num}/{total_batches}: LỖI → {e}")

        time.sleep(RATE_LIMIT_DELAY)

    print(f"    → {len(all_results)} ingredients có dữ liệu dinh dưỡng\n")
    return all_results


def save_results(results: list[dict]) -> Path:
    """Lưu kết quả ra data/usda_with_category.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "usda_with_category.json"

    print(f"[3/3] Đang lưu {len(results)} ingredients vào {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    file_size = output_path.stat().st_size / 1024
    print(f"    → Đã lưu! File size: {file_size:.1f} KB\n")
    return output_path


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    """Pipeline: list (fdcId) → nutrients + category (từ detail) → save."""
    if not settings.usda_api_key:
        print("LỖI: USDA_API_KEY chưa được cấu hình trong .env")
        print("Thêm dòng: USDA_API_KEY=your_key_here")
        sys.exit(1)

    fdc_ids = fetch_food_list()
    if not fdc_ids:
        print("Không lấy được dữ liệu nào. Kiểm tra API key hoặc network.")
        sys.exit(1)

    results = process_all_foods(fdc_ids)
    save_results(results)

    # Phân bố category
    from collections import Counter
    cats = Counter(r["category"] for r in results)
    empty = cats.pop("", 0)
    print("Phân bố foodCategory:")
    for k, v in cats.most_common():
        print(f"  {v:4d}  {k}")
    print(f"  {empty:4d}  <rỗng — fallback ingredient>")

    print("\nMẫu 5 ingredients đầu (kèm category):")
    for item in results[:5]:
        print(f"  [{item['category'][:30]:30s}] {item['ingredient_name']}")


if __name__ == "__main__":
    main()
