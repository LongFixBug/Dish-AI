"""Unit tests cho quyết định cascade từ album ảnh tham chiếu (offline)."""

import httpx
import pytest

from backend.services import recognition_cascade
from backend.services.dish_image_index import DishCandidateScore
from backend.services import dish_image_index
from backend.services.recognition_cascade import (
    LocalEvidence,
    decide_cascade,
    decide_local_fusion,
    image_candidates,
    merge_candidate_names,
)

THRESHOLD = 0.93
MARGIN = 0.04
LIMIT = 8


def _candidate(
    name: str,
    score: float,
    votes: int = 1,
    class_slug: str | None = None,
) -> DishCandidateScore:
    return DishCandidateScore(
        dish_name=name,
        best_score=score,
        votes=votes,
        class_slug=class_slug,
    )


def _evidence(
    name: str | None,
    canonical_id: str | None,
    *,
    strong: bool,
    solo_strong: bool = False,
    confidence: float = 0.0,
) -> LocalEvidence:
    return LocalEvidence(
        dish_name=name,
        canonical_id=canonical_id,
        confidence=confidence,
        strong=strong,
        solo_strong=solo_strong,
    )


# ─── decide_local_fusion ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("cv", "album", "expected_action", "expected_reason"),
    [
        (
            _evidence("Phở bò", "dish-pho", strong=True, confidence=0.91),
            _evidence("Pho bo", "dish-pho", strong=True, confidence=0.88),
            "local_consensus",
            "same_catalog_dish",
        ),
        (
            _evidence(
                "Cơm tấm",
                "dish-com-tam",
                strong=True,
                solo_strong=True,
                confidence=0.97,
            ),
            _evidence("Cơm tấm", None, strong=False, confidence=0.71),
            "vision",
            "no_strong_local_evidence",
        ),
        (
            _evidence("Phở bò", None, strong=False, confidence=0.35),
            _evidence(
                "Cao lầu",
                "dish-cao-lau",
                strong=True,
                solo_strong=True,
                confidence=0.90,
            ),
            "vision",
            "no_strong_local_evidence",
        ),
        (
            _evidence("Bún riêu", "dish-bun-rieu", strong=True, confidence=0.91),
            _evidence(
                "Bún bò Huế", "dish-bun-bo-hue", strong=True, confidence=0.89
            ),
            "vision",
            "strong_disagreement",
        ),
        (
            _evidence("Phở bò", None, strong=False, confidence=0.35),
            _evidence("Hủ tiếu", None, strong=False, confidence=0.70),
            "vision",
            "no_strong_local_evidence",
        ),
        (
            # CV qua strong gate nhưng chưa qua solo gate thì album yếu
            # không đủ để biến CV thành một quyết định local.
            _evidence("Phở bò", "dish-pho", strong=True, confidence=0.90),
            _evidence(None, None, strong=False),
            "vision",
            "no_strong_local_evidence",
        ),
    ],
)
def test_local_fusion_decision_matrix(
    cv: LocalEvidence,
    album: LocalEvidence,
    expected_action: str,
    expected_reason: str,
) -> None:
    decision = decide_local_fusion(cv, album)

    assert decision.action == expected_action
    assert decision.reason == expected_reason


def test_strong_evidence_without_catalog_identity_cannot_auto_resolve() -> None:
    cv = _evidence(
        "Món ma",
        None,
        strong=True,
        solo_strong=True,
        confidence=0.99,
    )
    album = _evidence(None, None, strong=False)

    assert decide_local_fusion(cv, album).action == "vision"


# ─── decide_cascade ──────────────────────────────────────────────────────────


def test_empty_candidates_never_resolve() -> None:
    decision = decide_cascade([], THRESHOLD, MARGIN, LIMIT)

    assert decision.resolved is False
    assert decision.dish_name is None
    assert decision.score == 0.0
    assert decision.margin == 0.0
    assert decision.candidate_names == []


def test_single_candidate_margin_is_its_own_score() -> None:
    """Một ứng viên không có đối thủ → margin = chính điểm top-1."""
    decision = decide_cascade([_candidate("Phở bò", 0.95)], THRESHOLD, MARGIN, LIMIT)

    assert decision.resolved is True
    assert decision.dish_name == "Phở bò"
    assert decision.score == 0.95
    assert decision.margin == 0.95
    assert decision.candidate_names == ["Phở bò"]


