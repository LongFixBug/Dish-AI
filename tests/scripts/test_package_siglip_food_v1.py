import hashlib
import json
import tarfile


def test_read_expected_classes_matches_training_canonical_order(tmp_path) -> None:
    from scripts.package_siglip_food_v1 import _read_expected_classes

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"classes": ["hu_tieu", "banh_canh", "pho_bo"]}),
        encoding="utf-8",
    )

    assert _read_expected_classes(config) == ("banh_canh", "hu_tieu", "pho_bo")


def test_package_artifact_contains_only_inference_files_and_checksum(tmp_path) -> None:
    from scripts.package_siglip_food_v1 import package_artifact

    checkpoint_dir = tmp_path / "checkpoints" / "siglip_food_v1"
    encoder = checkpoint_dir / "encoder"
    encoder.mkdir(parents=True)
    (encoder / "config.json").write_text("{}", encoding="utf-8")
    (encoder / "model.safetensors").write_bytes(b"encoder weights")
    (checkpoint_dir / "classifier_head.pt").write_bytes(b"classifier weights")
    (checkpoint_dir / "manifest.json").write_text(
        json.dumps({"classes": ["banh_canh", "pho_bo"], "test_evaluated": True}),
        encoding="utf-8",
    )
    destination = tmp_path / "siglip_food_v1.tar.gz"

    report = package_artifact(
        checkpoint_dir=checkpoint_dir,
        destination=destination,
        expected_classes=("banh_canh", "pho_bo"),
    )

    assert report.path == destination
    assert report.sha256 == hashlib.file_digest(destination.open("rb"), "sha256").hexdigest()
    with tarfile.open(destination, "r:gz") as archive:
        assert sorted(archive.getnames()) == [
            "classifier_head.pt",
            "encoder/config.json",
            "encoder/model.safetensors",
            "manifest.json",
        ]
