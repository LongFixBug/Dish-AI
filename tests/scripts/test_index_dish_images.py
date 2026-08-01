"""Contracts for the dish image indexing CLI."""

import logging
import json
import uuid
from pathlib import Path

import pytest
from PIL import Image

from scripts import index_dish_images

VECTOR = [0.0] * 768


def _write_image(path: Path, color: str = "red") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color=color).save(path)


def _expected_record_id(path: Path) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())))


@pytest.fixture
def pipeline(monkeypatch):
    """Capture embed/upsert/init calls without touching HTTP or Qdrant."""
    calls = {
        "embed_batches": [],
        "entries": [],
        "vectors": [],
        "init_force": [],
    }

    async def fake_embed_images(batch):
        calls["embed_batches"].append(list(batch))
        return [list(VECTOR) for _ in batch]

    async def fake_upsert(entries, vectors):
        calls["entries"].extend(entries)
        calls["vectors"].extend(vectors)
        return len(entries)

    def fake_init(force=False):
        calls["init_force"].append(force)

    monkeypatch.setattr(
        index_dish_images, "_resolve_embedder", lambda: fake_embed_images,
    )
    monkeypatch.setattr(
        index_dish_images, "upsert_dish_image_vectors", fake_upsert,
    )
    monkeypatch.setattr(
        index_dish_images, "init_dish_images_collection", fake_init,
    )
    return calls


async def test_cap_keeps_first_sorted_files_per_class(tmp_path, pipeline, capsys):
    root = tmp_path / "train"
    for name in ("1.jpg", "2.jpg", "3.jpg", "4.jpg"):
        _write_image(root / "pho_bo" / name)

    totals = await index_dish_images.run([root], cap=2)

    assert totals == {"pho_bo": 2}
    assert [entry.record_id for entry in pipeline["entries"]] == [
        _expected_record_id(root / "pho_bo" / "1.jpg"),
        _expected_record_id(root / "pho_bo" / "2.jpg"),
    ]
    output = capsys.readouterr().out
    assert "pho_bo: 2 images indexed" in output
    assert "Total: 2 images indexed" in output


async def test_display_names_map_from_class_names_with_slug_fallback(
    tmp_path, pipeline, caplog,
):
    root = tmp_path / "train"
    _write_image(root / "pho_bo" / "a.jpg")
    _write_image(root / "mon_la_xyz" / "b.jpg")

    with caplog.at_level(logging.WARNING, logger="index_dish_images"):
        await index_dish_images.run([root], source="feedback")

    by_slug = {entry.class_slug: entry for entry in pipeline["entries"]}
    assert by_slug["pho_bo"].dish_name == "Phở bò"
    assert by_slug["mon_la_xyz"].dish_name == "Mon la xyz"
    assert all(entry.source == "feedback" for entry in pipeline["entries"])
    assert "mon_la_xyz" in caplog.text


async def test_corrupt_file_is_skipped_with_warning(tmp_path, pipeline, caplog):
    root = tmp_path / "train"
    bad = root / "pho_bo" / "aa_bad.jpg"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"not an image at all")
    _write_image(root / "pho_bo" / "zz_good.jpg")

    with caplog.at_level(logging.WARNING, logger="index_dish_images"):
        totals = await index_dish_images.run([root])

    assert totals == {"pho_bo": 1}
    assert [entry.record_id for entry in pipeline["entries"]] == [
        _expected_record_id(root / "pho_bo" / "zz_good.jpg"),
    ]
    assert "aa_bad.jpg" in caplog.text


async def test_embeds_in_batches_of_sixteen(tmp_path, pipeline):
    root = tmp_path / "train"
    for index in range(18):
        _write_image(root / "com_tam" / f"{index:03d}.jpg")

    totals = await index_dish_images.run([root])

    assert totals == {"com_tam": 18}
    assert [len(batch) for batch in pipeline["embed_batches"]] == [16, 2]
    assert len(pipeline["vectors"]) == 18


async def test_force_flag_recreates_collection(tmp_path, pipeline):
    root = tmp_path / "train"
    _write_image(root / "pho_bo" / "a.jpg")

    await index_dish_images.run([root], force=True)
    await index_dish_images.run([root])

    assert pipeline["init_force"] == [True, False]


async def test_manifest_indexes_only_explicitly_approved_relative_paths(
    tmp_path, pipeline,
):
    root = tmp_path / "references"
    _write_image(root / "pho_bo" / "approved.jpg")
    _write_image(root / "pho_bo" / "not-approved.jpg", color="blue")
    manifest = tmp_path / "approved.json"
    manifest.write_text(
        json.dumps({"approved_paths": ["pho_bo/approved.jpg"]}),
        encoding="utf-8",
    )

    totals = await index_dish_images.run([root], manifest_path=manifest)

    assert totals == {"pho_bo": 1}
    assert pipeline["entries"][0].record_id == _expected_record_id(
        root / "pho_bo" / "approved.jpg"
    )


def test_manifest_rejects_path_outside_album_root(tmp_path):
    root = tmp_path / "references"
    _write_image(root / "pho_bo" / "approved.jpg")
    manifest = tmp_path / "unsafe.json"
    manifest.write_text(
        json.dumps({"approved_paths": ["../outside.jpg"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside"):
        index_dish_images.load_manifest_image_paths(root, manifest)


async def test_missing_root_raises_before_touching_qdrant(tmp_path, pipeline):
    with pytest.raises(FileNotFoundError):
        await index_dish_images.run([tmp_path / "does_not_exist"])

    assert pipeline["init_force"] == []


async def test_cap_below_one_is_rejected(tmp_path, pipeline):
    with pytest.raises(ValueError):
        await index_dish_images.run([tmp_path], cap=0)


def test_parser_defaults_match_contract():
    arguments = index_dish_images.build_parser().parse_args([])

    assert arguments.roots == []
    assert arguments.cap == 50
    assert arguments.source == "seed"
    assert arguments.force is False


def test_default_roots_use_only_the_curated_reference_album():
    roots = index_dish_images.default_roots()

    assert roots == [
        index_dish_images.PROJECT_ROOT / "data" / "images" / "references"
    ]
