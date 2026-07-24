"""Làm sạch vn_dishes: deduplicate + LLM search gram.

Dùng LLM (DeepSeek/OpenCode API) để:
  1. Với mỗi nhóm trùng lặp → chọn bản đúng nhất, xóa bản sai
  2. Với mỗi món chưa có typical_grams → hỏi LLM gram chuẩn
  3. Verify calories có hợp lý không

Chạy:
  uv run python scripts/cleanup_vn_dishes.py --batch 50    # xử lý 50 món/lần
  uv run python scripts/cleanup_vn_dishes.py --dry-run     # chỉ xem, không sửa
"""

import asyncio
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text

from backend.db.postgres import async_session
from backend.config import settings

# ─── Helpers ───────────────────────────────────────────────────────────────

def normalize(name: str) -> str:
    s = unicodedata.normalize('NFKD', name.lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


async def ask_llm(prompt: str, fallback_model: str = "qwen3.5-plus") -> dict:
    """Gọi LLM text-only để phân tích dinh dưỡng. Fallback sang qwen nếu deepseek fail."""
    models = ["deepseek-v4-pro", fallback_model]
    last_error = None

    for model in models:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {settings.vision_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{settings.vision_api_base}/chat/completions",
                    json=body, headers=headers,
                )
            if r.status_code != 200:
                last_error = f"HTTP {r.status_code}"
                continue

            content = r.json()["choices"][0]["message"]["content"]
            if not content or not content.strip():
                last_error = "empty response"
                continue

            # Parse JSON
            content = content.strip()
            if "```" in content:
                parts = content.split("```")
                if len(parts) >= 2:
                    content = parts[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()

            return json.loads(content)
        except (json.JSONDecodeError, httpx.ReadTimeout, httpx.ConnectError) as e:
            last_error = str(e)[:100]
            continue

    raise RuntimeError(f"All models failed: {last_error}")


# ─── Main ──────────────────────────────────────────────────────────────────


async def process_duplicates(session, dry_run: bool = False) -> int:
    """Xử lý các nhóm trùng lặp: chọn bản đúng nhất, xóa bản sai."""
    r = await session.execute(text("SELECT id, dish_name FROM vn_dishes ORDER BY dish_name"))
    rows = r.all()

    # Group by normalized name
    groups = {}
    for rid, name in rows:
        key = normalize(name)
        if key not in groups:
            groups[key] = []
        groups[key].append((rid, name))

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    removed = 0

    for key, items in dupes.items():
        if len(items) <= 1:
            continue

        # Get full data for each duplicate
        ids = [it[0] for it in items]
        placeholders = ','.join([f"'{i}'" for i in ids])
        r = await session.execute(text(f"""
            SELECT id, dish_name, total_calories, total_protein_g,
                   total_fat_g, total_carbs_g, total_fiber_g, typical_grams
            FROM vn_dishes WHERE id IN ({placeholders})
        """))
        variants = {}
        for row in r.all():
            variants[str(row[0])] = {
                "name": row[1], "cal": row[2], "protein": row[3],
                "fat": row[4], "carbs": row[5], "fiber": row[6],
                "grams": row[7],
            }

        # Nếu chỉ khác ID nhưng giống hệt data → xóa duplicates giữ 1
        unique_datas = {}
        for vid, vdata in variants.items():
            data_key = (vdata["cal"], vdata["protein"], vdata["fat"],
                        vdata["carbs"], vdata["fiber"], vdata["grams"])
            if data_key not in unique_datas:
                unique_datas[data_key] = []
            unique_datas[data_key].append(vid)

        if len(unique_datas) == 1:
            # Tất cả giống nhau → giữ 1, xóa còn lại
            keep = list(unique_datas.values())[0][0]
            for data_key, id_list in unique_datas.items():
                for vid in id_list:
                    if vid != keep:
                        if not dry_run:
                            await session.execute(text(
                                "DELETE FROM vn_dishes WHERE id = :id"
                            ), {"id": vid})
                        removed += 1
            continue

        # Có variants khác nhau → dùng LLM chọn bản đúng nhất
        prompt = f"""Cho biết đâu là giá trị dinh dưỡng ĐÚNG NHẤT cho món "{items[0][1][:60]}".

Các variants từ database (mỗi dòng = 1 variant, có thể trùng hoặc khác):
"""
        for i, (vid, vdata) in enumerate(variants.items()):
            g = f" ({vdata['grams']}g)" if vdata['grams'] else ""
            prompt += f"  [{chr(65+i)}] {vdata['cal']:.0f} cal, P={vdata['protein']:.1f}g, F={vdata['fat']:.1f}g, C={vdata['carbs']:.1f}g, Fiber={vdata['fiber']:.1f}g{g}\n"

        prompt += """
Trả về CHỈ JSON: {"best": "A", "reason": "lý do ngắn gọn", "typical_grams": số hoặc null}
Nếu có typical_grams, ghi số gram chuẩn của 1 khẩu phần món này.
Nếu nhiều variant giống nhau, chọn cái đầu tiên."""

        try:
            result = await ask_llm(prompt)
            best_letter = result.get("best", "A")
            best_idx = ord(best_letter) - ord('A')
            best_id = list(variants.keys())[best_idx]

            # Update typical_grams nếu LLM suggest
            llm_grams = result.get("typical_grams")
            if llm_grams and isinstance(llm_grams, (int, float)) and 50 <= llm_grams <= 3000:
                # Chỉ update nếu chưa có
                if not variants[best_id]["grams"]:
                    if not dry_run:
                        await session.execute(text(
                            "UPDATE vn_dishes SET typical_grams = :g WHERE id = :id"
                        ), {"g": float(llm_grams), "id": best_id})

            # Xóa tất cả variants KHÔNG phải best
            for vid in variants:
                if vid != best_id:
                    if not dry_run:
                        await session.execute(text(
                            "DELETE FROM vn_dishes WHERE id = :id"
                        ), {"id": vid})
                    removed += 1

            print(f"  ✅ '{items[0][1][:40]}' ×{len(items)}: kept {best_letter}"
                  f"{' + grams='+str(llm_grams) if llm_grams else ''}")

        except Exception as e:
            print(f"  ⚠️  LLM fail for '{items[0][1][:40]}': {e}")
            # Fallback: giữ variant đầu tiên
            keep = list(variants.keys())[0]
            for vid in variants:
                if vid != keep:
                    if not dry_run:
                        await session.execute(text(
                            "DELETE FROM vn_dishes WHERE id = :id"
                        ), {"id": vid})
                    removed += 1

    return removed


async def process_missing_grams(session, batch: int, dry_run: bool = False) -> int:
    """Dùng LLM tìm typical_grams cho món chưa có."""
    r = await session.execute(text("""
        SELECT id, dish_name, total_calories, total_protein_g,
               total_fat_g, total_carbs_g
        FROM vn_dishes
        WHERE typical_grams IS NULL
        ORDER BY dish_name
        LIMIT :limit
    """), {"limit": batch})
    rows = r.all()

    updated = 0
    for row in rows:
        dish_id, name, cal, p, f_val, c = row
        prompt = f"""Món "{name}" có {cal:.0f} calories, {p:.1f}g protein, {f_val:.1f}g fat, {c:.1f}g carbs.

Dựa trên kiến thức ẩm thực Việt Nam, hãy cho biết:
1. 1 khẩu phần chuẩn của món này nặng bao nhiêu gram? (vd: 1 tô phở ~500g, 1 ổ bánh mì ~250g, 1 đĩa cơm ~400g)
2. Calories này có hợp lý cho khẩu phần đó không? Nếu KHÔNG, ghi lại calories đúng.

Trả về CHỈ JSON:
{{"typical_grams": số, "calories_ok": true/false, "correct_calories": số hoặc null, "reason": "lý do ngắn"}}"""

        try:
            result = await ask_llm(prompt)
            grams = result.get("typical_grams")
            if grams and isinstance(grams, (int, float)) and 50 <= grams <= 3000:
                if not dry_run:
                    await session.execute(text(
                        "UPDATE vn_dishes SET typical_grams = :g WHERE id = :id"
                    ), {"g": float(grams), "id": dish_id})
                updated += 1

                # Nếu calories sai → sửa
                if not result.get("calories_ok") and result.get("correct_calories"):
                    correct_cal = float(result["correct_calories"])
                    if 50 <= correct_cal <= 2500:
                        if not dry_run:
                            await session.execute(text(
                                "UPDATE vn_dishes SET total_calories = :cal WHERE id = :id"
                            ), {"cal": correct_cal, "id": dish_id})
                        print(f"  ✅ {name[:55]:55s} → {grams:.0f}g, cal {cal:.0f}→{correct_cal:.0f}")
                        continue

                print(f"  ✅ {name[:55]:55s} → {grams:.0f}g")
            else:
                print(f"  ⚠️  {name[:55]:55s} no valid grams from LLM")

        except Exception as e:
            print(f"  ❌ {name[:50]:50s} LLM error: {e}")

    return updated


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=30,
                        help="Số món xử lý tối đa cho missing grams")
    parser.add_argument("--dry-run", action="store_true",
                        help="Chỉ phân tích, không sửa DB")
    parser.add_argument("--skip-dedup", action="store_true",
                        help="Bỏ qua bước deduplicate")
    parser.add_argument("--skip-grams", action="store_true",
                        help="Bỏ qua bước tìm grams")
    args = parser.parse_args()

    async with async_session() as session:
        if not args.skip_dedup:
            print("=" * 60)
            print("STEP 1: Deduplicate")
            print("=" * 60)
            removed = await process_duplicates(session, dry_run=args.dry_run)
            if not args.dry_run:
                await session.commit()
            print(f"\nRemoved {removed} duplicate rows")

        if not args.skip_grams:
            print("\n" + "=" * 60)
            print("STEP 2: LLM search typical_grams")
            print("=" * 60)
            updated = await process_missing_grams(session, batch=args.batch,
                                                   dry_run=args.dry_run)
            if not args.dry_run:
                await session.commit()
            print(f"\nUpdated {updated} dishes with typical_grams")

        # Stats
        r = await session.execute(text("SELECT COUNT(*) FROM vn_dishes"))
        total = r.scalar()
        r = await session.execute(text(
            "SELECT COUNT(*) FROM vn_dishes WHERE typical_grams IS NOT NULL"
        ))
        with_grams = r.scalar()
        print(f"\n{'='*60}")
        print(f"Total: {total} dishes")
        print(f"With typical_grams: {with_grams} ({with_grams/max(total,1)*100:.1f}%)")

asyncio.run(main())
