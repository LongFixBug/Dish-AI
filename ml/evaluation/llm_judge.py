"""LLM-as-judge wrapper — llama.cpp local (Qwen2.5-7B) cho RAGAS.

RAGAS metric (context_precision, context_recall) cần 1 LLM-as-judge để chấm điểm
chất lượng retrieval. Dùng llama.cpp local (Qwen2.5-7B instruct, port 8080) —
OpenAI-compatible `/v1/chat/completions`, miễn phí, chạy được luôn.

Lý do dùng local thay Qwen3.7 cloud (OpenCode): cloud hết quota tuần (429 — resets
in 3 days). Local 7B quantized chấm judge tiếng Việt yếu hơn cloud nhưng đủ test
pipeline + miễn phí + offline. Khi cloud reset quota, đặt env RAGAS_LLM=cloud.

llama-server (start bằng scripts/start_llama.sh) expose `/v1/chat/completions`
OpenAI-compatible. RAGAS 0.2 dùng `LangchainLLMWrapper(ChatOpenAI(base_url=...))`
để wrap OpenAI-compatible endpoint (llm_factory hardcode OpenAI cloud, không
chấp custom base_url → không dùng được cho local).

Yêu cầu: llama-server chạy ở port 8080 TRƯỚC khi eval (scripts/start_llama.sh).

Usage:
    from ml.evaluation.llm_judge import get_evaluator_llm, test_judge
    asyncio.run(test_judge())  # smoke test
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from openai import AsyncOpenAI  # noqa: E402

from backend.config import settings  # noqa: E402

# Singleton
_evaluator_llm = None
_client: AsyncOpenAI | None = None

# Chọn LLM judge: "local" (default, llama.cpp 8080) hoặc "cloud" (Qwen3.7 OpenCode)
JUDGE_MODE = os.getenv("RAGAS_LLM", "local")


def _get_client() -> AsyncOpenAI:
    """Build AsyncOpenAI client (cho smoke test test_judge). local → 8080, cloud → OpenCode."""
    global _client
    if _client is None:
        if JUDGE_MODE == "cloud":
            if not settings.vision_api_key:
                raise RuntimeError(
                    "RAGAS_LLM=cloud nhưng vision_api_key rỗng — kiểm tra .env."
                )
            _client = AsyncOpenAI(
                api_key=settings.vision_api_key,
                base_url=settings.vision_api_base,
            )
        else:
            # local llama.cpp — llama-server expose /v1, key bất kỳ
            _client = AsyncOpenAI(
                api_key="local",
                base_url=f"{settings.llm_url}/v1",
            )
    return _client


def _get_base_url() -> str:
    """Trả base_url OpenAI-compatible theo mode."""
    if JUDGE_MODE == "cloud":
        return settings.vision_api_base
    return f"{settings.llm_url}/v1"


def _get_api_key() -> str:
    """Trả api key theo mode (local dùng dummy)."""
    if JUDGE_MODE == "cloud":
        if not settings.vision_api_key:
            raise RuntimeError("RAGAS_LLM=cloud nhưng vision_api_key rỗng — kiểm tra .env.")
        return settings.vision_api_key
    return "local"


def _get_model() -> str:
    """Trả model name theo mode. local dùng llm_model, cloud dùng vision_model."""
    if JUDGE_MODE == "cloud":
        return settings.vision_model
    return settings.llm_model


def get_evaluator_llm():
    """Trả RAGAS evaluator LLM wrapper. Singleton.

    RAGAS 0.2: dùng LangchainLLMWrapper(ChatOpenAI) với custom base_url.
    (llm_factory chỉ chấp OpenAI cloud mặc định, không wrtch custom endpoint.)
    """
    global _evaluator_llm
    if _evaluator_llm is None:
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper

        chat = ChatOpenAI(
            model=_get_model(),
            api_key=_get_api_key(),
            base_url=_get_base_url(),
            temperature=0.0,
        )
        _evaluator_llm = LangchainLLMWrapper(langchain_llm=chat)
    return _evaluator_llm


async def test_judge() -> str:
    """Smoke test: gọi judge 1 prompt "Say OK" → verify connectivity.

    Trả text response. Raise nếu API lỗi (llama-server không chạy, endpoint sai).
    Dùng trước khi chạy full eval để bắt sớm lỗi config.
    """
    client = _get_client()
    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=10,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    import asyncio

    print(f"Judge mode: {JUDGE_MODE}")
    if JUDGE_MODE == "cloud":
        print(f"Endpoint: {settings.vision_api_base} | Model: {settings.vision_model}")
        print(f"API key set: {'yes' if settings.vision_api_key else 'NO'}")
    else:
        print(f"Endpoint: {settings.llm_url}/v1 | Model: {settings.llm_model}")
    try:
        reply = asyncio.run(test_judge())
        print(f"✅ Judge online — reply: {reply!r}")
    except Exception as e:
        print(f"❌ Judge test fail: {e}")
        if JUDGE_MODE == "local":
            print("   → Kiểm tra llama-server chạy port 8080 (scripts/start_llama.sh)")
        sys.exit(1)