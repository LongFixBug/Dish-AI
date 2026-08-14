"""Tests for the single-source fast-lane class configuration."""

import json

import pytest

from backend.config import Settings
from backend.services.fast_lane_config import load_fast_lane_classes


def _write_config(path, classes) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "classes": classes}),
        encoding="utf-8",
    )


def test_fast_lane_loader_returns_sorted_unique_class_slugs(tmp_path) -> None:
    config_path = tmp_path / "fast_lane.json"
    _write_config(config_path, ["pho_bo", "com_tam"])

    assert load_fast_lane_classes(config_path) == frozenset({"com_tam", "pho_bo"})


def test_fast_lane_loader_rejects_duplicate_classes(tmp_path) -> None:
    config_path = tmp_path / "fast_lane.json"
    _write_config(config_path, ["pho_bo", "pho_bo"])

    with pytest.raises(ValueError, match="duplicate"):
        load_fast_lane_classes(config_path)


def test_settings_reads_fast_lane_classes_from_json_not_from_env_list(tmp_path) -> None:
    config_path = tmp_path / "fast_lane.json"
    _write_config(config_path, ["pho_bo", "com_tam"])

    settings = Settings(
        image_fast_lane_enabled=True,
        image_fast_lane_config_path=config_path,
        _env_file=None,
    )

    assert settings.image_fast_lane_classes == frozenset({"com_tam", "pho_bo"})


def test_disabled_fast_lane_does_not_require_or_load_config(tmp_path) -> None:
    settings = Settings(
        image_fast_lane_enabled=False,
        image_fast_lane_config_path=tmp_path / "missing.json",
        _env_file=None,
    )

    assert settings.image_fast_lane_classes == frozenset()
