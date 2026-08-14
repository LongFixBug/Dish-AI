"""Contracts for filling the isolated SigLIP food-v1 dataset."""

from pathlib import Path


def test_run_fills_only_requested_siglip_class_splits(tmp_path, make_noise_image):
    from scripts.fill_siglip_food_v1 import run

    root = tmp_path / "siglip_food_v1"
    calls: list[str] = []

    def fake_crawl(query: str, destination: Path, _limit: int) -> None:
        calls.append(query)
        destination.mkdir(parents=True, exist_ok=True)
        make_noise_image(len(calls)).save(destination / f"{len(calls)}.jpg", "JPEG")

    results = run(
        root=root,
        dishes={"chao_long": "Cháo lòng"},
        targets={"train": 1, "val": 1, "test": 1},
        crawl_limit=2,
        crawl=fake_crawl,
    )

    assert results["chao_long"].complete is True
    assert len(calls) == 3
    assert all(
        (root / split / "chao_long").is_dir()
        for split in ("train", "val", "test")
    )


def test_run_reuses_existing_test_and_does_not_crawl_it(tmp_path, make_noise_image):
    from scripts.fill_siglip_food_v1 import run

    root = tmp_path / "siglip_food_v1"
    test_image = root / "test" / "chao_long" / "held_out.jpg"
    test_image.parent.mkdir(parents=True)
    make_noise_image(100).save(test_image, "JPEG")
    calls: list[str] = []

    def fake_crawl(query: str, destination: Path, _limit: int) -> None:
        calls.append(query)
        destination.mkdir(parents=True, exist_ok=True)
        make_noise_image(len(calls)).save(destination / f"{len(calls)}.jpg", "JPEG")

    run(
        root=root,
        dishes={"chao_long": "Cháo lòng"},
        targets={"train": 1, "val": 1, "test": 1},
        crawl_limit=2,
        crawl=fake_crawl,
    )

    assert len(calls) == 2
    assert test_image.is_file()
