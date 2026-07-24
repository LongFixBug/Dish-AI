"""Seed typical_grams cho vn_dishes — chỉ dùng keyword dài, độ tin cậy cao.

Chỉ match keyword ≥ 5 ký tự để tránh false match (vd: "bánh đa" match "bánh đa cua" sai).
Chạy: uv run python scripts/seed_grams_v2.py
"""

import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.db.postgres import async_session
from sqlalchemy import text

# Chỉ dùng keyword ≥ 5 ký tự, cân nặng thực tế cho 1 khẩu phần
MANUAL = {
    # Món nước - tô lớn
    "phở bò": 500, "phở gà": 500, "phở xào": 400, "phở cuốn": 300,
    "bún bò": 550, "bún chả": 450, "bún riêu": 500, "bún thịt nướng": 400,
    "bún đậu": 450, "bún ốc": 500, "bún mọc": 500, "bún măng": 500,
    "bún ngan": 500, "bún tôm": 450, "bún cá": 500, "bún mắm": 500,
    "bún thang": 500, "bún sườn": 500,
    "hủ tiếu": 500, "hủ tíu": 500, "mì quảng": 450,
    "mì vằn thắn": 500, "mì hoành thánh": 500, "mì xào": 400,
    "mì trộn": 400, "mì tôm": 400, "mì gà": 450,
    "miến lươn": 450, "miến xào": 400, "miến cua": 450, "miến gà": 450, "miến trộn": 400,
    "bánh canh": 500,
    "bánh đa cua": 500, "bánh đa trộn": 450,
    "cháo lòng": 450, "cháo gà": 450, "cháo sườn": 450, "cháo vịt": 450,
    "cháo cá": 450, "cháo ếch": 450, "cháo trai": 450, "cháo ngao": 450,
    "cháo huyết": 450, "cháo bò": 450, "cháo hến": 450, "cháo đậu": 400,
    "cháo trắng": 350, "cháo tôm": 400,

    # Cơm
    "cơm tấm": 450, "cơm sườn": 450, "cơm gà": 400, "cơm rang": 350,
    "cơm chiên": 350, "cơm hến": 350, "cơm dừa": 350, "cơm niêu": 400,
    "cơm suất": 450, "cơm đĩa": 450,

    # Bánh mì
    "bánh mì": 250, "bánh mỳ": 250,

    # Bánh truyền thống
    "bánh xèo": 200, "bánh cuốn": 300, "bánh bèo": 150, "bánh bao": 150,
    "bánh chưng": 800, "bánh tét": 800, "bánh giò": 250, "bánh giầy": 100,
    "bánh dày": 100, "bánh đúc": 250, "bánh cam": 80, "bánh rán": 80,
    "bánh tiêu": 60, "bánh bò": 100, "bánh ít": 80, "bánh tôm": 100,
    "bánh khúc": 120, "bánh gối": 100, "bánh gai": 100,
    "bánh trôi": 150, "bánh chay": 150, "bánh tráng": 30,
    "bánh phở": 200, "bánh ướt": 250, "bánh hỏi": 200,
    "bánh bông lan": 100, "bánh flan": 100, "bánh quẩy": 50,
    "bánh quế": 30, "bánh gạo": 30, "bánh đậu xanh": 80,
    "bánh cốm": 80, "bánh chuối": 80, "bánh khoai": 80,
    "bánh dẻo": 150, "bánh nướng": 150, "bánh pía": 150,
    "bánh trung thu": 180, "bánh in": 30,
    "bánh bột lọc": 120, "bánh nậm": 100, "bánh lá": 100,

    # Gỏi / cuốn / nem
    "gỏi cuốn": 150, "nem rán": 100, "nem chua": 50, "chả giò": 80,
    "chả cá": 100, "chả lụa": 100, "chả mực": 100, "chả tôm": 100,
    "chả cốm": 100,

    # Chè / xôi
    "chè đậu": 300, "chè bắp": 300, "chè chuối": 300, "chè khoai": 300,
    "chè ba màu": 350, "chè thập cẩm": 350, "chè hạt sen": 300,
    "chè khúc bạch": 300, "chè bưởi": 300, "chè bà ba": 300,
    "xôi gấc": 300, "xôi đậu": 300, "xôi lạc": 300, "xôi vò": 300,
    "xôi ngô": 300, "xôi mặn": 300, "xôi gà": 300, "xôi thịt": 300,
    "xôi trứng": 250, "xôi xoài": 300, "xôi lá cẩm": 300, "xôi lá dứa": 300,

    # Đồ uống
    "sinh tố": 350, "nước ép": 250, "nước mía": 300,
    "cà phê sữa": 200, "cà phê đen": 150, "cà phê trứng": 200,
    "cà phê cốt dừa": 250, "trà sữa": 400, "trà đào": 350,
    "trà chanh": 300,
    "sữa chua": 100, "sữa tươi": 250, "sữa đậu nành": 250,
    "sữa bắp": 250, "kem": 100, "chè": 300, "sương sa": 250,
    "rau câu": 150, "tàu hũ": 200,

    # Thịt quay / gà / vịt
    "vịt quay": 1200, "gà quay": 1000, "gà luộc": 1200,
    "gà tần": 800, "gà hấp": 800, "gà rang": 400, "gà xào": 350,
    "heo quay": 1500, "lợn quay": 1500, "lợn sữa quay": 2000,

    # Món xào / kho / nướng
    "thịt kho": 300, "cá kho": 300, "sườn nướng": 300,
    "bò nướng": 300, "bò xào": 350, "bò lúc lắc": 300,
    "mực xào": 300, "tôm xào": 250, "tôm rang": 250,
    "đậu phụ": 200, "đậu sốt": 250,

    # Lẩu
    "lẩu thập cẩm": 1200, "lẩu hải sản": 1200, "lẩu gà": 1000,
    "lẩu bò": 1200, "lẩu riêu": 1200, "lẩu mắm": 1200,
    "lẩu cá": 1000, "lẩu dê": 1200,

    # Canh
    "canh chua": 400, "canh bí": 350, "canh rau": 350,
    "canh cua": 400, "canh mướp": 350, "canh khoai": 350,
}


