"""Qdrant vector search cho dishes — tìm món theo ngữ nghĩa khi ILIKE miss.

Flow:
  ILIKE (exact/substring match) → miss → Qdrant vector search (semantic)
    → tìm dish_name gần nhất → lookup_dish lại bằng tên tìm được

Tích hợp với embedding server llama.cpp (port 8081), vector 1024 chiều.
"""

import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.config import settings
from backend.services.embeddings import embed_query

logger = logging.getLogger("foodai")

# ─── Constants ─────────────────────────────────────────────────────────────────

COLLECTION_NAME = "dishes"
VECTOR_SIZE = 1024  # khớp Qwen3-Embedding-0.6B (1024 chiều)
# cosine similarity ≥ threshold → coi là match. Dưới threshold → không liên quan.
SIMILARITY_THRESHOLD = 0.75

# ─── Client ────────────────────────────────────────────────────────────────────

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Lazy-init QdrantClient (singleton)."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


# ─── Collection management ─────────────────────────────────────────────────────


def _collection_exists() -> bool:
    """Kiểm tra collection 'dishes' đã tồn tại trong Qdrant chưa."""
    client = _get_client()
    collections = client.get_collections()
    return any(c.name == COLLECTION_NAME for c in collections.collections)


def init_collection(force: bool = False) -> None:
    """Tạo collection 'dishes' trong Qdrant nếu chưa có.

    Args:
        force: True → xóa collection cũ + tạo mới (dùng khi reindex).
    """
    client = _get_client()

    if _collection_exists():
        if force:
            client.delete_collection(COLLECTION_NAME)
        else:
            logger.info("Qdrant collection '%s' đã tồn tại, bỏ qua init", COLLECTION_NAME)
            return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(
            size=VECTOR_SIZE,
            distance=qmodels.Distance.COSINE,
        ),
    )
    logger.info("Đã tạo Qdrant collection '%s' (vector %dD, cosine)", COLLECTION_NAME, VECTOR_SIZE)


# ─── Indexing ──────────────────────────────────────────────────────────────────


async def index_all_dishes(dish_names: list[tuple[str, str]]) -> int:
    """Embed + upsert tất cả dish names vào Qdrant.

    Gọi từ startup hoặc script seed — KHÔNG gọi từ request handler
    (embed batch + upsert có thể mất vài giây).

    Args:
        dish_names: list of (dish_name, dish_id) — id để map ngược về DB.

    Returns:
        Số lượng points đã upsert.
    """
    if not dish_names:
        return 0

    names = [name for name, _ in dish_names]
    ids = [did for _, did in dish_names]

    # Embed từng tên — gọi tuần tự vì llama.cpp embedding server
    # không hỗ trợ batch input (hoặc có nhưng giới hạn nhỏ).
    # Dùng list comprehension + embed_query async.
    vectors = []
    for name in names:
        try:
            vec = await embed_query(name)
            vectors.append(vec)
        except Exception:
            logger.warning("Embed thất bại cho '%s', bỏ qua", name)
            vectors.append(None)

    # Build points (bỏ qua những cái embed fail)
    points = []
    for i, vec in enumerate(vectors):
        if vec is None:
            continue
        points.append(
            qmodels.PointStruct(
                id=ids[i],
                vector=vec,
                payload={"dish_name": names[i]},
            )
        )

    if not points:
        return 0

    client = _get_client()
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.info("Đã index %d dishes vào Qdrant", len(points))
    return len(points)


async def index_one_dish(dish_id: str, dish_name: str) -> bool:
    """Embed + upsert 1 dish vào Qdrant (dùng khi contribute món mới).

    Returns:
        True nếu upsert thành công, False nếu embed lỗi.
    """
    try:
        vec = await embed_query(dish_name)
    except Exception:
        logger.warning("Embed thất bại cho dish '%s', không index vào Qdrant", dish_name)
        return False

    client = _get_client()
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            qmodels.PointStruct(
                id=dish_id,
                vector=vec,
                payload={"dish_name": dish_name},
            )
        ],
    )
    return True


# ─── Search ────────────────────────────────────────────────────────────────────


async def search_dish(query: str, limit: int = 5) -> list[dict]:
    """Tìm dish trong Qdrant theo ngữ nghĩa (cosine similarity).

    Args:
        query: tên món cần tìm (từ Vision hoặc user gõ).
        limit: số kết quả tối đa.

    Returns:
        [
            {
                "dish_id": str (UUID từ DB),
                "dish_name": str,
                "score": float (0-1, cosine similarity),
            },
            ...
        ]
        Rỗng nếu: collection chưa được init, embed lỗi, hoặc không có match > threshold.
    """
    if not _collection_exists():
        logger.warning("Qdrant collection '%s' chưa tồn tại, bỏ qua vector search", COLLECTION_NAME)
        return []

    try:
        query_vec = await embed_query(query)
    except Exception:
        logger.warning("Embed thất bại cho query '%s', không dùng Qdrant", query)
        return []

    client = _get_client()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=limit,
        score_threshold=SIMILARITY_THRESHOLD,
    )

    return [
        {
            "dish_id": str(hit.id),
            "dish_name": hit.payload["dish_name"],
            "score": round(hit.score, 4),
        }
        for hit in results.points
    ]
