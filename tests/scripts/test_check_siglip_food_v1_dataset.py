"""Contracts for the local SigLIP food-v1 dataset inventory."""


def test_inventory_reports_valid_invalid_and_missing_images(tmp_path, make_noise_image) -> None:
    from scripts.check_siglip_food_v1_dataset import inventory_dataset

    root = tmp_path / "siglip_food_v1"
    for split in ("train", "val", "test"):
        for slug in ("banh_canh", "pho_bo"):
            folder = root / split / slug
            folder.mkdir(parents=True)
            make_noise_image(len(split) + len(slug)).save(folder / "valid.jpg", "JPEG")
    (root / "train" / "banh_canh" / "broken.jpg").write_text("not an image")

    report = inventory_dataset(
        data_dir=root,
        classes=("banh_canh", "pho_bo"),
        targets={"train": 2, "val": 1, "test": 1},
    )

    assert report["minimum_ready"] is False
    assert report["target_ready"] is False
    assert report["splits"]["train"]["banh_canh"] == {
        "valid": 1,
        "missing": 1,
        "invalid": ["broken.jpg"],
    }
