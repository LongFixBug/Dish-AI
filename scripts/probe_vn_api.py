"""Probe API Viện Dinh Dưỡng — in keys item gốc để check có field phân loại không.

Mục đích: Task #7 (re-parse metadata fix item_type) cần biết response gốc của 2
endpoint có field category/food_group/type không. Script parse_vn_foods.py hiện
chỉ giữ 7 field {ingredient_name, *_per_g, source} — có thể đã BỎ metadata phân
loại. Script này probe 1 page mỗi endpoint, in TẤT CẢ keys của item đầu tiên +
dump 1 item mẫu full JSON.

Read-only: KHÔNG ghi file, KHÔNG sửa data. Chỉ in ra console để người đọc quyết
định có re-parse VN hay không.

Kỳ vọng (dựa schema vn_foods.json hiện có 7 field): API không trả field category
→ giữ nguyên phân loại VN hiện có và chỉ re-parse nguồn USDA.

Usage:
    python scripts/probe_vn_api.py
"""

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Constants (copy từ parse_vn_foods.py — DRY: script không export sạch) ─────

BASE_URL = "https://viendinhduong.vn"
FOOD_API = "/api/fe/foodNatunal/getPageFoodData"   # nguyên liệu thô
MEAL_API = "/api/fe/tool/getPageFoodData"           # món ăn nấu sẵn

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

TIMEOUT = 30.0


def _probe_endpoint(client: httpx.Client, name: str, api_path: str) -> None:
    """Probe 1 page của 1 endpoint: in keys item đầu + dump full JSON mẫu."""
    print(f"\n=== {name} ({api_path}) ===")
    try:
        response = client.get(
            f"{BASE_URL}{api_path}",
            params={"page": 1},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  ❌ Lỗi gọi API: {e}")
        return

    data = response.json()
    items = data.get("data", [])
    total = data.get("total", 0)
    print(f"  total (API báo): {total}")
    print(f"  items page 1: {len(items)}")

    if not items:
        print("  ⚠ Không có item nào ở page 1")
        return

    first = items[0]
    keys = list(first.keys())
    print(f"  keys của item[0]: {keys}")

    # Tìm field phân loại tiềm năng (category/group/type/kind)
    candidates = [k for k in keys if any(
        word in k.lower() for word in ("category", "group", "type", "kind", "class")
    )]
    if candidates:
        print(f"  🎯 Field phân loại tiềm năng: {candidates}")
        for c in candidates:
            print(f"     {c} = {first.get(c)!r}")
    else:
        print("  → KHÔNG thấy field phân loại nào → VN giữ heuristic")

    print("  Mẫu item[0] full JSON:")
    print(json.dumps(first, ensure_ascii=False, indent=2)[:1200])


def main() -> None:
    """Probe cả 2 endpoint VN (foodNatunal + tool)."""
    print("Probe API Viện Dinh Dưỡng — tìm field phân loại (category/type/group)")
    with httpx.Client() as client:
        _probe_endpoint(client, "Thực phẩm (nguyên liệu)", FOOD_API)
        _probe_endpoint(client, "Món ăn (nấu sẵn)", MEAL_API)

    print("\n👉 Nếu 2 endpoint đều không có field phân loại → giữ phân loại VN hiện có,")
    print("   chỉ re-parse USDA bằng scripts/reparse_usda_category.py.")


if __name__ == "__main__":
    main()
