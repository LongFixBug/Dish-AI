"""Test offline cho scripts/download_datasets.py — chỉ phần thuần túy.

Không chạm mạng: dataset là iterator in-memory (list of dicts), ảnh là
ảnh nhiễu PIL sinh tại chỗ, Hugging Face `datasets` không bị import.
"""

import json

import imagehash
import pytest

from scripts.download_datasets import (
    build_class_slug,
    collect_split,
    find_dataset_columns,
    is_duplicate_phash,
    is_min_size,
    load_existing_state,
    merge_class_names,
)

LABEL_NAMES = ["Phở bò", "Bánh xèo"]


# ---------------------------------------------------------------- slug


def test_build_class_slug_strips_vietnamese_accents():
    assert build_class_slug("Phở bò") == "pho_bo"
    assert build_class_slug("Bánh xèo") == "banh_xeo"
    assert build_class_slug("Bún đậu mắm tôm") == "bun_dau_mam_tom"
    assert build_class_slug("Bánh Đúc") == "banh_duc"


def test_build_class_slug_handles_separators_and_case():
    assert build_class_slug("Banh-beo") == "banh_beo"
    assert build_class_slug("  Cao   lầu ") == "cao_lau"
    assert build_class_slug("Pho") == "pho"


# ------------------------------------------------- class_names.json merge


def test_merge_class_names_preserves_existing_keys(tmp_path):
    path = tmp_path / "class_names.json"
    path.write_text(
        json.dumps({"pho_bo": "Phở bò"}, ensure_ascii=False), encoding="utf-8"
    )

    merged = merge_class_names(
        path, {"pho_bo": "TÊN KHÁC PHẢI BỊ BỎ QUA", "banh_xeo": "Bánh xèo"}
    )

    assert merged == {"banh_xeo": "Bánh xèo", "pho_bo": "Phở bò"}
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == merged
    assert list(on_disk) == sorted(on_disk)  # key đã sort


def test_merge_class_names_creates_file_and_parent_dirs(tmp_path):
    path = tmp_path / "eval" / "class_names.json"

    merged = merge_class_names(path, {"xoi_xeo": "Xôi xéo"})

    assert merged == {"xoi_xeo": "Xôi xéo"}
    assert "Xôi xéo" in path.read_text(encoding="utf-8")  # giữ unicode, không escape


# ------------------------------------------------------------ phash dedup


def test_identical_image_is_duplicate(make_noise_image):
    first = imagehash.phash(make_noise_image(1))
    second = imagehash.phash(make_noise_image(1))

    assert is_duplicate_phash(second, [first]) is True


def test_different_noise_image_is_not_duplicate(make_noise_image):
    first = imagehash.phash(make_noise_image(1))
    second = imagehash.phash(make_noise_image(2))

    assert is_duplicate_phash(second, [first]) is False


def test_is_duplicate_with_empty_registry(make_noise_image):
    assert is_duplicate_phash(imagehash.phash(make_noise_image(1)), []) is False


# --------------------------------------------------------- min-size filter


def test_is_min_size_accepts_100px_and_rejects_smaller(make_noise_image):
    assert is_min_size(make_noise_image(1, size=(100, 100))) is True
    assert is_min_size(make_noise_image(1, size=(99, 500))) is False
    assert is_min_size(make_noise_image(1, size=(500, 99))) is False


# ------------------------------------------------------- feature detection


class FakeClassLabel:
    def __init__(self, names: list[str]) -> None:
        self.names = names


class FakeImageFeature:
    dtype = "PIL.Image.Image"


def test_find_dataset_columns_by_duck_typing():
    features = {
        "image": FakeImageFeature(),
        "label": FakeClassLabel(["Phở bò", "Bánh xèo"]),
    }

    image_column, label_column, label_names = find_dataset_columns(features)

    assert image_column == "image"
    assert label_column == "label"
    assert label_names == ["Phở bò", "Bánh xèo"]


def test_find_dataset_columns_raises_without_class_label():
    with pytest.raises(RuntimeError, match="features"):
        find_dataset_columns({"image": FakeImageFeature()})


# --------------------------------------------------- collect_split cap logic


def test_collect_split_caps_each_class_and_stops_early(tmp_path, make_noise_image):
    consumed: list[int] = []

    def fake_rows():
        for index in range(100):
            consumed.append(index)
            yield {"image": make_noise_image(index), "label": index % 2}

    result = collect_split(
        fake_rows(), "image", "label", LABEL_NAMES, tmp_path, per_class=2
    )

    assert result.error is None
    assert result.saved == {"banh_xeo": 2, "pho_bo": 2}
    # đủ 2 ảnh/lớp sau đúng 4 dòng → dừng ngay, không kéo thêm từ stream
    assert len(consumed) == 4
    assert (tmp_path / "pho_bo" / "pho_bo_0.jpg").is_file()
    assert (tmp_path / "banh_xeo" / "banh_xeo_1.jpg").is_file()


