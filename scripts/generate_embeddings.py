"""Sinh vector embedding cho tất cả ingredients trong DB.

Gọi llama.cpp embedding server (port 8081), lấy vector 1024 chiều,
UPDATE vào cột embedding của nutrition_ingredients.

Usage:
    python scripts/generate_embeddings.py
"""

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update, and_

from backend.db.models import NutritionIngredient
from backend.db.postgres import async_session
from backend.config import settings

# ─── Constants ──────────────────────────────────────────────────

EMBEDDING_API = f"{settings.embedding_url}/v1/embeddings"
BATCH_SIZE = 50      # Số ingredients gửi 1 lần
REQUEST_DELAY = 0.1   # Delay giữa các request để không quá tải
TIMEOUT = 30.0


# ─── Logic ──────────────────────────────────────────────────────

async def get_ingredients_without_embedding() -> list[NutritionIngredient]:
    """Lấy danh sách ingredients chưa có embedding."""
    async with async_session() as session:
        result = await session.execute(
            select(NutritionIngredient)
            .where(NutritionIngredient.embedding.is_(None))
        )
        return list(result.scalars().all())


async def generate_embeddings_batch(
    client: httpx.AsyncClient,
    ingredients: list[NutritionIngredient],
) -> list[list[float]]:
    """Gửi batch ingredient names lên embedding server, trả về list vector."""
    names = [ing.ingredient_name for ing in ingredients]

    response = await client.post(
        EMBEDDING_API,
        json={
            "input": names,
            "model": settings.embedding_model,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    # Trả về list các vector, giữ đúng thứ tự
    return [item["embedding"] for item in data["data"]]


async def update_embeddings(
    ingredients: list[NutritionIngredient],
    embeddings: list[list[float]],
) -> int:
    """UPDATE embedding vào DB, trả về số dòng đã update."""
    async with async_session() as session:
        count = 0
        for ing, emb in zip(ingredients, embeddings):
            await session.execute(
                update(NutritionIngredient)
                .where(NutritionIngredient.id == ing.id)
                .values(embedding=emb)
            )
            count += 1
        await session.commit()
    return count


async def main() -> None:
    """Duyệt toàn bộ ingredients chưa có embedding, sinh và lưu."""
    # Step 1: Đếm số cần làm
    ingredients = await get_ingredients_without_embedding()
    total = len(ingredients)

    if total == 0:
        print("✅ Tất cả ingredients đã có embedding rồi!")
        return

    print(f"📦 Cần sinh embedding cho {total} ingredients")
    print(f"   Embedding server: {settings.embedding_url}")
    print(f"   Model: {settings.embedding_model}")
    print(f"   Batch size: {BATCH_SIZE}\n")

    # Step 2: Gọi API theo batch
    async with httpx.AsyncClient() as client:
        total_updated = 0
        for i in range(0, total, BATCH_SIZE):
            batch = ingredients[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            try:
                embeddings = await generate_embeddings_batch(client, batch)
                updated = await update_embeddings(batch, embeddings)
                total_updated += updated
                print(
                    f"  batch {batch_num}/{total_batches}: "
                    f"+{updated} rows (tổng: {total_updated})"
                )
            except httpx.HTTPError as e:
                print(f"  batch {batch_num}/{total_batches}: LỖI → {e}")

            await asyncio.sleep(REQUEST_DELAY)

    print(f"\n✅ Đã sinh embedding cho {total_updated}/{total} ingredients!\n")


if __name__ == "__main__":
    asyncio.run(main())
