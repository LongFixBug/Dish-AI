"""Offline contracts for adding clean EfficientNet classes from crawled images."""

import importlib
import json
import sys

from PIL import Image


def test_import_does_not_load_icrawler():
    for module_name in (
        "icrawler",
        "icrawler.builtin",
        "scripts.build_new_dish_classes",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("scripts.build_new_dish_classes")

    assert "icrawler" not in sys.modules


def test_new_dishes_keep_requested_names_as_canonical_classes():
    from scripts.build_new_dish_classes import NEW_DISHES

    assert NEW_DISHES["banh_canh"] == "Bánh canh"
    assert NEW_DISHES["hu_tieu"] == "Hủ tiếu"
    assert NEW_DISHES["bun_bo_hue"] == "Bún bò Huế"
    assert NEW_DISHES["chao_long"] == "Cháo lòng"
    assert NEW_DISHES["xien_que_chien"] == "Xiên que chiên"
    assert NEW_DISHES["rau_muong_xao_toi"] == "Rau muống xào tỏi"
    assert NEW_DISHES["khoai_lang_nuong"] == "Khoai lang nướng"
    assert NEW_DISHES["tra_sua_tran_chau"] == "Trà sữa trân châu"
    assert NEW_DISHES["uc_ga_ap_chao"] == "Ức gà áp chảo"


def test_class_queries_include_local_and_food_contexts_without_duplicates():
    from scripts.build_new_dish_classes import class_queries

    queries = class_queries("Bánh tráng trộn")

    assert len(queries) == len(set(queries))
    assert all("Bánh tráng trộn" in query for query in queries)
    assert any("Sài Gòn" in query for query in queries)
    assert any("đường phố" in query for query in queries)


def test_class_queries_adds_an_unambiguous_bubble_tea_alias():
    from scripts.build_new_dish_classes import class_queries

    queries = class_queries("Trà sữa trân châu")

    assert any("bubble tea" in query.casefold() for query in queries)


def test_fast_selection_rejects_a_near_duplicate(tmp_path, make_noise_image):
    import imagehash

    from scripts.build_new_dish_classes import select_survivors_fast

    staging = tmp_path / "staging"
    staging.mkdir()
    make_noise_image(1).save(staging / "duplicate.jpg", "JPEG")
    make_noise_image(2).save(staging / "new.jpg", "JPEG")

    selection = select_survivors_fast(
        staging, [imagehash.phash(make_noise_image(1))], limit=2
    )

    assert [path.name for path in selection.accepted] == ["new.jpg"]
    assert selection.rejected_duplicate == 1


def test_build_class_fills_each_split_with_distinct_images(tmp_path, make_noise_image):
    from scripts.build_new_dish_classes import SPLIT_TARGETS, build_class

    output_root = tmp_path / "candidate"
    seen_seeds: list[int] = []

    def fake_crawl(_query, destination, _limit):
        destination.mkdir(parents=True, exist_ok=True)
        seed = len(seen_seeds) + 1
        seen_seeds.append(seed)
        make_noise_image(seed).save(destination / f"{seed}.jpg", "JPEG")

    result = build_class(
        "tra_sua_tran_chau",
        "Trà sữa trân châu",
        output_root,
        [],
        split_targets={"train": 1, "val": 1, "test": 1, "references": 1},
        crawl_limit=2,
        crawl=fake_crawl,
    )

    assert result.complete is True
    assert result.counts == {split: 1 for split in SPLIT_TARGETS}
    hashes = []
    for split in SPLIT_TARGETS:
        image_path = next((output_root / split / "tra_sua_tran_chau").glob("*.jpg"))
        with Image.open(image_path) as image:
            hashes.append(image.tobytes())
    assert len(set(hashes)) == 4


def test_apply_class_refuses_incomplete_candidate(tmp_path, make_noise_image):
    from scripts.build_new_dish_classes import apply_class

    candidate = tmp_path / "candidate"
    (candidate / "train" / "bo_ne").mkdir(parents=True)
    make_noise_image(1).save(candidate / "train" / "bo_ne" / "0.jpg", "JPEG")

    try:
        apply_class(
            "bo_ne",
            candidate,
            tmp_path / "images",
            {"train": 1, "val": 1},
        )
    except ValueError as exc:
        assert "chưa đủ" in str(exc)
    else:
        raise AssertionError("must not apply an incomplete class")


def test_apply_class_moves_complete_splits_without_overwriting(tmp_path, make_noise_image):
    from scripts.build_new_dish_classes import apply_class

    candidate = tmp_path / "candidate"
    images = tmp_path / "images"
    targets = {"train": 1, "val": 1}
    for index, split in enumerate(targets):
        path = candidate / split / "bo_ne" / "0.jpg"
        path.parent.mkdir(parents=True)
        make_noise_image(index).save(path, "JPEG")

    apply_class("bo_ne", candidate, images, targets)

    assert (images / "train" / "bo_ne" / "0.jpg").is_file()
    assert (images / "val" / "bo_ne" / "0.jpg").is_file()
    assert not (candidate / "train" / "bo_ne").exists()


def test_is_class_applied_requires_every_split_to_reach_target(
    tmp_path, make_noise_image
):
    from scripts.build_new_dish_classes import is_class_applied

    targets = {"train": 1, "val": 1}
    for index, split in enumerate(targets):
        path = tmp_path / split / "bo_ne" / "0.jpg"
        path.parent.mkdir(parents=True)
        make_noise_image(index).save(path, "JPEG")

    assert is_class_applied("bo_ne", tmp_path, targets) is True
    assert is_class_applied("pha_lau", tmp_path, targets) is False


def test_merge_class_names_adds_only_applied_classes(tmp_path):
    from scripts.build_new_dish_classes import merge_class_names

    path = tmp_path / "class_names.json"
    path.write_text(json.dumps({"pho_bo": "Phở bò"}), encoding="utf-8")

    merge_class_names(path, {"bo_ne": "Bò né", "pho_bo": "Không đổi"})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "bo_ne": "Bò né",
        "pho_bo": "Phở bò",
    }


def test_applied_dishes_includes_complete_classes_that_were_skipped_on_resume(
    tmp_path, make_noise_image
):
    from scripts.build_new_dish_classes import applied_dishes

    targets = {"train": 1, "val": 1}
    for index, split in enumerate(targets):
        path = tmp_path / split / "pha_lau" / "0.jpg"
        path.parent.mkdir(parents=True)
        make_noise_image(index).save(path, "JPEG")

    assert applied_dishes(
        {"pha_lau": "Phá lấu", "bo_ne": "Bò né"}, tmp_path, targets
    ) == {"pha_lau": "Phá lấu"}
