"""Image-retrieval cascade over the reviewed dish-photo album.

Trước khi gọi Vision, ảnh upload được embed bằng SigLIP 2 và so với album
ảnh tham chiếu trong Qdrant (collection ``dish_images``). Top-1 đủ tự tin và
tách biệt rõ khỏi top-2 thì trả lời ngay, khỏi tốn một lượt cloud Vision;
chưa đủ thì các tên ứng viên chỉ được nối thêm vào prompt của Vision.
"""

import logging
from dataclasses import dataclass

from backend.config import settings
from backend.services.dish_image_index import DishCandidateScore, top_dish_candidates
from backend.services.image_embeddings import embed_image
from backend.services.menu_vocabulary import (
    DISH_FAMILY_TOKENS,
    MENU_STOP_TOKENS,
    accent_tokens,
)

logger = logging.getLogger("foodai")


@dataclass(frozen=True)
class CascadeDecision:
    """Kết quả biểu quyết của album ảnh cho một ảnh upload.

    ``dish_name``/``score``/``margin`` mô tả top-1 (nếu có ứng viên);
    ``resolved`` mới là cờ quyết định có được dùng thẳng tên đó hay không.
    ``candidate_names`` luôn được điền để nối vào prompt Vision khi cần.
    """

    resolved: bool
    dish_name: str | None
    score: float
    margin: float
    candidate_names: list[str]


def decide_cascade(
    candidates: list[DishCandidateScore],
    threshold: float,
    margin: float,
    candidates_limit: int,
) -> CascadeDecision:
    """PURE: quyết định resolve khi top-1 vừa đủ điểm vừa tách biệt top-2.

    Một ứng viên duy nhất không có đối thủ → margin = chính điểm top-1
    (cùng ngữ nghĩa với ml/evaluation/tune_cascade.py).
    """
    if not candidates:
        return CascadeDecision(
            resolved=False,
            dish_name=None,
            score=0.0,
            margin=0.0,
            candidate_names=[],
        )

    top1 = candidates[0]
    runner_up_score = candidates[1].best_score if len(candidates) > 1 else 0.0
    actual_margin = top1.best_score - runner_up_score
    is_resolved = top1.best_score >= threshold and actual_margin >= margin
    return CascadeDecision(
        resolved=is_resolved,
        dish_name=top1.dish_name,
        score=top1.best_score,
        margin=actual_margin,
        candidate_names=[
            candidate.dish_name for candidate in candidates[:candidates_limit]
        ],
    )


def _accent_key(name: str) -> str:
    """Khóa so trùng không phân biệt dấu ("Phở bò" và "Pho bo" là một)."""
    return " ".join(accent_tokens(name))


def _refinement_tokens(name: str) -> list[str]:
    """Token mang nghĩa của tên món, giữ nguyên thứ tự để biết đâu là họ món.

    Từ đệm bị loại để "Bánh mì kẹp thịt" và "Bánh mì thịt" được coi là một —
    nếu không, chữ "kẹp" thừa ra sẽ khiến một match đúng bị đánh trượt.
    """
    return [token for token in accent_tokens(name) if token not in MENU_STOP_TOKENS]


def is_name_refinement(album_name: str, resolved_name: str) -> bool:
    """PURE: tên catalog phải là *mở rộng* của tên album, không được biến dạng.

    Điều kiện: mọi token của tên album có mặt trong tên catalog VÀ token đầu
    (họ món: phở/bún/cơm/bánh...) trùng nhau. "Phở bò" → "Phở bò chín" đạt;
    "Nem nướng" → "Bún nem nướng" (đổi họ món) và "Bánh mì kẹp thịt" →
    "Bánh cuốn thịt" (rơi mất token) đều bị chặn để rơi về Vision.

    Riêng tên trơ trọi đúng một họ món ("Phở", "Bún") là *danh mục* chứ chưa
    phải món ăn, nên bắt buộc khớp chính xác: cho nó vơ lấy biến thể bất kỳ
    thì "Phở" thành "Phở chiên", calo lệch hẳn một quãng.
    """
    album_tokens = _refinement_tokens(album_name)
    resolved_tokens = _refinement_tokens(resolved_name)
    if not album_tokens or not resolved_tokens:
        return False
    if album_tokens[0] != resolved_tokens[0]:
        return False
    if len(album_tokens) == 1 and album_tokens[0] in DISH_FAMILY_TOKENS:
        return album_tokens == resolved_tokens
    return set(album_tokens) <= set(resolved_tokens)


def merge_candidate_names(
    primary: list[str],
    secondary: list[str],
    limit: int,
) -> list[str]:
    """Ghép hai danh sách tên ứng viên, ưu tiên ``primary``, khử trùng lặp.

    Trùng lặp được so không phân biệt dấu; kết quả cắt tại ``limit``.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for name in [*primary, *secondary]:
        key = _accent_key(name)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(name)
        if len(merged) >= limit:
            break
    return merged


async def image_candidates(image_bytes: bytes) -> list[DishCandidateScore]:
    """Embed ảnh upload rồi để album ảnh tham chiếu biểu quyết tên món.

    Album chỉ là tầng tăng tốc: sidecar sập, Qdrant sập hay collection chưa
    tồn tại đều trả ``[]`` (kèm warning) để flow CV + Vision cũ chạy như thường.
    """
    if not settings.image_embed_enabled:
        return []
    try:
        vector = await embed_image(image_bytes)
        return await top_dish_candidates(
            vector,
            dish_limit=settings.image_candidates_limit,
        )
    except Exception:
        logger.warning(
            "Image cascade không khả dụng, fallback về flow CV + Vision",
            exc_info=True,
        )
        return []
