"""Evaluation harness — RAGAS RAG eval (context_precision/recall) + custom eval.

Chạy RAG eval cho pipeline search_ingredients (2-tier ILIKE + vector fallback):
    DEBUG=false python -m ml.evaluation.rag_eval

LLM-as-judge: llama.cpp local (Qwen2.5-7B, port 8080) — default.
    Qwen3.7 cloud (OpenCode) hết quota tuần → fallback local. Khi reset,
    đặt env RAGAS_LLM=cloud để dùng lại.
Report: ml/evaluation/reports/rag_eval_{timestamp}.{json,md}

Yêu cầu hạ tầng: DB postgres 5432 + embedding server 8081 (vector fallback)
    + LLM server 8080 (RAGAS judge local).
"""
