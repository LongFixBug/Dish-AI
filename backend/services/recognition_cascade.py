"""Archived local image-retrieval cascade used only by offline experiments.

The API no longer imports or executes this module. It remains available for
historical evaluation reports and rollback work, with no production effect.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from backend.config import settings
from backend.services.catalog_aliases import is_reviewed_catalog_alias
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


@dataclass(frozen=True)
class LocalEvidence:
    """Legacy offline evidence object, kept for historical fusion reports.

    ``strong`` là gate để tham gia consensus/phản biện. ``solo_strong`` được
    giữ để tương thích dữ liệu/test cũ, nhưng không còn được dùng trong API
    runtime SigLIP2.
    """

    dish_name: str | None
    canonical_id: str | None
    confidence: float
    strong: bool
    solo_strong: bool = False


FusionAction = Literal["local_consensus", "vision"]


@dataclass(frozen=True)
class LocalFusionDecision:
    """Legacy two-source fusion result for offline evaluation only."""

    action: FusionAction
    dish_name: str | None
    canonical_id: str | None
    reason: str


def decide_local_fusion(
    cv: LocalEvidence,
    album: LocalEvidence,
) -> LocalFusionDecision:
    """PURE: chỉ local-consensus mới được phép trả kết quả trực tiếp.

    Confidence của một nguồn không được dùng làm quyền phủ quyết nguồn kia:
    nếu hai nguồn khác UUID, hoặc chỉ có một nguồn đủ mạnh, phải chuyển Vision
    kèm candidate hints.
    """
    cv_strong = bool(cv.strong and cv.dish_name and cv.canonical_id)
    album_strong = bool(album.strong and album.dish_name and album.canonical_id)

    if cv_strong and album_strong:
        if cv.canonical_id == album.canonical_id:
            return LocalFusionDecision(
                action="local_consensus",
                dish_name=album.dish_name,
                canonical_id=album.canonical_id,
                reason="same_catalog_dish",
            )
        return LocalFusionDecision(
            action="vision",
            dish_name=None,
            canonical_id=None,
            reason="strong_disagreement",
        )

    return LocalFusionDecision(
        action="vision",
        dish_name=None,
        canonical_id=None,
        reason="no_strong_local_evidence",
    )


def decide_cascade(
    candidates: list[DishCandidateScore],
    threshold: float,
    margin: float,
    candidates_limit: int,
    allowed_class_slugs: set[str] | frozenset[str] | None = None,
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
    score_gate_passed = top1.best_score >= threshold and actual_margin >= margin
    fast_lane_gate_passed = (
        not allowed_class_slugs
        or top1.class_slug is not None
        and top1.class_slug in allowed_class_slugs
    )
    is_resolved = score_gate_passed and fast_lane_gate_passed
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


def is_catalog_identity_safe(query_name: str, resolved_name: str) -> bool:
    """Accept lexical refinements plus the explicit reviewed alias allow-list."""
    return is_name_refinement(query_name, resolved_name) or is_reviewed_catalog_alias(
        query_name,
        resolved_name,
    )


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

    Sidecar/Qdrant failures return ``[]`` so the request can fall back to
    Vision without a local model crash.
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
            "Image retrieval không khả dụng, fallback về Vision",
            exc_info=True,
        )
        return []
