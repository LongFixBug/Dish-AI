"""Authenticated SSE chatbot endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import CurrentUser, require_user
from backend.db.postgres import get_session
from backend.services import chat_service
from backend.config import settings
from schemas.chat import ChatRequest

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _event(name: str, payload: dict[str, object]) -> str:
    return (
        f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> StreamingResponse:
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chatbot hiện đang tắt.")

    async def generate():
        async for event_name, payload in chat_service.stream_chat(
            session,
            current_user.id,
            request,
        ):
            yield _event(event_name, payload)
            await asyncio.sleep(0)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
