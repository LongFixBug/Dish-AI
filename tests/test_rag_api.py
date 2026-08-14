"""HTTP contracts for the simple RAG chat endpoint."""

from langchain_core.documents import Document

from backend.api import rag as rag_api


def test_rag_chat_requires_authentication(anonymous_client) -> None:
    response = anonymous_client.post(
        "/api/v1/rag/chat",
        json={"question": "Phở bò có gì?"},
    )

    assert response.status_code in {401, 403}


def test_rag_chat_returns_answer_and_sources(client, monkeypatch) -> None:
    received: dict[str, str] = {}

    async def fake_answer_question(question: str) -> tuple[str, list[Document]]:
        received["question"] = question
        return (
            "Phở bò có bánh phở và thịt bò.",
            [
                Document(
                    page_content="Phở bò có bánh phở và thịt bò.",
                    metadata={
                        "document_id": "pho-bo",
                        "title": "Phở bò",
                        "source": "foodai_demo",
                        "score": 0.7344,
                    },
                )
            ],
        )

    monkeypatch.setattr(rag_api, "answer_question", fake_answer_question)

    response = client.post(
        "/api/v1/rag/chat",
        json={"question": "  Phở   bò có gì?  "},
    )

    assert response.status_code == 200
    assert received == {"question": "Phở bò có gì?"}
    assert response.json() == {
        "answer": "Phở bò có bánh phở và thịt bò.",
        "sources": [
            {
                "document_id": "pho-bo",
                "title": "Phở bò",
                "source": "foodai_demo",
                "score": 0.7344,
            }
        ],
    }


def test_rag_chat_rejects_blank_and_too_long_questions(client) -> None:
    blank = client.post("/api/v1/rag/chat", json={"question": "   "})
    too_long = client.post("/api/v1/rag/chat", json={"question": "x" * 1001})

    assert blank.status_code == 422
    assert too_long.status_code == 422


def test_rag_chat_hides_internal_service_errors(client, monkeypatch) -> None:
    async def fake_answer_question(_question: str) -> tuple[str, list[Document]]:
        raise RuntimeError("llama.cpp connection refused")

    monkeypatch.setattr(rag_api, "answer_question", fake_answer_question)

    response = client.post(
        "/api/v1/rag/chat",
        json={"question": "Phở bò có gì?"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "RAG hiện chưa sẵn sàng. Vui lòng thử lại sau.",
    }
