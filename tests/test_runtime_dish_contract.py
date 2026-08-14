"""Runtime class and album contracts for released dish recognition."""

import json
from pathlib import Path

from ml.training import train


ROOT = Path(__file__).resolve().parents[1]


def test_ha_cao_is_in_the_approved_album_and_open_set_classifier_queue() -> None:
    classes_path = ROOT / "data/eval/efficientnet_tier_a_classes.json"
    manifest_path = ROOT / "data/eval/reference_album_tier_a_approved.json"

    classes = train.load_class_allowlist(classes_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    ood_path = ROOT / "data/eval/efficientnet_ood_classes.json"
    ood = json.loads(ood_path.read_text(encoding="utf-8"))

    assert "ha_cao" not in classes
    assert len(classes) == 29
    assert "ha_cao" in ood["classes"]
    assert any(
        path.startswith("ha_cao/") for path in manifest["approved_paths"]
    )
    assert manifest["audit"]["counts_by_class"]["ha_cao"] > 0