def test_score_exactly_at_threshold_resolves() -> None:
    decision = decide_cascade(
        [_candidate("Phở bò", THRESHOLD)], THRESHOLD, MARGIN, LIMIT
    )

    assert decision.resolved is True


def test_score_just_below_threshold_does_not_resolve() -> None:
    decision = decide_cascade(
        [_candidate("Phở bò", 0.9299)], THRESHOLD, MARGIN, LIMIT
    )

    assert decision.resolved is False
    # Tên và điểm top-1 vẫn được báo cáo để log/debug, chỉ cờ resolved là tắt.
    assert decision.dish_name == "Phở bò"
    assert decision.candidate_names == ["Phở bò"]


def test_margin_exactly_at_limit_resolves() -> None:
    # 0.75/0.5/0.25 biểu diễn chính xác trong float nhị phân → biên "==" thật
    # sự được kiểm tra, không bị nhiễu bởi sai số trừ hai số thập phân.
    decision = decide_cascade(
        [_candidate("Phở bò", 0.75), _candidate("Phở gà", 0.5)],
        threshold=0.7,
        margin=0.25,
        candidates_limit=LIMIT,
    )

    assert decision.resolved is True
    assert decision.margin == 0.25


def test_margin_below_limit_does_not_resolve() -> None:
    decision = decide_cascade(
        [_candidate("Phở bò", 0.95), _candidate("Phở gà", 0.92)],
        THRESHOLD,
        MARGIN,
        LIMIT,
    )

    assert decision.resolved is False
    assert decision.margin == pytest.approx(0.03)
    assert decision.candidate_names == ["Phở bò", "Phở gà"]


def test_candidate_names_are_capped_in_best_score_order() -> None:
    candidates = [
        _candidate("Phở bò", 0.97),
        _candidate("Phở gà", 0.90),
        _candidate("Bún bò Huế", 0.85),
        _candidate("Hủ tiếu", 0.80),
    ]

    decision = decide_cascade(candidates, THRESHOLD, MARGIN, candidates_limit=2)

    # Resolved hay không thì candidate_names vẫn được điền (và bị cắt tại limit).
    assert decision.resolved is True
    assert decision.candidate_names == ["Phở bò", "Phở gà"]


def test_fast_lane_allowlist_rejects_a_high_score_non_fast_lane_candidate() -> None:
    decision = decide_cascade(
        [
            _candidate("Bún mắm", 0.96, class_slug="bun_mam"),
            _candidate("Phở bò", 0.80, class_slug="pho_bo"),
        ],
        threshold=0.86,
        margin=0.07,
        candidates_limit=LIMIT,
        allowed_class_slugs={"pho_bo"},
    )

    assert decision.resolved is False
    assert decision.dish_name == "Bún mắm"
    assert decision.candidate_names == ["Bún mắm", "Phở bò"]


def test_fast_lane_allowlist_accepts_a_candidate_in_the_configured_classes() -> None:
    decision = decide_cascade(
        [_candidate("Phở bò", 0.96, class_slug="pho_bo")],
        threshold=0.86,
        margin=0.07,
        candidates_limit=LIMIT,
        allowed_class_slugs={"pho_bo"},
    )

    assert decision.resolved is True


def test_top3_blend_rewards_consistent_reference_matches() -> None:
    """Ba ảnh gần nhau đáng tin hơn một ảnh đơn lẻ tình cờ giống query."""
    one_lucky_hit = dish_image_index.aggregate_candidate_score(
        [0.96, 0.60, 0.58], mode="top3_blend"
    )
    consistent_hits = dish_image_index.aggregate_candidate_score(
        [0.93, 0.92, 0.91], mode="top3_blend"
    )

    assert consistent_hits > one_lucky_hit


def test_best_score_mode_preserves_current_album_threshold_semantics() -> None:
    assert dish_image_index.aggregate_candidate_score(
        [0.96, 0.60, 0.58], mode="best"
    ) == pytest.approx(0.96)


# ─── merge_candidate_names ───────────────────────────────────────────────────


def test_merge_puts_primary_first_and_dedupes_accent_insensitively() -> None:
    merged = merge_candidate_names(
        ["Phở bò", "Bún chả"],
        ["Pho bo", "Bánh mì thập cẩm"],
        limit=12,
    )

    assert merged == ["Phở bò", "Bún chả", "Bánh mì thập cẩm"]


def test_merge_caps_at_limit() -> None:
    merged = merge_candidate_names(
        ["Phở bò", "Bún chả"],
        ["Cơm tấm", "Bánh xèo"],
        limit=3,
    )

    assert merged == ["Phở bò", "Bún chả", "Cơm tấm"]


