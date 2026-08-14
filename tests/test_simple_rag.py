from langchain_core.documents import Document

from backend.services.rag import split_documents


def test_short_document_becomes_one_chunk_and_keeps_metadata() -> None:
    document = Document(
        page_content="Phở bò là món nước phổ biến của Việt Nam.",
        metadata={
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
        },
    )

    chunks = split_documents([document])

    assert len(chunks) == 1
    assert chunks[0].page_content == document.page_content
    assert chunks[0].metadata["document_id"] == "pho-bo"
    assert chunks[0].metadata["title"] == "Phở bò"
    assert chunks[0].metadata["source"] == "foodai_demo"
    assert chunks[0].metadata["chunk_index"] == 0
