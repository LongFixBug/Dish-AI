"""Build eval dataset tiếng Việt cho RAGAS RAG eval.

Dataset ~30-50 query, mỗi query kèm ground_truth (list tên nguyên liệu mong đợi
CÓ TRONG DB). Mix: có dấu, không dấu, sai chính tả nhẹ — để test cả ILIKE (vn_norm)
lẫn vector fallback (cosine_distance).

Ground truth hand-curate (KHÔNG tự sinh từ search kết quả — sẽ circular, eval luôn
perfect). Mỗi ground_truth name được verify tồn tại trong DB qua `verify_ground_truth`
bỏ name không có → tránh reference sai làm RAGAS chấm nhầm.

Build SingleTurnSample cho RAGAS:
  - user_input: query
  - retrieved_contexts: list ingredient_name từ search_ingredients
  - reference: "; ".join(ground_truth)  (cần cho LLMContextRecall/Precision)
  - response: "; ".join(retrieved_contexts)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import func, literal, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from backend.db.models import NutritionIngredient  # noqa: E402
from backend.services.ingredients import search_ingredients  # noqa: E402

# ─── Eval queries (hand-curated) ──────────────────────────────────────────────
# (query, [ground_truth_names mong đợi CÓ trong DB], note)
# Ground truth = tên chính xác (substring) xuất hiện trong nutrition_ingredients.
# verify_ground_truth sẽ bỏ name không match ILIKE nào trong DB.

EVAL_QUERIES: list[tuple[str, list[str], str]] = [
    # ── Có dấu — ILIKE hit trực tiếp ──
    ("thịt bò", ["Thịt bò"], "có dấu — ingredient phổ biến"),
    ("thịt lợn", ["Thịt lợn"], "có dấu — ingredient"),
    ("thịt nạc", ["thịt nạc"], "có dấu"),
    ("trứng gà", ["Trứng gà"], "có dấu"),
    ("sữa bò", ["Sữa bò"], "có dấu"),
    ("cà chua", ["cà chua"], "có dấu — vegetable"),
    ("dưa hấu", ["dưa hấu"], "có dấu — fruit"),
    ("gạo", ["gạo"], "có dấu — grain"),
    ("đường", ["đường"], "có dấu"),
    ("cơm chiên", ["cơm chiên"], "có dấu — có thể dish (lọc)"),

    # ── Không dấu — test vn_norm ILIKE ──
    ("thit bo", ["thịt bò"], "không dấu — vn_norm ILIKE hit"),
    ("thit lon", ["thịt lợn"], "không dấu"),
    ("thit nac", ["thịt nạc"], "không dấu — nạc"),
    ("trung ga", ["trứng gà"], "không dấu — sai chính tả nhẹ (trung vs trứng)"),
    ("sua bo", ["sữa bò"], "không dấu"),
    ("ca chua", ["cà chua"], "không dấu"),
    ("dua hau", ["dưa hấu"], "không dấu — fruit"),
    ("com chien", ["cơm chiên"], "không dấu"),
    ("duong", ["đường"], "không dấu — 1 chữ"),
    ("muoi", ["muối"], "không dấu — 1 chữ"),
    ("dau an", ["dầu ăn"], "không dấu"),
    ("sua chua", ["sữa chua"], "không dấu — product?"),

    # ── Multi-word không dấu ──
    ("bun thit nac", ["bún thịt nướng", "thịt nạc"], "không dấu multi-word — vector fallback"),
    ("thit bo bap", ["thịt bò"], "không dấu — bắp bò"),
    ("ca chua tuoi", ["cà chua"], "không dấu + 'tươi'"),

    # ── Query là món (dish) — kỳ vọng retrieved rỗng/thiếu (lọc item_type) ──
    ("bun cha", ["bún chả"], "dish — autocomplete lọc (kỳ vọng miss hoặc 0)"),
    ("pho bo", ["phở bò"], "dish — lọc"),
    ("com tam", ["cơm tấm"], "dish — lọc"),

    # ── Sai chính tả nặng — test vector fallback ──
    ("sua ong", [], "sữa ong — có thể miss (đúng) hoặc vector móc sai"),
    ("rau muong", ["rau muống"], "không dấu — rau muống"),
    ("oi", ["ổi"], "không dấu 1 chữ — fruit ổi"),
    ("xoai", ["xoài"], "không dấu — fruit xoài"),
]


async def verify_ground_truth(session: AsyncSession, names: list[str]) -> list[str]:
    """Check mỗi ground_truth name có tồn tại trong DB (ILIKE vn_norm).

    Bỏ name không match → tránh reference sai. Trả list name đã verify.
    """
    verified: list[str] = []
    for name in names:
        if not name:
            continue
        stmt = (
            select(NutritionIngredient.id)
            .where(
                func.vn_norm(NutritionIngredient.ingredient_name).op("ILIKE")(
                    func.vn_norm(literal(f"%{name}%"))
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        if result.scalars().first():
            verified.append(name)
    return verified


async def build_eval_dataset(session: AsyncSession, limit: int = 8):
    """Build list SingleTurnSample cho RAGAS từ EVAL_QUERIES.

    Với mỗi query: gọi search_ingredients (vector_fallback=True — autocomplete path)
    → retrieved_contexts. Verify ground_truth → reference. Build SingleTurnSample.

    Returns:
        list[SingleTurnSample] — import ragas.dataset_schema.
    """
    from ragas.dataset_schema import SingleTurnSample

    samples: list[SingleTurnSample] = []
    stats = {"total": len(EVAL_QUERIES), "retrieved_empty": 0, "gt_verified_empty": 0}

    for query, gt_names, note in EVAL_QUERIES:
        # Retrieved contexts qua pipeline thật
        hits = await search_ingredients(session, query, limit=limit, vector_fallback=True)
        retrieved = [h.ingredient_name for h in hits]
        if not retrieved:
            stats["retrieved_empty"] += 1

        # Ground truth verify trong DB
        verified_gt = await verify_ground_truth(session, gt_names)
        if gt_names and not verified_gt:
            stats["gt_verified_empty"] += 1

        reference = "; ".join(verified_gt)
        samples.append(SingleTurnSample(
            user_input=query,
            retrieved_contexts=retrieved,
            reference=reference,
            response="; ".join(retrieved),
        ))

    print(f"Dataset: {stats['total']} queries, "
          f"{stats['retrieved_empty']} retrieved rỗng, "
          f"{stats['gt_verified_empty']} ground_truth không verify được")
    return samples


if __name__ == "__main__":
    # Quick check: in EVAL_QUERIES + count
    print(f"EVAL_QUERIES: {len(EVAL_QUERIES)} queries")
    for q, gt, note in EVAL_QUERIES:
        print(f"  {q!r:20s} gt={gt}  ({note})")
