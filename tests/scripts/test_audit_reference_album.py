"""Contracts for producing an approved, reproducible reference-album manifest."""

import json
from pathlib import Path

from PIL import Image, ImageDraw


def _write_image(path: Path, color: str = "red") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 120), color=color).save(path)


def test_audit_rejects_invalid_and_cross_label_duplicate_images(tmp_path) -> None:
    from scripts.audit_reference_album import audit_reference_album

    root = tmp_path / "references"
    _write_image(root / "pho_bo" / "keep.jpg")
    _write_image(root / "bun_bo_hue" / "duplicate.jpg")
    (root / "pho_bo" / "broken.jpg").write_bytes(b"not-an-image")

    audit = audit_reference_album(root, {"pho_bo", "bun_bo_hue"})

    assert audit.total_files == 3
    assert audit.invalid_paths == ("pho_bo/broken.jpg",)
    assert audit.cross_label_duplicates == (
        ("bun_bo_hue/duplicate.jpg", "pho_bo/keep.jpg"),
    )
    assert audit.approved_paths == ("bun_bo_hue/duplicate.jpg",)


def test_manifest_contains_only_approved_relative_paths_and_integrity_hash(tmp_path) -> None:
    from scripts.audit_reference_album import (
        audit_reference_album,
        write_manifest,
    )

    root = tmp_path / "references"
    _write_image(root / "pho_bo" / "approved.jpg")
    _write_image(root / "untrusted" / "ignored.jpg", color="blue")
    audit = audit_reference_album(root, {"pho_bo"})
    manifest_path = tmp_path / "approved.json"

    write_manifest(manifest_path, root, audit, tier_name="tier_a")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["tier_name"] == "tier_a"
    assert manifest["approved_paths"] == ["pho_bo/approved.jpg"]
    assert manifest["approved_count"] == 1
    assert len(manifest["manifest_sha256"]) == 64


def test_load_allowed_classes_accepts_the_versioned_tier_a_contract(tmp_path) -> None:
    from scripts.audit_reference_album import load_allowed_classes

    classes = tmp_path / "tier_a.json"
    classes.write_text(
        json.dumps({"schema_version": 1, "classes": ["pho_bo", "banh_xeo"]}),
        encoding="utf-8",
    )

    assert load_allowed_classes(classes) == {"pho_bo", "banh_xeo"}


def test_audit_can_include_reviewed_album_only_class(tmp_path) -> None:
    from scripts.audit_reference_album import audit_reference_album

    root = tmp_path / "references"
    _write_image(root / "pho_bo" / "approved.jpg")
    image = Image.new("RGB", (120, 120), color="blue")
    ImageDraw.Draw(image).ellipse((20, 20, 100, 100), fill="yellow")
    root.joinpath("ha_cao", "album_only.jpg").parent.mkdir(parents=True)
    image.save(root / "ha_cao" / "album_only.jpg")

    audit = audit_reference_album(
        root,
        {"pho_bo"},
        extra_classes={"ha_cao"},
    )

    assert audit.counts_by_class == {"ha_cao": 1, "pho_bo": 1}
    assert "ha_cao/album_only.jpg" in audit.approved_paths
