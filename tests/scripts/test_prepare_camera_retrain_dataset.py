"""Contracts for preparing a non-destructive camera retrain experiment."""


def test_retrain_gate_rejects_incomplete_camera_manifest() -> None:
    import pytest

    from scripts.prepare_camera_retrain_dataset import require_ready_manifest

    with pytest.raises(ValueError, match="camera dataset chưa đạt gate"):
        require_ready_manifest({"ready": False, "blocking_reasons": ["camera_images_below_minimum"]})


def test_prepare_dataset_copies_baseline_and_camera_train_val(tmp_path) -> None:
    from scripts.prepare_camera_retrain_dataset import prepare_dataset

    base = tmp_path / "base"
    camera = tmp_path / "camera"
    output = tmp_path / "experiment"
    for root, split, class_name, filename in (
        (base, "train", "pho_bo", "baseline.jpg"),
        (base, "val", "pho_bo", "baseline-val.jpg"),
        (camera, "train", "pho_bo", "camera.jpg"),
        (camera, "val", "pho_bo", "camera-val.jpg"),
    ):
        target = root / split / class_name
        target.mkdir(parents=True, exist_ok=True)
        (target / filename).write_bytes(b"image")

    copied = prepare_dataset(base, camera, output)

    assert copied == 4
    assert (output / "train/pho_bo/baseline.jpg").exists()
    assert (output / "train/pho_bo/camera.jpg").exists()
    assert (output / "val/pho_bo/baseline-val.jpg").exists()
    assert (output / "val/pho_bo/camera-val.jpg").exists()
