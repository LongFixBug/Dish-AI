"""Offline tests for rebuilding a leakage-free reference image album."""

import importlib
import json
import sys

import imagehash


def test_import_does_not_load_icrawler():
    for module_name in (
        "icrawler",
        "icrawler.builtin",
        "scripts.build_reference_album",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("scripts.build_reference_album")

    assert "icrawler" not in sys.modules


def test_load_target_dishes_uses_train_folders_and_canonical_names(tmp_path):
    from scripts.build_reference_album import load_target_dishes

    train_dir = tmp_path / "train"
    (train_dir / "pho_bo").mkdir(parents=True)
    (train_dir / "banh_xeo").mkdir()
    mapping = tmp_path / "class_names.json"
    mapping.write_text(
        json.dumps({"pho_bo": "Phở bò", "banh_xeo": "Bánh xèo"}),
        encoding="utf-8",
    )

    assert load_target_dishes(train_dir, mapping) == {
        "banh_xeo": "Bánh xèo",
        "pho_bo": "Phở bò",
    }


def test_collect_blocked_hashes_walks_every_split(tmp_path, make_noise_image):
    from scripts.build_reference_album import collect_blocked_hashes

    train = tmp_path / "train"
    golden = tmp_path / "golden"
    (train / "pho_bo").mkdir(parents=True)
    (golden / "banh_xeo").mkdir(parents=True)
    make_noise_image(1).save(train / "pho_bo" / "a.jpg", "JPEG")
    make_noise_image(2).save(golden / "banh_xeo" / "b.jpg", "JPEG")

    hashes = collect_blocked_hashes([train, golden])

    assert len(hashes) == 2


def test_build_queries_keeps_dish_name_and_adds_distinct_contexts():
    from scripts.build_reference_album import build_queries

    queries = build_queries("Bún bò Huế")

    assert len(queries) == len(set(queries))
    assert all("Bún bò Huế" in query for query in queries)
    assert any("nhà hàng" in query for query in queries)


def test_build_class_rejects_blocked_and_saves_only_new_images(
    tmp_path, make_noise_image
):
    from scripts.build_reference_album import build_class

    blocked_image = make_noise_image(1)
    blocked_hashes = [imagehash.phash(blocked_image)]
    output_root = tmp_path / "candidate"

    def fake_crawl(_query, destination, _limit):
        destination.mkdir(parents=True, exist_ok=True)
        blocked_image.save(destination / "blocked.jpg", "JPEG")
        make_noise_image(2).save(destination / "new.jpg", "JPEG")

    result = build_class(
        "pho_bo",
        "Phở bò",
        output_root,
        blocked_hashes,
        per_class=1,
        crawl_limit=5,
        crawl=fake_crawl,
    )

    assert result.saved == 1
    assert result.rejected_duplicate == 1
    saved = list((output_root / "pho_bo").glob("*.jpg"))
    assert len(saved) == 1
    assert imagehash.phash(make_noise_image(2)) == imagehash.phash(
        __import__("PIL").Image.open(saved[0])
    )


def test_audit_candidate_reports_missing_and_underfilled_classes(
    tmp_path, make_noise_image
):
    from scripts.build_reference_album import audit_candidate

    root = tmp_path / "candidate"
    (root / "pho_bo").mkdir(parents=True)
    make_noise_image(1).save(root / "pho_bo" / "one.jpg", "JPEG")

    audit = audit_candidate(root, ["pho_bo", "banh_xeo"], per_class=2)

    assert audit.counts == {"banh_xeo": 0, "pho_bo": 1}
    assert audit.complete is False


def test_promote_candidate_keeps_recoverable_backup(tmp_path, make_noise_image):
    from scripts.build_reference_album import promote_candidate

    target = tmp_path / "references"
    candidate = tmp_path / "references_candidate"
    backup_root = tmp_path / "reference_backups"
    (target / "old").mkdir(parents=True)
    (candidate / "pho_bo").mkdir(parents=True)
    make_noise_image(1).save(target / "old" / "old.jpg", "JPEG")
    make_noise_image(2).save(candidate / "pho_bo" / "new.jpg", "JPEG")

    backup = promote_candidate(candidate, target, backup_root, "20260729T120000Z")

    assert (target / "pho_bo" / "new.jpg").is_file()
    assert (backup / "old" / "old.jpg").is_file()
    assert not candidate.exists()
