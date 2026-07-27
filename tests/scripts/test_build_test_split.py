"""Test offline cho scripts/build_test_split.py — không crawl, không mạng.

Kiểm tra: icrawler KHÔNG bị import ở module scope, validate ảnh Pillow,
dedup phash chống leakage với train/val/references, cap --per-class.
"""

import importlib
import sys

import imagehash

from scripts.build_test_split import (
    DISHES,
    collect_known_hashes,
    hash_directory_images,
    open_verified_image,
    save_survivors,
    select_survivors,
)

EXPECTED_CLASSES = {
    "banh_mi_kep_thit",
    "banh_xeo",
    "com_tam",
    "ha_cao",
    "nem_nuong",
    "pho_bo",
    "pho_ga",
    "xoi_xeo",
}


# ------------------------------------------------------- module boundaries


def test_importing_module_does_not_import_icrawler():
    for module_name in ("icrawler", "icrawler.builtin", "scripts.build_test_split"):
        sys.modules.pop(module_name, None)

    importlib.import_module("scripts.build_test_split")

    assert "icrawler" not in sys.modules


def test_dishes_covers_8_local_cv_classes_with_accented_keywords():
    assert set(DISHES) == EXPECTED_CLASSES
    assert DISHES["pho_bo"].startswith("phở bò")
    assert "bánh mì kẹp thịt" in DISHES["banh_mi_kep_thit"]
    assert "xôi xéo" in DISHES["xoi_xeo"]


# --------------------------------------------------------- validate Pillow


def test_open_verified_image_accepts_real_jpeg(tmp_path, make_noise_image):
    path = tmp_path / "good.jpg"
    make_noise_image(1).save(path, "JPEG")

    image = open_verified_image(path)

    assert image is not None
    assert image.size == (120, 120)


def test_open_verified_image_rejects_corrupt_file(tmp_path):
    path = tmp_path / "fake.jpg"
    path.write_bytes(b"day khong phai la anh")

    assert open_verified_image(path) is None


# --------------------------------------------------- phash theo cây thư mục


def test_hash_directory_images_walks_recursively(tmp_path, make_noise_image):
    (tmp_path / "pho_bo").mkdir()
    make_noise_image(1).save(tmp_path / "pho_bo" / "a.jpg", "JPEG")
    make_noise_image(2).save(tmp_path / "b.png", "PNG")
    (tmp_path / "notes.txt").write_text("bỏ qua file không phải ảnh")

    hashes = hash_directory_images(tmp_path)

    assert len(hashes) == 2


def test_hash_directory_images_missing_dir_returns_empty(tmp_path):
    assert hash_directory_images(tmp_path / "khong_ton_tai") == []


def test_collect_known_hashes_merges_train_val_references(
    tmp_path, make_noise_image
):
    train_dir, val_dir = tmp_path / "train", tmp_path / "val"
    (train_dir / "pho_bo").mkdir(parents=True)
    (val_dir / "pho_bo").mkdir(parents=True)
    make_noise_image(1).save(train_dir / "pho_bo" / "t.jpg", "JPEG")
    make_noise_image(2).save(val_dir / "pho_bo" / "v.jpg", "JPEG")
    reference_hashes = [imagehash.phash(make_noise_image(3))]

    known = collect_known_hashes(
        "pho_bo", reference_hashes, train_dir=train_dir, val_dir=val_dir
    )

    assert len(known) == 3


# ------------------------------------------- chọn ảnh sống sót (anti-leak)


def test_select_survivors_rejects_leakage_duplicates(tmp_path, make_noise_image):
    staging = tmp_path / "staging"
    staging.mkdir()
    make_noise_image(1).save(staging / "000001.jpg", "JPEG")  # trùng với train
    make_noise_image(2).save(staging / "000002.jpg", "JPEG")  # ảnh mới
    known_hashes = [imagehash.phash(make_noise_image(1))]

    result = select_survivors(staging, known_hashes, per_class=5)

    assert [path.name for path in result.accepted] == ["000002.jpg"]
    assert result.rejected_duplicate == 1


def test_select_survivors_rejects_duplicates_within_staging(
    tmp_path, make_noise_image
):
    staging = tmp_path / "staging"
    staging.mkdir()
    make_noise_image(1).save(staging / "000001.jpg", "JPEG")
    make_noise_image(1).save(staging / "000002.jpg", "JPEG")  # bản sao nội bộ

    result = select_survivors(staging, [], per_class=5)

    assert len(result.accepted) == 1
    assert result.rejected_duplicate == 1


def test_select_survivors_rejects_small_and_invalid(tmp_path, make_noise_image):
    staging = tmp_path / "staging"
    staging.mkdir()
    make_noise_image(1, size=(80, 200)).save(staging / "000001.jpg", "JPEG")
    (staging / "000002.jpg").write_bytes(b"hong")
    make_noise_image(2).save(staging / "000003.jpg", "JPEG")

    result = select_survivors(staging, [], per_class=5)

    assert len(result.accepted) == 1
    assert result.rejected_small == 1
    assert result.rejected_invalid == 1


def test_select_survivors_stops_at_per_class_cap(tmp_path, make_noise_image):
    staging = tmp_path / "staging"
    staging.mkdir()
    for seed in range(5):
        make_noise_image(seed).save(staging / f"00000{seed}.jpg", "JPEG")

    result = select_survivors(staging, [], per_class=2)

    # lấy 2 ảnh ĐẦU TIÊN theo thứ tự tên file
    assert [path.name for path in result.accepted] == ["000000.jpg", "000001.jpg"]


# ------------------------------------------------------------- lưu kết quả


def test_save_survivors_writes_rgb_jpeg_with_slug_names(
    tmp_path, make_noise_image
):
    staging = tmp_path / "staging"
    staging.mkdir()
    source = staging / "raw.png"
    make_noise_image(1).save(source, "PNG")
    class_dir = tmp_path / "test" / "pho_bo"

    saved = save_survivors([source], class_dir, "pho_bo")

    assert saved == 1
    target = class_dir / "pho_bo_0.jpg"
    assert target.is_file()
    reopened = open_verified_image(target)
    assert reopened is not None
    assert reopened.mode == "RGB"