def test_collect_split_skips_images_below_min_size(tmp_path, make_noise_image):
    rows = [
        {"image": make_noise_image(1, size=(50, 120)), "label": 0},
        {"image": make_noise_image(2), "label": 0},
    ]

    result = collect_split(rows, "image", "label", LABEL_NAMES, tmp_path, per_class=1)

    assert result.skipped_small == 1
    assert result.saved["pho_bo"] == 1


def test_collect_split_skips_duplicate_images(tmp_path, make_noise_image):
    rows = [
        {"image": make_noise_image(7), "label": 0},
        {"image": make_noise_image(7), "label": 0},  # y hệt → trùng
        {"image": make_noise_image(8), "label": 0},
    ]

    result = collect_split(rows, "image", "label", LABEL_NAMES, tmp_path, per_class=2)

    assert result.skipped_duplicate == 1
    assert result.saved["pho_bo"] == 2


def test_collect_split_skips_images_seen_in_an_earlier_split(
    tmp_path, make_noise_image
):
    train_hash = imagehash.phash(make_noise_image(7))
    rows = [
        {"image": make_noise_image(7), "label": 0},
        {"image": make_noise_image(8), "label": 0},
    ]

    result = collect_split(
        rows,
        "image",
        "label",
        LABEL_NAMES,
        tmp_path,
        per_class=1,
        blocked_hashes={"pho_bo": [train_hash]},
    )

    assert result.skipped_duplicate == 1
    assert result.saved["pho_bo"] == 1
    assert len(list((tmp_path / "pho_bo").iterdir())) == 1


def test_collect_split_restricts_to_wanted_classes(tmp_path, make_noise_image):
    rows = [
        {"image": make_noise_image(1), "label": 1},  # banh_xeo — ngoài wanted
        {"image": make_noise_image(2), "label": 0},
    ]

    result = collect_split(
        rows, "image", "label", LABEL_NAMES, tmp_path, per_class=1,
        wanted={"pho_bo"},
    )

    assert result.saved == {"pho_bo": 1}
    assert not (tmp_path / "banh_xeo").exists()


def test_collect_split_accepts_string_labels(tmp_path, make_noise_image):
    rows = [{"image": make_noise_image(1), "label": "Phở bò"}]

    result = collect_split(rows, "image", "label", LABEL_NAMES, tmp_path, per_class=1)

    assert result.saved["pho_bo"] == 1


def test_collect_split_reports_error_with_partial_progress(
    tmp_path, make_noise_image
):
    def flaky_rows():
        yield {"image": make_noise_image(1), "label": 0}
        raise ConnectionError("đứt mạng giữa stream")

    result = collect_split(
        flaky_rows(), "image", "label", LABEL_NAMES, tmp_path, per_class=5
    )

    assert result.saved["pho_bo"] == 1
    assert result.error is not None
    assert "đứt mạng" in result.error


# --------------------------------------------------- resume từ ảnh sẵn có


def test_collect_split_counts_existing_images_toward_cap(
    tmp_path, make_noise_image
):
    class_dir = tmp_path / "pho_bo"
    class_dir.mkdir()
    make_noise_image(1).save(class_dir / "pho_bo_0.jpg", "JPEG")

    rows = [{"image": make_noise_image(2), "label": 0}]
    result = collect_split(
        rows, "image", "label", LABEL_NAMES, tmp_path, per_class=1,
        wanted={"pho_bo"},
    )

    assert result.saved == {"pho_bo": 1}  # đã đầy từ trước, không lưu thêm
    assert len(list(class_dir.iterdir())) == 1


def test_load_existing_state_counts_and_hashes(tmp_path, make_noise_image):
    class_dir = tmp_path / "pho_bo"
    class_dir.mkdir()
    make_noise_image(1).save(class_dir / "pho_bo_0.jpg", "JPEG")
    make_noise_image(2).save(class_dir / "pho_bo_1.jpg", "JPEG")

    counts, hashes = load_existing_state(tmp_path, ["pho_bo", "banh_xeo"])

    assert counts == {"pho_bo": 2, "banh_xeo": 0}
    assert len(hashes["pho_bo"]) == 2
    assert hashes["banh_xeo"] == []
