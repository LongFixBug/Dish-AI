"""Deduplicate vn_dishes bằng SQL rules - không dùng LLM."""
import asyncio
import sys
import unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.postgres import async_session
from sqlalchemy import text

def normalize(name):
    s = unicodedata.normalize('NFKD', name.lower())
    return ''.join(c for c in s if not unicodedata.combining(c))

async def main():
    async with async_session() as session:
        r = await session.execute(text(
            "SELECT id, dish_name, typical_grams, total_calories FROM vn_dishes ORDER BY dish_name"
        ))
        rows = r.all()

        groups = {}
        for rid, name, grams, cal in rows:
            key = normalize(name)
            if key not in groups:
                groups[key] = []
            groups[key].append((rid, name, grams, cal))

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"Groups: {len(groups)} unique, {len(dupes)} with duplicates")

        to_delete = []
        for key, items in dupes.items():
            with_g = [i for i in items if i[2] is not None]
            without_g = [i for i in items if i[2] is None]

            if with_g and without_g:
                for i in without_g:
                    to_delete.append(i[0])
                continue
            if with_g:
                cals = sorted(with_g, key=lambda x: x[3])
                keep = cals[len(cals) // 2]
                for i in cals:
                    if i[0] != keep[0]:
                        to_delete.append(i[0])
                continue
            cals = sorted(items, key=lambda x: x[3])
            keep = cals[len(cals) // 2]
            for i in cals:
                if i[0] != keep[0]:
                    to_delete.append(i[0])

        print(f"To delete: {len(to_delete)}")

        if to_delete:
            for i in range(0, len(to_delete), 100):
                batch = to_delete[i:i+100]
                ph = ','.join([f"'{x}'" for x in batch])
                await session.execute(text(f"DELETE FROM vn_dishes WHERE id IN ({ph})"))
            await session.commit()

        r = await session.execute(text("SELECT COUNT(*) FROM vn_dishes"))
        print(f"Remaining: {r.scalar()} dishes")
        r = await session.execute(text(
            "SELECT COUNT(*) FROM vn_dishes WHERE typical_grams IS NOT NULL"
        ))
        print(f"With grams: {r.scalar()}")

asyncio.run(main())
