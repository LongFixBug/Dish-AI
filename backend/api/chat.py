"""Chat endpoints with SSE streaming."""
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/echo-stream")
async def echo_stream():
    async def generate():
        message = "Xin chào bạn nhé"
        for word in message.split():
            yield f"data: {word}\n\n"
            await asyncio.sleep(0.3)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
