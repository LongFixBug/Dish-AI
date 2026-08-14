"""Final contracts for the small, traceable RAG V0 flow."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from backend.services import rag


def test_load_documents_uses_manifest_metadata(tmp_path: Path) -> None:
    (tmp_path / "pho-bo.txt").write_text("Phở bò có bánh phở.", encoding="utf-8")
    (tmp_path / "documents.json").write_text(
        """{
          "documents": [{
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
            "file": "pho-bo.txt"
          }]
        }""",
        encoding="utf-8",
    )

    documents = rag.load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].metadata == {
        "document_id": "pho-bo",
        "title": "Phở bò",
        "source": "foodai_demo",
        "file_path": str(tmp_path / "pho-bo.txt"),
    }


def test_load_documents_rejects_unlisted_or_empty_files(tmp_path: Path) -> None:
    (tmp_path / "pho-bo.txt").write_text("", encoding="utf-8")
    (tmp_path / "documents.json").write_text(
        """{
          "documents": [{
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
            "file": "pho-bo.txt"
          }]
        }""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="rỗng"):
        rag.load_documents(tmp_path)


def test_load_documents_rejects_missing_manifest_file(tmp_path: Path) -> None:
    (tmp_path / "documents.json").write_text(
        """{
          "documents": [{
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
            "file": "pho-bo.txt"
          }]
        }""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="không tồn tại"):
        rag.load_documents(tmp_path)


async def test_embed_text_rejects_wrong_vector_dimension(monkeypatch) -> None:
    async def fake_embed_query(_text: str) -> list[float]:
        return [0.1, 0.2]

    monkeypatch.setattr(rag, "embed_query", fake_embed_query)

    with pytest.raises(ValueError, match="1024"):
        await rag.embed_text("Phở bò")


def test_rebuild_validates_all_vectors_before_deleting_collection(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.deleted = False

        def collection_exists(self, _name: str) -> bool:
            return True

        def delete_collection(self, _name: str) -> None:
            self.deleted = True

    client = FakeClient()
    monkeypatch.setattr(rag, "get_qdrant_client", lambda: client)
    chunks = [
        Document(
            page_content="Phở bò có bánh phở.",
            metadata={
                "document_id": "pho-bo",
                "title": "Phở bò",
                "source": "foodai_demo",
                "chunk_index": 0,
            },
        )
    ]

    with pytest.raises(ValueError, match="1024"):
        rag.rebuild_rag_collection(chunks, [[0.1, 0.2]])

    assert client.deleted is False


def test_create_and_rebuild_collection_after_validating_points(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.exists = False
            self.created = 0
            self.deleted = 0
            self.upserted = 0

        def collection_exists(self, _name: str) -> bool:
            return self.exists

        def create_collection(self, **_kwargs) -> None:
            self.created += 1
            self.exists = True

        def delete_collection(self, _name: str) -> None:
            self.deleted += 1
            self.exists = False

        def upsert(self, **_kwargs) -> None:
            self.upserted += 1

    client = FakeClient()
    monkeypatch.setattr(rag, "get_qdrant_client", lambda: client)
    rag.create_rag_collection()
    rag.create_rag_collection()

    chunk = Document(
        page_content="Phở bò có bánh phở.",
        metadata={
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
            "chunk_index": 0,
        },
    )
    rag.rebuild_rag_collection([chunk], [[0.1] * rag.VECTOR_SIZE])

    assert (client.created, client.deleted, client.upserted) == (2, 1, 1)


def test_upsert_keeps_each_chunk_paired_with_its_vector(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def upsert(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(rag, "get_qdrant_client", FakeClient)
    chunks = [
        Document(
            page_content="Chunk một.",
            metadata={
                "document_id": "pho-bo",
                "title": "Phở bò",
                "source": "foodai_demo",
                "chunk_index": 0,
            },
        ),
        Document(
            page_content="Chunk hai.",
            metadata={
                "document_id": "bun-bo-hue",
                "title": "Bún bò Huế",
                "source": "foodai_demo",
                "chunk_index": 0,
            },
        ),
    ]

    rag.upsert_chunks(chunks, [[0.1] * rag.VECTOR_SIZE, [0.2] * rag.VECTOR_SIZE])

    points = captured["points"]
    assert [point.payload["document_id"] for point in points] == ["pho-bo", "bun-bo-hue"]
    assert [point.vector[0] for point in points] == [0.1, 0.2]


async def test_search_rejects_a_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="lớn hơn"):
        await rag.search_chunks("Phở bò", limit=0)


async def test_search_uses_top_k_and_discards_scores_below_threshold(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_embed_text(_text: str) -> list[float]:
        return [0.1] * rag.VECTOR_SIZE

    class FakeClient:
        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                points=[
                    SimpleNamespace(
                        score=0.82,
                        payload={
                            "document_id": "pho-bo",
                            "title": "Phở bò",
                            "source": "foodai_demo",
                            "chunk_index": 0,
                            "content": "Phở bò có bánh phở.",
                        },
                    ),
                    SimpleNamespace(
                        score=0.21,
                        payload={
                            "document_id": "other",
                            "title": "Khác",
                            "source": "foodai_demo",
                            "chunk_index": 0,
                            "content": "Không liên quan.",
                        },
                    ),
                ]
            )

    monkeypatch.setattr(rag, "embed_text", fake_embed_text)
    monkeypatch.setattr(rag, "get_qdrant_client", FakeClient)

    chunks = await rag.search_chunks("Phở bò là gì?", limit=3)

    assert captured["limit"] == 3
    assert captured["score_threshold"] == rag.MIN_RETRIEVAL_SCORE
    assert [chunk.metadata["document_id"] for chunk in chunks] == ["pho-bo"]


async def test_search_expands_document_question_and_uses_lexical_fallback(monkeypatch) -> None:
    embedded_texts: list[str] = []
    calls: list[dict[str, object]] = []

    async def fake_embed_text(text: str) -> list[float]:
        embedded_texts.append(text)
        return [0.1] * rag.VECTOR_SIZE

    class FakeClient:
        def query_points(self, **kwargs):
            calls.append(kwargs)
            if kwargs.get("score_threshold") is not None:
                return SimpleNamespace(points=[])
            return SimpleNamespace(
                points=[
                    SimpleNamespace(
                        score=0.31,
                        payload={
                            "document_id": "pho-bo",
                            "title": "Phở bò",
                            "source": "foodai_demo",
                            "chunk_index": 0,
                            "content": (
                                "Dữ liệu dinh dưỡng chính thức trong FoodAI phải lấy "
                                "từ catalog PostgreSQL."
                            ),
                        },
                    )
                ]
            )

    monkeypatch.setattr(rag, "embed_text", fake_embed_text)
    monkeypatch.setattr(rag, "get_qdrant_client", FakeClient)

    chunks = await rag.search_chunks(
        "Dữ liệu dinh dưỡng chính thức của FoodAI lấy từ đâu?",
    )

    assert "catalog PostgreSQL" in embedded_texts[0]
    assert len(calls) == 2
    assert chunks[0].metadata["retrieval"] == "lexical"
    assert chunks[0].metadata["document_id"] == "pho-bo"


async def test_no_context_returns_fixed_answer_without_calling_llm(monkeypatch) -> None:
    async def fake_search_chunks(_question: str) -> list[Document]:
        return []

    class LlmMustNotBeCalled:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("LLM must not be called when context is empty")

    monkeypatch.setattr(rag, "search_chunks", fake_search_chunks)
    monkeypatch.setattr(rag.httpx, "AsyncClient", LlmMustNotBeCalled)

    answer, sources = await rag.answer_question("Món này có chữa bệnh không?")

    assert answer == "Mình chưa tìm thấy tài liệu phù hợp để trả lời câu này."
    assert sources == []


async def test_answer_question_sends_context_to_the_llm(monkeypatch) -> None:
    retrieved = Document(
        page_content="Phở bò có bánh phở.",
        metadata={
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
            "chunk_index": 0,
            "score": 0.8,
        },
    )
    captured: dict[str, object] = {}

    async def fake_search_chunks(_question: str) -> list[Document]:
        return [retrieved]

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "Phở bò có bánh phở."}}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def post(self, _url: str, **kwargs) -> FakeResponse:
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(rag, "search_chunks", fake_search_chunks)
    monkeypatch.setattr(rag.httpx, "AsyncClient", lambda **_kwargs: FakeClient())

    answer, sources = await rag.answer_question("Phở bò có gì?")

    assert answer == "Phở bò có bánh phở."
    assert sources == [retrieved]
    assert "CONTEXT:" in captured["json"]["messages"][0]["content"]


def test_build_prompt_places_context_before_question() -> None:
    prompt = rag.build_prompt(
        "Phở bò có gì?",
        [Document(page_content="Phở bò có bánh phở.", metadata={})],
    )

    assert prompt.index("CONTEXT:") < prompt.index("QUESTION:")
    assert "[1] Phở bò có bánh phở." in prompt
