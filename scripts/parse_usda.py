"""Parse USDA FoodData Central → FoodAI NutritionPerGram schema.

Hai bước chính:
  1. POST /foods/list  → lấy danh sách {fdcId, description, dataType}
  2. POST /foods       → lấy chi tiết dinh dưỡng (batch 20 ID/lần)
  3. amount / 100      → giá trị per gram → map vào NutritionPerGram

Usage:
    python scripts/parse_usda.py

Output:
    data/usda_ingredients.json  — list[NutritionPerGram]
"""

import json
import sys
import time
from pathlib import Path

import httpx

# Cho phép import từ app/ khi chạy script từ thư mục gốc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.nal.usda.gov/fdc/v1"

# Chỉ lấy 2 loại dữ liệu chuẩn (per 100g, được USDA kiểm định)
DATA_TYPES = ["Foundation", "SR Legacy"]

# 5 nutrient IDs cần extract → map vào field của NutritionPerGram
TARGET_NUTRIENTS: dict[str, str] = {
    "208": "calories_per_g",  # Energy (kcal)
    "203": "protein_per_g",   # Protein (g)
    "204": "fat_per_g",       # Total lipid (fat) (g)
    "205": "carbs_per_g",     # Carbohydrate, by difference (g)
    "291": "fiber_per_g",     # Fiber, total dietary (g)
}

# USDA rate limit: 3600 requests/giờ → 1 req/giây là an toàn
RATE_LIMIT_DELAY = 1.1

# Batch size cho POST /foods (API nhận tối đa 20 ID/lần)
BATCH_SIZE = 20

# Timeout + retry — USDA API thỉnh thoảng chậm
REQUEST_TIMEOUT = 60.0
MAX_RETRIES = 3

# Thư mục output
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _api_params() -> dict:
    """Trả về query params chứa api_key cho mọi request."""
    return {"api_key": settings.usda_api_key}


def _post_with_retry(url: str, json_payload: dict) -> httpx.Response:
    """POST request với retry khi gặp timeout hoặc lỗi server (5xx)."""
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
            wait = attempt * 5  # tăng dần: 5s, 10s, 15s
            print(f"    ⚠ Timeout (attempt {attempt}/{MAX_RETRIES}), "
                  f"chờ {wait}s rồi thử lại...")
            time.sleep(wait)
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                last_error = e
                wait = attempt * 5
                print(f"    ⚠ Server error {e.response.status_code} "
                      f"(attempt {attempt}/{MAX_RETRIES}), chờ {wait}s...")
                time.sleep(wait)
            else:
                raise  # 4xx thì không retry
    raise last_error  # type: ignore[misc]


# ─── Step 1: Lấy danh sách thực phẩm ──────────────────────────────────────────


def fetch_food_list(page_size: int = 200, max_pages: int = 50) -> list[dict]:
    """Gọi POST /foods/list, duyệt tất cả các trang.

    Mỗi item trả về có dạng:
        {"fdcId": 747448, "description": "Strawberries, raw", "dataType": "Foundation"}

    Args:
        page_size: số items mỗi trang (tối đa 200).
        max_pages: safety cap — nếu vượt quá thì dừng.

    Returns:
        Danh sách tất cả foods thuộc Foundation + SR Legacy.
    """
    foods: list[dict] = []
    page = 1

    print(f"[1/3] Đang lấy danh sách thực phẩm (dataType={DATA_TYPES})...")

    while page <= max_pages:
        payload = {
            "dataType": DATA_TYPES,
            "pageSize": page_size,
            "pageNumber": page,
        }

        response = _post_with_retry(f"{BASE_URL}/foods/list", payload)

        items = response.json()
        if not items:
            break  # hết data

        foods.extend(items)
        print(f"    page {page}: +{len(items)} items (tổng: {len(foods)})")
        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    print(f"    → Tổng cộng {len(foods)} thực phẩm\n")
    return foods


# ─── Step 2: Lấy chi tiết dinh dưỡng (batch) ──────────────────────────────────


