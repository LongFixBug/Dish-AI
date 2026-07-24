"""Strip English tên món trong ngoặc + dedup vn_dishes.

VD: "Phở bò xào (Stir-fried beef pho)" → "Phở bò xào"
    "Nem nướng (5 cái) (Grilled pork rolls (5 pieces))" → "Nem nướng (5 cái)"

Cách hoạt động: split theo dấu ngoặc "(" → giữ các phần không chứa
tiếng Anh (>=3 ký tự liên tiếp alphabet), ghép lại.

Chạy: DEBUG=false python scripts/clean_vn_dish_names.py
"""

import asyncio
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from backend.db.postgres import async_session

# Một segment chứa >=3 chữ cái alphabet liên tiếp → coi là tiếng Anh
_HAS_EN = re.compile(r"[A-Za-z]{3,}")


def clean_name(name: str) -> str:
    """Strip từng lớp ngoặc CUỐI CÙNG nếu có tiếng Anh (>=3 alphabet liên tiếp).

    Chỉ xét ngoặc ở đuôi — VD:
      "Xúc xích rán (5 cái) (Fried sausages (5 pieces))"
      → lần 1: ngoặc cuối "(Fried sausages (5 pieces))" có EN → strip
      → "Xúc xích rán (5 cái)"
      → lần 2: ngoặc cuối "(5 cái)" không có EN → dừng
    """
    name = name.strip()
    while True:
        if not name.endswith(")"):
            break
        # Tìm dấu "(" mở khớp với ")" cuối cùng
        depth = 0
        open_idx = -1
        for i in range(len(name) - 1, -1, -1):
            if name[i] == ")":
                depth += 1
            elif name[i] == "(":
                depth -= 1
                if depth == 0:
                    open_idx = i
                    break
        if open_idx < 0:
            break  # unmatched paren
        content = name[open_idx + 1 : -1]  # nội dung trong ngoặc
        if _HAS_EN.search(content):
            # Có tiếng Anh → strip ngoặc này và lặp
            name = name[:open_idx].strip()
        else:
            # Không có tiếng Anh → đây là ngoặc tiếng Việt, dừng
            break
    return name


async def main():
    async with async_session() as s:
        r = await s.execute(text("SELECT id, dish_name FROM vn_dishes ORDER BY id"))
        rows = list(r.fetchall())

        total = len(rows)
        updates: list[tuple[str, str]] = []
        cleaned_map: dict[str, list[str]] = {}

        for row_id, name in rows:
            cleaned = clean_name(name)
            if cleaned != name:
                updates.append((str(row_id), cleaned))
            cleaned_map.setdefault(cleaned, []).append(str(row_id))

        print(f"Total: {total}")
        print(f"Need update (has English): {len(updates)}")
        print(f"Unique after clean: {len(cleaned_map)}")

        # Show a few examples
        for row_id, name in rows:
            cleaned = clean_name(name)
            if cleaned != name:
                print(f"  [{name}] → [{cleaned}]")
                if len(updates) > 10:
                    print(f"  ... and {len(updates) - 1} more")
                    break

        dups = {k: v for k, v in cleaned_map.items() if len(v) > 1}
        print(f"\nDuplicate groups: {len(dups)}")

        if not updates and not dups:
            print("✅ Nothing to do!")
            return

        # Update names
        print(f"\nUpdating {len(updates)} names...")
        for row_id, cleaned in updates:
            await s.execute(
                text("UPDATE vn_dishes SET dish_name = :nm WHERE id = CAST(:uid AS uuid)"),
                {"nm": cleaned, "uid": row_id},
            )

        # Dedup: keep best row (has grams, prefer vnmeal source)
        deleted = 0
        for name, ids in dups.items():
            r2 = await s.execute(
                text(
                    "SELECT id::text, typical_grams, source FROM vn_dishes "
                    "WHERE id::text = ANY(CAST(:ids AS text[])) "
                    "ORDER BY typical_grams DESC NULLS LAST, "
                    "CASE WHEN source='vnmeal' THEN 0 ELSE 1 END"
                ),
                {"ids": ids},
            )
            ranked = list(r2.fetchall())
            keep_id = str(ranked[0][0])
            for did in ids:
                if did != keep_id:
                    await s.execute(
                        text("DELETE FROM vn_dishes WHERE id = CAST(:uid AS uuid)"),
                        {"uid": did},
                    )
                    deleted += 1

        await s.commit()
        print(f"✅ Done! Updated: {len(updates)} names, Deleted: {deleted} dups")

        # Verify
        r = await s.execute(text("SELECT count(*) FROM vn_dishes"))
        remaining = r.scalar()
        r2 = await s.execute(
            text("SELECT count(*) FROM vn_dishes WHERE dish_name ~ '[(][A-Za-z]'")
        )
        still_en = r2.scalar()
        print(f"Remaining: {remaining} rows ({still_en} still have English)")
        if still_en > 0:
            print("\nRemaining EN names:")
            r3 = await s.execute(
                text("SELECT dish_name FROM vn_dishes WHERE dish_name ~ '[(][A-Za-z]'")
            )
            for row in r3:
                print(f"  [{row[0]}]")


if __name__ == "__main__":
    asyncio.run(main())