def test_merge_skips_blank_names() -> None:
    assert merge_candidate_names(["  ", "Phở bò"], [""], limit=5) == ["Phở bò"]


# ─── image_candidates ────────────────────────────────────────────────────────


async def test_image_candidates_disabled_short_circuits(monkeypatch) -> None:
    async def embed_must_not_run(_data: bytes) -> list[float]:
        raise AssertionError("Sidecar không được gọi khi image_embed_enabled=False")

    monkeypatch.setattr(
        recognition_cascade.settings, "image_embed_enabled", False
    )
    monkeypatch.setattr(recognition_cascade, "embed_image", embed_must_not_run)

    assert await image_candidates(b"jpeg") == []


async def test_image_candidates_swallows_sidecar_failure(monkeypatch) -> None:
    monkeypatch.setattr(recognition_cascade.settings, "image_embed_enabled", True)

    async def failing_embed(_data: bytes) -> list[float]:
        raise httpx.ConnectError("sidecar down")

    monkeypatch.setattr(recognition_cascade, "embed_image", failing_embed)

    assert await image_candidates(b"jpeg") == []


async def test_image_candidates_swallows_qdrant_failure(monkeypatch) -> None:
    monkeypatch.setattr(recognition_cascade.settings, "image_embed_enabled", True)

    async def fake_embed(_data: bytes) -> list[float]:
        return [0.1] * 768

    async def failing_search(_vector: list[float], **_kwargs) -> list:
        raise RuntimeError("collection dish_images missing")

    monkeypatch.setattr(recognition_cascade, "embed_image", fake_embed)
    monkeypatch.setattr(recognition_cascade, "top_dish_candidates", failing_search)

    assert await image_candidates(b"jpeg") == []


async def test_image_candidates_returns_album_votes(monkeypatch) -> None:
    monkeypatch.setattr(recognition_cascade.settings, "image_embed_enabled", True)
    captured: dict = {}
    expected = [_candidate("Phở bò", 0.96, votes=4)]

    async def fake_embed(data: bytes) -> list[float]:
        captured["bytes"] = data
        return [0.5, 0.5]

    async def fake_search(vector: list[float], **kwargs) -> list:
        captured["vector"] = vector
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(recognition_cascade, "embed_image", fake_embed)
    monkeypatch.setattr(recognition_cascade, "top_dish_candidates", fake_search)

    result = await image_candidates(b"jpeg")

    assert result == expected
    assert captured["bytes"] == b"jpeg"
    assert captured["vector"] == [0.5, 0.5]
    assert captured["kwargs"] == {
        "dish_limit": recognition_cascade.settings.image_candidates_limit,
    }


# ─── is_name_refinement ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("album_name", "resolved_name", "expected"),
    [
        # Mở rộng hợp lệ: giữ nguyên họ món, chỉ thêm chi tiết.
        ("Phở bò", "Phở bò chín", True),
        ("Phở gà", "Phở gà", True),
        ("Phở bò", "PHỞ BÒ TÁI", True),
        # So không phân biệt dấu.
        ("Pho bo", "Phở bò chín", True),
        # Dấu ngoặc trong tên catalog chỉ là chú thích, không phải token khác:
        # "(Huế)" phải khớp với "Huế" thay vì bị coi là mất token.
        ("Bún bò Huế", "Bún bò giò heo (Huế)", True),
        # Tên album trơ trọi một họ món là *danh mục*, không phải món ăn: vơ
        # lấy biến thể bất kỳ làm calo lệch xa (phở nước vs phở chiên phồng).
        ("Phở", "Phở chiên", False),
        ("Phở", "Phở", True),
        # Đổi họ món (thêm "bún" đứng đầu) → chặn.
        ("Nem nướng", "Bún nem nướng", False),
        # Rơi mất token ("mì", "kẹp") → chặn.
        ("Bánh mì kẹp thịt", "Bánh cuốn thịt", False),
        # Khác hẳn món → chặn.
        ("Cơm tấm", "Xôi xéo", False),
        # Chuỗi rỗng → chặn.
        ("", "Phở bò", False),
        ("Phở bò", "", False),
    ],
)
def test_is_name_refinement(album_name, resolved_name, expected) -> None:
    assert (
        recognition_cascade.is_name_refinement(album_name, resolved_name)
        is expected
    )
