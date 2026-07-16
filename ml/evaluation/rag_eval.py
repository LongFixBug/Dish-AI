"""RAG eval chính — chạy RAGAS context_precision/recall trên search_ingredients.

Pipeline đánh giá: với mỗi query tiếng Việt → search_ingredients (2-tier ILIKE +
vector fallback) → retrieved contexts. RAGAS LLMContextRecall +
LLMContextPrecisionWithReference chấm điểm (LLM-as-judge = llama.cpp local, Qwen2.5-7B).

Script độc lập, KHÔNG nằm trong pytest thường (gọi LLM chậm).
Chạy khi cần đánh giá pipeline. Report JSON + MD vào ml/evaluation/reports/.

Yêu cầu hạ tầng trước khi chạy:
  - DB postgres 5432 chạy (docker compose up -d postgres)
  - Embedding server 8081 chạy (llama-server --embedding) — cho vector fallback
  - .env có VISION_API_KEY (chỉ cần khi RAGAS_LLM=cloud)

Usage:
    DEBUG=false python -m ml.evaluation.rag_eval
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings  # noqa: E402
from backend.services.ingredients import search_ingredients  # noqa: E402
from ml.evaluation.dataset import EVAL_QUERIES, build_eval_dataset, verify_ground_truth  # noqa: E402
from ml.evaluation.llm_judge import JUDGE_MODE, _get_model, get_evaluator_llm  # noqa: E402

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


# ─── DB session (tái dùng pattern tests/conftest.py — engine riêng) ────────────


async def _get_session() -> AsyncSession:
    """Tạo engine + session riêng (KHÔNG dùng global async_session — event loop conflict).

    Yield session, dispose engine khi xong. Pattern từ tests/conftest.py.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = await factory().__aenter__()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


# ─── RAGAS scoring ────────────────────────────────────────────────────────────


async def _score_sample(sample, recall_metric, precision_metric) -> dict:
    """Chấm 1 sample bằng 2 metric RAGAS. Trả dict kết quả per-query."""
    recall = await recall_metric.single_turn_ascore(sample)
    precision = await precision_metric.single_turn_ascore(sample)
    return {
        "query": sample.user_input,
        "retrieved_top3": list(sample.retrieved_contexts[:3]),
        "n_retrieved": len(sample.retrieved_contexts),
        "reference": sample.reference,
        "context_recall": float(round(recall, 3)),
        "context_precision": float(round(precision, 3)),
    }


async def _run_eval(samples, evaluator_llm) -> list[dict]:
    """Chạy RAGAS cho tất cả sample. Init metric 1 lần, reuse."""
    from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall

    recall_metric = LLMContextRecall(llm=evaluator_llm)
    precision_metric = LLMContextPrecisionWithReference(llm=evaluator_llm)

    results: list[dict] = []
    total = len(samples)
    for i, sample in enumerate(samples, 1):
        print(f"  [{i}/{total}] {sample.user_input!r} ...", end=" ", flush=True)
        try:
            row = await _score_sample(sample, recall_metric, precision_metric)
            print(f"recall={row['context_recall']}, precision={row['context_precision']}")
        except Exception as e:
            print(f"❌ lỗi: {e}")
            row = {
                "query": sample.user_input,
                "retrieved_top3": list(sample.retrieved_contexts[:3]),
                "n_retrieved": len(sample.retrieved_contexts),
                "reference": sample.reference,
                "context_recall": None,
                "context_precision": None,
                "error": str(e),
            }
        results.append(row)
    return results


# ─── Report ──────────────────────────────────────────────────────────────────


def _aggregate(results: list[dict]) -> dict:
    """Tính mean recall/precision (bỏ qua None + NaN — local judge thỉnh thoảng
    trả JSON hỏng → NaN, không phải lỗi pipeline)."""
    import math

    def _valid(values: list) -> list[float]:
        clean = []
        for v in values:
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if math.isnan(fv) or math.isinf(fv):
                continue
            clean.append(fv)
        return clean

    recalls = _valid([r.get("context_recall") for r in results])
    precisions = _valid([r.get("context_precision") for r in results])
    nan_count = sum(
        1 for r in results
        if r.get("context_recall") is not None
        and isinstance(r.get("context_recall"), float)
        and math.isnan(r.get("context_recall"))
    )

    def _mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 3) if xs else 0.0

    return {
        "n_queries": len(results),
        "n_scored": len(recalls),
        "n_nan_skipped": nan_count,
        "mean_recall": _mean(recalls),
        "mean_precision": _mean(precisions),
    }


