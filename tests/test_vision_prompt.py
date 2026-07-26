"""Contracts for Vision prompting and provider-response normalization."""

import pytest

from ml.inference.vision import (
    VisionError,
    _build_food_identification_prompt,
    _extract_message_content,
    _normalize_dishes,
)


def test_provider_response_requires_message_content() -> None:
    with pytest.raises(VisionError, match="response không hợp lệ"):
        _extract_message_content({"choices": []})


def test_normalizer_ignores_non_object_items() -> None:
    normalized = _normalize_dishes(
        [None, "not-an-object", {"dish_name": "Phở bò", "gram": 500}]
    )

    assert [dish["dish_name"] for dish in normalized] == ["Phở bò"]
    assert normalized[0]["is_side"] is False


def test_prompt_groups_com_tam_at_menu_item_level() -> None:
    prompt = _build_food_identification_prompt()

    assert "TỐI ĐA 3 món" in prompt
    assert "Cơm sườn" in prompt
    assert "Trứng ốp la" in prompt
    assert "Chả bì" in prompt
    assert "BẮT BUỘC là 'Chả bì'" in prompt
    assert "không gọi là 'Cơm chả lụa trứng'" in prompt
    assert "đồ chua" in prompt
    assert "rau muống chua" in prompt
    assert "mỡ hành" in prompt
    assert "KHÔNG tách" in prompt
    assert '"confidence": số từ 0 đến 1' in prompt
    assert "chỉ trả món phụ khi confidence >= 0.80" in prompt.casefold()


def test_prompt_can_constrain_vision_to_catalog_candidates() -> None:
    prompt = _build_food_identification_prompt(
        candidate_names=["Bánh mì thập cẩm", "Bánh mì chảo"]
    )

    assert "DANH SÁCH ỨNG VIÊN TỪ CATALOG" in prompt
    assert "Bánh mì thập cẩm" in prompt
    assert "Bánh mì chảo" in prompt
    assert "CHỈ được chọn tên trong danh sách" in prompt


def test_prompt_requests_a_separate_portion_confidence() -> None:
    prompt = _build_food_identification_prompt()

    assert '"gram_confidence": số từ 0 đến 1' in prompt
    assert "không chắc khối lượng thì dùng confidence thấp" in prompt.casefold()


def test_normalizer_keeps_at_most_three_menu_items() -> None:
    raw_dishes = [
        {"dish_name": "Cơm sườn", "gram": 450},
        {"dish_name": "Trứng ốp la", "gram": 50, "is_side": True},
        {"dish_name": "Chả bì", "gram": 70, "is_side": True},
        {"dish_name": "Đồ chua", "gram": 40, "is_side": True},
        {"dish_name": "Mỡ hành", "gram": 10, "is_side": True},
    ]

    normalized = _normalize_dishes(raw_dishes)

    assert [dish["dish_name"] for dish in normalized] == [
        "Cơm sườn",
        "Trứng ốp la",
        "Chả bì",
    ]


def test_normalizer_uses_char_bi_label_for_com_suon_combo() -> None:
    normalized = _normalize_dishes(
        [
            {"dish_name": "Cơm sườn", "gram": 350},
            {"dish_name": "Trứng ốp la", "gram": 60, "is_side": True},
            {
                "dish_name": "Chả trứng hấp",
                "gram": 40,
                "is_side": True,
                "total_calories": 85,
            },
        ]
    )

    assert normalized[2]["dish_name"] == "Chả bì"
    assert normalized[2]["gram"] == 40.0
    assert normalized[2]["total_calories"] == 85.0


def test_normalizer_suppresses_uncertain_side_and_included_accompaniment() -> None:
    normalized = _normalize_dishes(
        [
            {"dish_name": "Cơm sườn", "gram": 350, "confidence": 0.91},
            {
                "dish_name": "Rong biển",
                "gram": 40,
                "is_side": True,
                "confidence": 0.62,
            },
            {
                "dish_name": "Đồ chua rau củ",
                "gram": 30,
                "is_side": True,
                "confidence": 0.95,
            },
        ]
    )

    assert [dish["dish_name"] for dish in normalized] == ["Cơm sườn"]


def test_normalizer_uses_overall_confidence_for_legacy_vision_response() -> None:
    normalized = _normalize_dishes(
        [
            {"dish_name": "Cơm sườn", "gram": 350},
            {"dish_name": "Rong biển", "gram": 40, "is_side": True},
        ],
        default_confidence=0.67,
    )

    assert [dish["dish_name"] for dish in normalized] == ["Cơm sườn"]


def test_normalizer_keeps_confident_standalone_side_dish() -> None:
    normalized = _normalize_dishes(
        [
            {"dish_name": "Cơm sườn", "gram": 350, "confidence": 0.91},
            {
                "dish_name": "Canh rau củ",
                "gram": 150,
                "is_side": True,
                "confidence": 0.86,
            },
        ]
    )

    assert [dish["dish_name"] for dish in normalized] == [
        "Cơm sườn",
        "Canh rau củ",
    ]


def test_normalizer_preserves_item_confidence_for_the_api() -> None:
    normalized = _normalize_dishes(
        [{"dish_name": "Phở bò", "gram": 500, "confidence": 0.87}]
    )

    assert normalized[0]["confidence"] == 0.87


def test_normalizer_rejects_physically_implausible_nutrition() -> None:
    normalized = _normalize_dishes(
        [
            {
                "dish_name": "Món lỗi",
                "gram": 100,
                "confidence": 0.95,
                "total_calories": 2000,
                "total_protein_g": 20,
                "total_fat_g": 10,
                "total_carbs_g": 30,
                "total_fiber_g": 2,
            }
        ]
    )

    assert normalized == []
