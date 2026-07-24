"""Dùng LLM batch (DeepSeek V4) search typical_grams cho vn_dishes.

Prompt chứa nhiều món 1 lần → LLM trả JSON array → parse → UPDATE DB.

Chạy: uv run python scripts/llm_search_grams.py --input /tmp/llm_grams_prompt.txt
"""

import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text

from backend.db.postgres import async_session
from backend.config import settings


async def ask_llm_batch(prompt: str) -> list[dict]:
    """Gửi prompt 1 lần, nhận JSON array."""
    body = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    headers = {"Authorization": f"Bearer {settings.vision_api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=180) as cl:
        r = await cl.post(f"{settings.vision_api_base}/chat/completions", json=body, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    finish = data["choices"][0].get("finish_reason", "")
    print(f"  LLM response: {len(content)} chars, finish={finish}")

    if not content or not content.strip():
        # Thử lấy reasoning_content (DeepSeek V4 có thể trả trong reasoning)
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        if reasoning:
            print(f"  Reasoning ({len(reasoning)} chars): {reasoning[:200]}...")
        return []

    # Parse JSON array
    content = content.strip()
    if "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Thử extract mảng JSON từ giữa text
        import re
        m = re.search(r'\[.*\]', content, re.DOTALL)
        if m:
            return json.loads(m.group())
        print(f"  Parse failed, content[:300]: {content[:300]}")
        return []


async def update_from_json(items: list[dict]):
    """Update typical_grams + nutrition cho mỗi item match được."""
    updated = 0
    async with async_session() as session:
        for item in items:
            name = item.get("name", "")
            grams = item.get("grams")
            if not name or not grams:
                continue
            if not isinstance(grams, (int, float)) or grams < 20 or grams > 3000:
                continue

            # Match bằng ILIKE substring trên tên gốc (không phân biệt hoa thường)
            r = await session.execute(text("""
                UPDATE vn_dishes SET typical_grams = :grams WHERE typical_grams IS NULL
                AND (dish_name ILIKE '%' || :name || '%'
                     OR dish_name ILIKE '%' || :name_short || '%')
                RETURNING dish_name
            """), {
                "grams": float(grams),
                "name": name,
                "name_short": name.split("(")[0].strip() if "(" in name else name,
            })
            rows = r.all()
            updated += len(rows)
            for row in rows:
                cal_info = f"cal={item.get('calories','?')}" if item.get('calories') else ""
                print(f"  ✅ {row[0][:55]:55s} → {grams:.0f}g {cal_info}")

        await session.commit()
    print(f"\nUpdated: {updated} dishes")


async def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="File chứa prompt")
    args = p.parse_args()

    prompt = Path(args.input).read_text()
    print(f"Prompt length: {len(prompt)} chars")
    print("Calling DeepSeek V4...")
    items = await ask_llm_batch(prompt)
    print(f"Got {len(items)} items from LLM")
    if items:
        await update_from_json(items)

asyncio.run(main())