def _build_report(results: list[dict], aggregate: dict, timestamp: str) -> dict:
    """Build report dict (JSON-serializable)."""
    return {
        "timestamp": timestamp,
        "pipeline": "search_ingredients (ILIKE + vector fallback)",
        "llm_judge": f"{JUDGE_MODE}:{_get_model()}",
        "aggregate": aggregate,
        "per_query": results,
    }


def _save_report(report: dict, timestamp: str) -> tuple[Path, Path]:
    """Lưu report JSON + MD vào reports/. Trả (json_path, md_path)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"rag_eval_{timestamp}.json"
    md_path = REPORTS_DIR / f"rag_eval_{timestamp}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_md(report), encoding="utf-8")
    return json_path, md_path


def _render_md(report: dict) -> str:
    """Render report markdown — bảng per-query + aggregate."""
    agg = report["aggregate"]
    lines = [
        f"# RAG Eval Report — {report['timestamp']}",
        "",
        f"**Pipeline**: {report['pipeline']}",
        f"**LLM judge**: {report['llm_judge']}",
        "",
        "## Aggregate",
        "",
        f"- Queries: {agg['n_queries']}",
        f"- Scored: {agg['n_scored']}",
        f"- **Mean context recall**: {agg['mean_recall']}",
        f"- **Mean context precision**: {agg['mean_precision']}",
        "",
        "## Per-query",
        "",
        "| Query | n_retrieved | Recall | Precision | Reference |",
        "|-------|-------------|--------|-----------|-----------|",
    ]
    for r in report["per_query"]:
        rec = r.get("context_recall")
        prec = r.get("context_precision")
        rec_s = f"{rec}" if rec is not None else "—"
        prec_s = f"{prec}" if prec is not None else f"ERR"
        ref = (r.get("reference") or "")[:40].replace("|", "\\|")
        lines.append(f"| {r['query']} | {r['n_retrieved']} | {rec_s} | {prec_s} | {ref} |")
    return "\n".join(lines) + "\n"


def _print_summary(report: dict) -> None:
    """In tóm tắt console."""
    agg = report["aggregate"]
    print("\n" + "=" * 60)
    print(f"📊 RAG EVAL SUMMARY ({report['timestamp']})")
    print("=" * 60)
    print(f"  Queries: {agg['n_queries']} (scored: {agg['n_scored']})")
    print(f"  Mean context recall:    {agg['mean_recall']}")
    print(f"  Mean context precision: {agg['mean_precision']}")
    print("=" * 60)


# ─── Main ────────────────────────────────────────────────────────────────────


async def main() -> None:
    """Pipeline: DB session → build dataset → RAGAS eval → report."""
    # Timestamp truyền vào (Date.now không dùng được — nhận từ args hoặc fixed)
    timestamp = sys.argv[1] if len(sys.argv) > 1 else "manual"

    print("🔍 RAG eval — search_ingredients (ILIKE + vector fallback)")
    print(f"   LLM judge: {JUDGE_MODE} ({_get_model()})\n")

    # 1. DB session
    session_gen = _get_session()
    session = await session_gen.__anext__()

    try:
        # 2. Build dataset
        print("📝 Build eval dataset...")
        samples = await build_eval_dataset(session, limit=8)
        print(f"   → {len(samples)} samples\n")

        # 3. LLM judge
        print(f"🤖 Init RAGAS evaluator LLM ({JUDGE_MODE})...")
        evaluator_llm = get_evaluator_llm()
        print("   → ready\n")

        # 4. Run eval
        print("⚖️  Chấm điểm RAGAS (context_recall + context_precision)...")
        results = await _run_eval(samples, evaluator_llm)
    finally:
        await session_gen.aclose()

    # 5. Report
    aggregate = _aggregate(results)
    report = _build_report(results, aggregate, timestamp)
    _print_summary(report)

    json_path, md_path = _save_report(report, timestamp)
    print(f"\n💾 Report saved:")
    print(f"   JSON: {json_path}")
    print(f"   MD:   {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
