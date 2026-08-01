"""TDD contracts for recoverably quarantining cross-split image duplicates.

User journey: a dataset maintainer previews pHash cross-split leakage, reviews a
manifest, and can later quarantine only the losing copies without deleting or
overwriting anything.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _save(image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG")


def test_dry_run_writes_complete_manifest_without_moving_images(
    tmp_path, make_noise_image
):
    from scripts.quarantine_cross_split_duplicates import run

    image_root = tmp_path / "images"
    train_path = image_root / "train" / "pho_bo" / "train-copy.jpg"
    val_path = image_root / "val" / "pho_bo" / "val-copy.jpg"
    _save(make_noise_image(1), train_path)
    _save(make_noise_image(1), val_path)

    result = run(
        image_root=image_root,
        report_dir=tmp_path / "reports",
        backup_root=tmp_path / "backup",
        timestamp="20260730T010203Z",
    )

    manifest = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert result.applied_count == 0
    assert result.expected_move_count == 1
    assert train_path.is_file()
    assert val_path.is_file()
    assert result.markdown_path.is_file()
    assert manifest["mode"] == "dry_run"
    assert manifest["expected_move_count"] == 1
    assert manifest["matches"][0]["distance"] == 0
    assert manifest["decisions"][0]["keep_path"].endswith("val-copy.jpg")
    assert manifest["decisions"][0]["quarantine_path"].endswith("train-copy.jpg")
    assert manifest["decisions"][0]["label_conflict"] is False


def test_apply_moves_only_lower_priority_copy_to_timestamped_backup_and_reaudits(
    tmp_path, make_noise_image
):
    from scripts.quarantine_cross_split_duplicates import run

    image_root = tmp_path / "images"
    train_path = image_root / "train" / "pho_bo" / "train-copy.jpg"
    test_path = image_root / "test" / "pho_bo" / "test-copy.jpg"
    _save(make_noise_image(2), train_path)
    _save(make_noise_image(2), test_path)
    original_bytes = train_path.read_bytes()

    result = run(
        image_root=image_root,
        report_dir=tmp_path / "reports",
        backup_root=tmp_path / "backup",
        timestamp="20260730T020304Z",
        apply=True,
        targets={"train": 1, "val": 0, "test": 1},
    )

    backup_path = (
        tmp_path
        / "backup"
        / "20260730T020304Z"
        / "data"
        / "images"
        / "train"
        / "pho_bo"
        / "train-copy.jpg"
    )
    manifest = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert result.applied_count == 1
    assert test_path.is_file()
    assert not train_path.exists()
    assert backup_path.read_bytes() == original_bytes
    assert manifest["post_apply_cross_split_match_count"] == 0
    assert manifest["target_shortfalls"] == {"train": {"pho_bo": 1}}


def test_priority_keeps_test_and_quarantines_all_lower_priority_copies(
    tmp_path, make_noise_image
):
    from scripts.quarantine_cross_split_duplicates import run

    image_root = tmp_path / "images"
    train_path = image_root / "train" / "pho_bo" / "a-train.jpg"
    val_path = image_root / "val" / "pho_bo" / "b-val.jpg"
    test_path = image_root / "test" / "pho_bo" / "c-test.jpg"
    for path in (train_path, val_path, test_path):
        _save(make_noise_image(3), path)

    result = run(
        image_root=image_root,
        report_dir=tmp_path / "reports",
        backup_root=tmp_path / "backup",
        timestamp="20260730T030405Z",
        apply=True,
    )

    assert result.applied_count == 2
    assert not train_path.exists()
    assert not val_path.exists()
    assert test_path.is_file()
    assert result.post_apply_cross_split_match_count == 0


def test_same_priority_keeps_lexicographically_first_path(make_noise_image, tmp_path):
    from scripts.quarantine_cross_split_duplicates import (
        ImageRecord,
        Match,
        decide_match,
    )

    alpha = tmp_path / "train" / "pho_bo" / "alpha.jpg"
    zulu = tmp_path / "val" / "pho_bo" / "zulu.jpg"
    _save(make_noise_image(4), alpha)
    _save(make_noise_image(4), zulu)
    match = Match(
        left=ImageRecord(alpha, "train", "pho_bo", 0),
        right=ImageRecord(zulu, "val", "pho_bo", 0),
        distance=0,
    )

    decision = decide_match(match, {"train": 1, "val": 1, "test": 2})

    assert decision.keep_path == alpha
    assert decision.quarantine_path == zulu


def test_cross_label_match_is_flagged_but_still_uses_priority(
    tmp_path, make_noise_image
):
    from scripts.quarantine_cross_split_duplicates import run

    image_root = tmp_path / "images"
    train_path = image_root / "train" / "pho_bo" / "photo.jpg"
    val_path = image_root / "val" / "bun_rieu" / "photo.jpg"
    _save(make_noise_image(5), train_path)
    _save(make_noise_image(5), val_path)

    result = run(
        image_root=image_root,
        report_dir=tmp_path / "reports",
        backup_root=tmp_path / "backup",
        timestamp="20260730T040506Z",
    )

    manifest = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert manifest["decisions"][0]["label_conflict"] is True
    assert manifest["decisions"][0]["quarantine_path"].endswith("train/pho_bo/photo.jpg")
    assert train_path.is_file()
    assert val_path.is_file()


def test_apply_refuses_existing_backup_target_without_touching_source(
    tmp_path, make_noise_image
):
    from scripts.quarantine_cross_split_duplicates import run

    image_root = tmp_path / "images"
    train_path = image_root / "train" / "pho_bo" / "copy.jpg"
    test_path = image_root / "test" / "pho_bo" / "copy.jpg"
    _save(make_noise_image(6), train_path)
    _save(make_noise_image(6), test_path)
    backup_path = (
        tmp_path
        / "backup"
        / "20260730T050607Z"
        / "data"
        / "images"
        / "train"
        / "pho_bo"
        / "copy.jpg"
    )
    _save(make_noise_image(7), backup_path)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run(
            image_root=image_root,
            report_dir=tmp_path / "reports",
            backup_root=tmp_path / "backup",
            timestamp="20260730T050607Z",
            apply=True,
        )

    assert train_path.is_file()
    assert test_path.is_file()


def test_cli_accepts_a_configurable_phash_threshold():
    from scripts.quarantine_cross_split_duplicates import parse_args

    args = parse_args(["--threshold", "3"])

    assert args.threshold == 3


def test_hash_matcher_rejects_thresholds_above_its_proven_safe_limit():
    from scripts.quarantine_cross_split_duplicates import find_cross_split_matches

    with pytest.raises(ValueError, match="between 0 and 6"):
        find_cross_split_matches([], threshold=7)


def test_direct_script_invocation_resolves_project_imports(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/quarantine_cross_split_duplicates.py",
            "--image-root",
            str(tmp_path / "images"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--backup-root",
            str(tmp_path / "backup"),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