async def main():
    async with async_session() as session:
        # Clear all first
        await session.execute(text("UPDATE vn_dishes SET typical_grams = NULL"))
        print("Cleared all typical_grams")

        updated = 0
        for keyword, grams in sorted(MANUAL.items(), key=lambda x: -len(x[0])):
            if len(keyword) < 5:
                continue
            # Match dish_name chứa keyword
            r = await session.execute(text("""
                UPDATE vn_dishes SET typical_grams = :grams
                WHERE typical_grams IS NULL AND dish_name ILIKE '%' || :kw || '%'
            """), {"grams": grams, "kw": keyword})
            if r.rowcount > 0:
                updated += r.rowcount
        await session.commit()

        r = await session.execute(text("SELECT COUNT(*) FROM vn_dishes WHERE typical_grams IS NOT NULL"))
        print(f"Seeded: {r.scalar()} dishes with typical_grams")
        r = await session.execute(text("SELECT COUNT(*) FROM vn_dishes"))
        total = r.scalar()
        print(f"Total: {total}, Coverage: {r.scalar()/total*100:.1f}%")

        # Verify suspicious
        r = await session.execute(text("""
            SELECT COUNT(*) FROM vn_dishes
            WHERE typical_grams IS NOT NULL
              AND (total_calories / NULLIF(typical_grams,0) < 0.3
                   OR total_calories / NULLIF(typical_grams,0) > 5)
        """))
        suspicious = r.scalar()
        print(f"Suspicious cal/g (<0.3 or >5): {suspicious}")

asyncio.run(main())
