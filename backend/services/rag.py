"""RAG V0: load corpus -> split -> embed -> Qdrant -> local LLM."""

import asyncio
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.config import settings
from backend.services.embeddings import embed_query
from schemas.rag import RagCorpusManifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_DATA_DIR = PROJECT_ROOT / "data" / "rag"
RAG_MANIFEST_FILE = "documents.json"
RAG_COLLECTION_NAME = "rag_documents_v0"
VECTOR_SIZE = 1024
MIN_RETRIEVAL_SCORE = 0.60
LLM_CHAT_URL = f"{settings.llm_url.rstrip('/')}/v1/chat/completions"
_qdrant_client: QdrantClient | None = None


def split_documents(
    documents: list[Document],
    *,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Document]:
    """Chia document thành đoạn nhỏ nhưng giữ metadata của document gốc."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    chunks: list[Document] = []

    for document in documents:
        document_chunks = splitter.split_documents([document])
        for chunk_index, chunk in enumerate(document_chunks):
            chunks.append(
                Document(
                    page_content=chunk.page_content,
                    metadata={**chunk.metadata, "chunk_index": chunk_index},
                )
            )
    return chunks


def load_documents(directory: Path) -> list[Document]:
    """Chỉ load file .txt được khai báo trong documents.json."""
    root = directory.resolve()
    manifest_path = root / RAG_MANIFEST_FILE
    if not manifest_path.is_file():
        raise ValueError(f"Thiếu manifest RAG: {manifest_path}")

    try:
        manifest = RagCorpusManifest.model_validate_json(manifest_path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Manifest RAG không hợp lệ: {manifest_path}") from exc

    specs_by_file = {document.file: document for document in manifest.documents}
    loader = DirectoryLoader(
        path=str(root),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"autodetect_encoding": True},
    )
    loaded_documents = loader.load()
    documents: list[Document] = []
    found_files: set[str] = set()

    for loaded in loaded_documents:
        file_path = Path(str(loaded.metadata["source"])).resolve()
        try:
            relative_file = file_path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Tài liệu nằm ngoài thư mục RAG: {file_path}") from exc
        spec = specs_by_file.get(relative_file)
        if spec is None:
            raise ValueError(f"Tài liệu chưa khai báo trong manifest: {relative_file}")

        content = loaded.page_content.strip()
        if not content:
            raise ValueError(f"Tài liệu RAG rỗng: {relative_file}")
        found_files.add(relative_file)
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "document_id": spec.document_id,
                    "title": spec.title,
                    "source": spec.source,
                    "file_path": str(file_path),
                },
            )
        )

    missing_files = set(specs_by_file).difference(found_files)
    if missing_files:
        missing = ", ".join(sorted(missing_files))
        raise ValueError(f"Manifest khai báo file không tồn tại: {missing}")
    return documents


def load_rag_chunks() -> list[Document]:
    return split_documents(load_documents(RAG_DATA_DIR))


async def embed_text(text: str) -> list[float]:
    """Embed một đoạn text và chặn vector sai model/dimension ngay tại biên."""
    vector = await embed_query(text)
    if len(vector) != VECTOR_SIZE:
        raise ValueError(f"Vector không đúng {VECTOR_SIZE} chiều.")
    return vector


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.qdrant_url)
    return _qdrant_client


def _create_collection(client: QdrantClient) -> None:
    client.create_collection(
        collection_name=RAG_COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )


def create_rag_collection() -> None:
    """Tạo collection lần đầu; giữ nguyên nếu collection đã tồn tại."""
    client = get_qdrant_client()
    if not client.collection_exists(RAG_COLLECTION_NAME):
        _create_collection(client)


def get_chunk_id(chunk: Document) -> str:
    document_id = str(chunk.metadata["document_id"])
    chunk_index = int(chunk.metadata["chunk_index"])
    return str(uuid5(NAMESPACE_URL, f"{document_id}:{chunk_index}"))


def _build_points(chunks: list[Document], vectors: list[list[float]]) -> list[PointStruct]:
    if len(chunks) != len(vectors):
        raise ValueError("Số chunks phải bằng số vectors.")

    points: list[PointStruct] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != VECTOR_SIZE:
            raise ValueError(f"Vector không đúng {VECTOR_SIZE} chiều.")
        points.append(
            PointStruct(
                id=get_chunk_id(chunk),
                vector=vector,
                payload={
                    "document_id": str(chunk.metadata["document_id"]),
                    "title": str(chunk.metadata["title"]),
                    "source": str(chunk.metadata["source"]),
                    "chunk_index": int(chunk.metadata["chunk_index"]),
                    "content": chunk.page_content,
                },
            )
        )
    return points


def upsert_chunks(chunks: list[Document], vectors: list[list[float]]) -> None:
    """Ghi points vào collection hiện có; dùng cho thao tác bổ sung có chủ đích."""
    points = _build_points(chunks, vectors)
    get_qdrant_client().upsert(
        collection_name=RAG_COLLECTION_NAME,
        points=points,
        wait=True,
    )


def rebuild_rag_collection(chunks: list[Document], vectors: list[list[float]]) -> None:
    """Thay collection RAG sau khi toàn bộ chunk/vector đã được validate."""
    points = _build_points(chunks, vectors)
    client = get_qdrant_client()
    if client.collection_exists(RAG_COLLECTION_NAME):
        client.delete_collection(RAG_COLLECTION_NAME)
    _create_collection(client)
    client.upsert(collection_name=RAG_COLLECTION_NAME, points=points, wait=True)


async def search_chunks(query: str, limit: int = 3) -> list[Document]:
    """Trả top-k chunk đủ điểm; score thấp nghĩa là không có context tin cậy."""
    if limit < 1:
        raise ValueError("limit phải lớn hơn hoặc bằng 1.")
    query_vector = await embed_text(query)
    result = await asyncio.to_thread(
        get_qdrant_client().query_points,
        collection_name=RAG_COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        score_threshold=MIN_RETRIEVAL_SCORE,
        with_payload=True,
    )

    chunks: list[Document] = []
    for point in result.points:
        score = float(point.score)
        payload = point.payload or {}
        content = payload.get("content")
        document_id = payload.get("document_id")
        title = payload.get("title")
        source = payload.get("source")
        chunk_index = payload.get("chunk_index")
        if (
            score < MIN_RETRIEVAL_SCORE
            or not isinstance(content, str)
            or not isinstance(document_id, str)
            or not isinstance(title, str)
            or not isinstance(source, str)
            or not isinstance(chunk_index, int)
        ):
            continue
        chunks.append(
            Document(
                page_content=content,
                metadata={
                    "document_id": document_id,
                    "title": title,
                    "source": source,
                    "chunk_index": chunk_index,
                    "score": round(score, 4),
                },
            )
        )
    return chunks


def build_prompt(question: str, chunks: list[Document]) -> str:
    context = "\n\n".join(
        f"[{index}] {chunk.page_content}" for index, chunk in enumerate(chunks, start=1)
    )
    return f"""Bạn là trợ lý FoodAI.
Chỉ trả lời dựa trên CONTEXT.
Nếu CONTEXT không đủ thông tin, hãy nói rõ là chưa đủ dữ liệu.

CONTEXT:
{context}

QUESTION:
{question}
"""


async def answer_question(question: str) -> tuple[str, list[Document]]:
    chunks = await search_chunks(question)
    if not chunks:
        return "Mình chưa tìm thấy tài liệu phù hợp để trả lời câu này.", []

    prompt = build_prompt(question, chunks)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            LLM_CHAT_URL,
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "stream": False,
            },
        )
    response.raise_for_status()

    try:
        answer = response.json()["choices"][0]["message"]["content"].strip()
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("LLM trả về dữ liệu không đúng định dạng.") from exc
    if not answer:
        raise ValueError("LLM trả về câu trả lời rỗng.")
    return answer, chunks