def extract_nutrients(food_detail: dict) -> dict[str, float]:
    """Từ 1 food detail JSON, extract 5 target nutrients.

    Xử lý cả 2 format JSON từ API:
      - Format A (từ /foods/list):   {"number": "208", "amount": 31.0, ...}
      - Format B (từ /food/{id}):    {"amount": 31.0, "nutrient": {"number": "208", ...}}

    Returns:
        dict với key là field name (calories_per_g, ...), value là giá trị per gram.
        VD: {"calories_per_g": 0.31, "protein_per_g": 0.0064, ...}
    """
    result: dict[str, float] = {}

    for fn in food_detail.get("foodNutrients", []):
        # Format B: nutrient info nằm trong fn["nutrient"]
        nutrient_info = fn.get("nutrient", fn)  # fallback về fn nếu là format A
        nutrient_number = str(nutrient_info.get("number", ""))

        if nutrient_number in TARGET_NUTRIENTS:
            field_name = TARGET_NUTRIENTS[nutrient_number]
            amount_per_100g = fn.get("amount", 0) or 0.0
            # Chia 100 để có giá trị per gram
            result[field_name] = round(amount_per_100g / 100, 6)

    return result


def fetch_nutrients_batch(fdc_ids: list[int]) -> list[dict]:
    """Gọi POST /foods với batch ID, trả về list NutritionPerGram dicts.

    Args:
        fdc_ids: tối đa 20 fdcId (giới hạn của USDA API).

    Returns:
        list[dict] với keys: ingredient_name, calories_per_g, protein_per_g, ...
    """
    response = _post_with_retry(f"{BASE_URL}/foods", {"fdcIds": fdc_ids})

    results: list[dict] = []
    for food_detail in response.json():
        nutrients = extract_nutrients(food_detail)

        # Chỉ giữ lại những item có ít nhất 1 nutrient > 0
        if any(v > 0 for v in nutrients.values()):
            results.append({
                "ingredient_name": food_detail.get("description", ""),
                **nutrients,
                "source": food_detail.get("dataType", "unknown").lower(),
            })

    return results


# ─── Step 3: Batch loop + save ────────────────────────────────────────────────


def process_all_foods(foods: list[dict]) -> list[dict]:
    """Duyệt toàn bộ danh sách foods theo batch, gọi API lấy nutrients.

    Returns:
        list[dict] — mỗi dict là 1 NutritionPerGram-ready record.
    """
    all_results: list[dict] = []
    total = len(foods)
    fdc_ids = [f["fdcId"] for f in foods]

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


def save_results(results: list[dict], filename: str = "usda_ingredients.json") -> Path:
    """Lưu kết quả ra file JSON trong data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / filename

    print(f"[3/3] Đang lưu {len(results)} ingredients vào {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    file_size = output_path.stat().st_size / 1024
    print(f"    → Đã lưu! File size: {file_size:.1f} KB\n")
    return output_path


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Pipeline chính: list → nutrients → save."""
    if not settings.usda_api_key:
        print("LỖI: USDA_API_KEY chưa được cấu hình trong .env")
        print("Thêm dòng: USDA_API_KEY=your_key_here")
        sys.exit(1)

    foods = fetch_food_list()
    if not foods:
        print("Không lấy được dữ liệu nào. Kiểm tra API key hoặc network.")
        sys.exit(1)

    results = process_all_foods(foods)
    save_results(results)

    # In 5 món mẫu
    print("Mẫu 5 ingredients đầu tiên:")
    for item in results[:5]:
        print(f"  {item['ingredient_name']}: "
              f"cal={item.get('calories_per_g', 0):.4f}/g, "
              f"protein={item.get('protein_per_g', 0):.4f}/g, "
              f"fat={item.get('fat_per_g', 0):.4f}/g, "
              f"carbs={item.get('carbs_per_g', 0):.4f}/g, "
              f"fiber={item.get('fiber_per_g', 0):.4f}/g")


if __name__ == "__main__":
    main()
