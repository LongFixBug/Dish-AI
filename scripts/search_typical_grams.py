"""Script tự động tìm typical_grams cho vn_dishes qua WebSearch.

Flow:
  1. SELECT dishes WHERE typical_grams IS NULL (limit N)
  2. Với mỗi món: WebSearch "tên món + khối lượng gram"
  3. Nếu tìm thấy số gram cụ thể → UPDATE typical_grams
  4. Nếu không tìm thấy → skip

Dùng batch để test với 10-20 món trước, sau đó scale lên toàn bộ.

Chạy: uv run python scripts/search_typical_grams.py [--batch 20]
"""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.db.postgres import async_session


def parse_grams_from_snippet(snippet: str) -> float | None:
    """Tìm số gram trong 1 đoạn text.

    Pattern: "500g" | "500 gram" | "~500g" | "khoảng 500g" | "500-600g"
    Chỉ lấy giá trị gram hợp lý (50-3000g).
    """
    if not snippet:
        return None

    # Normalize: bỏ dấu ~ ≈ khoảng, lowercase
    s = snippet.lower()
    s = re.sub(r'[~≈]', '', s)

    # Pattern 1: "XXXg" hoặc "XXX g" hoặc "XXX gram" (phổ biến nhất)
    matches = re.findall(r'(?:khoảng\s*)?(\d{2,4})\s*(?:g|gram|gam)\b', s)
    if matches:
        for m in matches:
            val = float(m)
            if 50 <= val <= 3000:
                return val

    # Pattern 2: "XXX-XXXg" → lấy trung bình
    matches = re.findall(r'(\d{2,4})\s*[-–]\s*(\d{2,4})\s*(?:g|gram|gam)\b', s)
    if matches:
        for low, high in matches:
            val = (float(low) + float(high)) / 2
            if 50 <= val <= 3000:
                return val

    # Pattern 3: "khẩu phần XXXg" hoặc "serving XXXg"
    matches = re.findall(r'(?:khẩu\s*phần|serving|portion|suất)\s*(?:khoảng\s*)?(\d{2,4})\s*(?:g|gram|gam)?', s)
    if matches:
        for m in matches:
            val = float(m)
            if 50 <= val <= 3000:
                return val

    return None


# ─── Từ điển thủ công cho các món phổ biến ───────────────────────────────

MANUAL_GRAMS: dict[str, float] = {
    # Món nước (tô lớn ~500g)
    "phở": 500, "bún": 500, "hủ tiếu": 500, "mì": 450, "miến": 450,
    "bánh canh": 500, "cháo": 450, "súp": 350, "canh": 300,
    "lẩu": 1200,
    # Cơm (đĩa/ phần)
    "cơm": 400, "cơm chiên": 350, "cơm rang": 350,
    # Bánh
    "bánh mì": 250, "bánh xèo": 200, "bánh cuốn": 300,
    "bánh bèo": 150, "bánh bao": 150, "bánh chưng": 800,
    "bánh tét": 800, "bánh giò": 200, "bánh dày": 100,
    "bánh tráng": 30, "bánh đa": 20, "bánh đúc": 200,
    "bánh bông lan": 100, "bánh flan": 100, "bánh cam": 80,
    "bánh rán": 80, "bánh tiêu": 60, "bánh bò": 100,
    "bánh ít": 80, "bánh tôm": 100, "bánh khúc": 100,
    "bánh gối": 100, "bánh phở": 200, "bánh ướt": 250,
    # Gỏi / cuốn
    "gỏi cuốn": 150, "nem": 100, "chả giò": 80,
    "chả": 100, "nem rán": 100,
    # Chè / xôi
    "chè": 300, "xôi": 300, "bánh trôi": 150, "bánh chay": 150,
    # Đồ uống
    "sữa": 250, "sinh tố": 350, "nước": 300, "trà": 250,
    "cà phê": 200, "nước ép": 250, "nước mía": 300,
    "sữa chua": 100, "kem": 100,
    # Thịt quay / món khô
    "vịt quay": 1200, "gà quay": 1000, "heo quay": 1500,
    "gà luộc": 1200, "vịt luộc": 1000,
    # Món xào
    "xào": 350, "rán": 250, "chiên": 250, "kho": 300,
    "hấp": 350, "nướng": 300, "om": 400,
}


async def search_and_update(batch_size: int = 20, use_manual_only: bool = True) -> int:
    """Tìm typical_grams cho dishes chưa có.

    Args:
        batch_size: số món xử lý tối đa
        use_manual_only: chỉ dùng MANUAL_GRAMS, không gọi WebSearch
    Returns:
        số món đã updated
    """
    total_updated = 0

    async with async_session() as session:
        # Lấy danh sách dishes chưa có typical_grams
        result = await session.execute(text("""
            SELECT id, dish_name FROM vn_dishes
            WHERE typical_grams IS NULL
            ORDER BY dish_name
            LIMIT :limit
        """), {"limit": batch_size})

        dishes = [(row[0], row[1]) for row in result.all()]
        print(f"Found {len(dishes)} dishes without typical_grams (batch={batch_size})")

        for dish_id, dish_name in dishes:
            grams = None

            # Step 1: Check MANUAL_GRAMS (từ điển thủ công)
            # Ưu tiên keyword DÀI hơn (cụ thể hơn) trước
            name_lower = dish_name.lower()
            matched_kw = None
            matched_weight = 0.0
            for keyword, weight in MANUAL_GRAMS.items():
                if keyword in name_lower:
                    if len(keyword) > len(matched_kw or ""):
                        matched_kw = keyword
                        matched_weight = weight
            if matched_kw:
                grams = matched_weight
                keyword = matched_kw

            # Step 2: Nếu không dùng manual-only và có WebSearch tool → tự động search
            # (bỏ qua trong prototype này - dùng manual là đủ ổn)
            if grams is None and not use_manual_only:
                # TODO: integrate WebSearch API
                pass

            if grams is not None:
                await session.execute(text("""
                    UPDATE vn_dishes SET typical_grams = :grams WHERE id = :id
                """), {"grams": grams, "id": dish_id})
                total_updated += 1
                print(f"  ✅ {dish_name[:60]:60s} → {grams:.0f}g  [{keyword}]")
            else:
                if total_updated % 50 == 0 and total_updated > 0:
                    print(f"  ... skipped {total_updated} so far ...")

        await session.commit()

    return total_updated


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=500, help="Số món xử lý tối đa")
    parser.add_argument("--manual-only", action="store_true", default=True,
                        help="Chỉ dùng từ điển thủ công, không gọi WebSearch")
    args = parser.parse_args()

    updated = await search_and_update(
        batch_size=args.batch,
        use_manual_only=args.manual_only,
    )
    print(f"\n✅ Total updated: {updated} dishes")

    # In thống kê
    async with async_session() as session:
        r = await session.execute(text(
            "SELECT COUNT(*) FROM vn_dishes WHERE typical_grams IS NOT NULL"
        ))
        with_grams = r.scalar()
        r = await session.execute(text("SELECT COUNT(*) FROM vn_dishes"))
        total = r.scalar()
        print(f"Coverage: {with_grams}/{total} ({with_grams/total*100:.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
