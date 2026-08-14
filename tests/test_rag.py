from pathlib import Path

from langchain_core.documents import Document

from backend.services.rag import load_documents, split_documents


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


def test_long_document_becomes_multiple_chunks_with_metadata() -> None:
    document = Document(
        page_content=("Phở bò có nước dùng trong, bánh phở mềm và thịt bò. " * 20),
        metadata={
            "document_id": "pho-bo",
            "title": "Phở bò",
            "source": "foodai_demo",
        },
    )

    chunks = split_documents(
        [document],
        chunk_size=80,
        chunk_overlap=20,
    )

    assert len(chunks) > 1
    assert all(chunk.page_content.strip() for chunk in chunks)
    assert all(len(chunk.page_content) <= 80 for chunk in chunks)
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.metadata["document_id"] == "pho-bo" for chunk in chunks)


def test_load_documents_reads_one_txt_file(tmp_path: Path) -> None:
    document_file = tmp_path / "pho-bo.txt"

    document_file.write_text(
        "Phở bò là món nước phổ biến của Việt Nam.",
        encoding="utf-8",
    )
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

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].page_content == "Phở bò là món nước phổ biến của Việt Nam."
    assert documents[0].metadata["document_id"] == "pho-bo"
    assert documents[0].metadata["title"] == "Phở bò"
    assert documents[0].metadata["source"] == "foodai_demo"
    assert documents[0].metadata["file_path"] == str(document_file)
