"""Contracts for the consented camera-feedback export gate."""

from types import SimpleNamespace


def _row(**overrides):
    values = {
        "id": "00000000-0000-0000-0000-000000000001",
        "submitted_by": "00000000-0000-0000-0000-000000000002",
        "recognition_event_id": "00000000-0000-0000-0000-000000000003",
        "object_key": "feedback/2026/08/user/image.jpg",
        "dish_name_slug": "pho_bo",
        "reviewed_dish_slug": "pho_bo",
        "capture_source": "camera",
        "consent_to_training": True,
        "status": "approved",
        "reviewed_at": "2026-08-06T00:00:00+00:00",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_only_reviewed_consented_camera_rows_are_exportable() -> None:
    from scripts.export_camera_feedback_dataset import is_exportable

    assert is_exportable(_row()) is True
    assert is_exportable(_row(status="pending")) is False
    assert is_exportable(_row(consent_to_training=False)) is False
    assert is_exportable(_row(capture_source="upload")) is False
    assert is_exportable(_row(reviewed_dish_slug=None)) is False
    assert is_exportable(_row(reviewed_at=None)) is False


def test_manifest_reports_total_and_per_class_camera_gates() -> None:
    from scripts.export_camera_feedback_dataset import build_dataset_manifest

    rows = [_row(id=f"id-{index}") for index in range(19)]
    rows.append(_row(id="id-19", reviewed_dish_slug="banh_can"))

    report = build_dataset_manifest(rows, minimum_total=20, minimum_per_class=20)

    assert report["camera_images"] == 20
    assert report["by_class"] == {"banh_can": 1, "pho_bo": 19}
    assert report["ready"] is False
    assert "pho_bo" in report["classes_below_minimum"]
    assert "banh_can" in report["classes_below_minimum"]
    assert report["missing_by_class"]["banh_can"] == 19
    assert report["missing_by_class"]["pho_bo"] == 1


def test_split_assignment_is_deterministic_and_has_known_buckets() -> None:
    from scripts.export_camera_feedback_dataset import split_for_submission

    first = split_for_submission("submission-123")
    assert first in {"train", "val", "test"}
    assert split_for_submission("submission-123") == first


def test_object_key_cannot_escape_storage_root(tmp_path) -> None:
    import pytest

    from scripts.export_camera_feedback_dataset import resolve_object_path

    with pytest.raises(ValueError):
        resolve_object_path(tmp_path, "../outside.jpg")
