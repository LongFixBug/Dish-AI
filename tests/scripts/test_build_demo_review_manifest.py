"""Tests for the explicitly demo-only visual review manifest."""

from pathlib import Path

from scripts.build_demo_review_manifest import build_manifest


def test_manifest_contains_only_selected_images_and_defers_the_rest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "references_candidate"
    class_dir = root / "pho_bo"
    class_dir.mkdir(parents=True)
    for name in ("pho_bo_0.jpg", "pho_bo_1.jpg", "uncertain.jpg"):
        (class_dir / name).write_bytes(b"image")

    manifest = build_manifest(
        root,
        {"pho_bo": (0,)},
        extra_names={},
    )

    assert manifest["demo_only"] is True
    assert manifest["review_status"] == "reviewed"
    assert manifest["provenance_status"] == "unverified_demo"
    assert manifest["approved_paths"] == ["pho_bo/pho_bo_0.jpg"]
    assert manifest["reviewed_paths"] == ["pho_bo/pho_bo_0.jpg"]
    assert manifest["deferred_paths"] == [
        "pho_bo/pho_bo_1.jpg",
        "pho_bo/uncertain.jpg",
    ]
