import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import CurrentUser, require_user
from backend.services.rag import answer_question
from schemas.rag import RagChatRequest, RagChatResponse, RagSource


logger = logging.getLogger("foodai")

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.post("/chat", response_model=RagChatResponse)
async def chat_with_rag(
    request: RagChatRequest,
    _current_user: Annotated[CurrentUser, Depends(require_user)],
) -> RagChatResponse:
    try:
        answer, chunks = await answer_question(request.question)
    except Exception:
        logger.exception("RAG chat failed")
        raise HTTPException(
            status_code=503,
            detail="RAG hiện chưa sẵn sàng. Vui lòng thử lại sau.",
        )

    sources = [
        RagSource(
            document_id=str(chunk.metadata["document_id"]),
            title=str(chunk.metadata["title"]),
            source=str(chunk.metadata["source"]),
            score=float(chunk.metadata["score"]),
        )
        for chunk in chunks
    ]

    return RagChatResponse(
        answer=answer,
        sources=sources,
    )
