"""Preflight contract for the one-command SigLIP food-v1 setup."""

import json


def test_prepare_training_requires_all_splits_and_sets_eight_epochs(
    tmp_path, make_noise_image
):
    from scripts.setup_siglip_food_v1 import prepare_training

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_model": "google/siglip2-base-patch16-224",
                "classes": ["bun_bo_hue", "chao_long"],
            }
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    for index, split in enumerate(("train", "val", "test")):
        for class_index, slug in enumerate(("bun_bo_hue", "chao_long")):
            path = data_dir / split / slug / "image.jpg"
            path.parent.mkdir(parents=True)
            make_noise_image(index * 10 + class_index).save(path, "JPEG")

    config, report = prepare_training(
        config_path=config_path,
        data_dir=data_dir,
        device_name="cpu",
        epochs=8,
        mps_available=False,
        cuda_available=False,
    )

    assert config.epochs == 8
    assert report["device"] == "cpu"
    assert report["counts"]["test"] == {"bun_bo_hue": 1, "chao_long": 1}


def test_initialize_dataset_workspace_creates_all_split_class_directories(tmp_path) -> None:
    from scripts.setup_siglip_food_v1 import initialize_dataset_workspace

    root = tmp_path / "siglip_food_v1"
    report = initialize_dataset_workspace(
        data_dir=root,
        classes=("banh_canh", "pho_bo"),
    )

    assert report == {"directories_created": 6, "data_dir": str(root)}
    for split in ("train", "val", "test"):
        for slug in ("banh_canh", "pho_bo"):
            assert (root / split / slug).is_dir()
    assert "Không commit ảnh" in (root / "README.md").read_text(encoding="utf-8")
