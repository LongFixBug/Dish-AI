"""Durable feedback object storage contracts."""

from pathlib import Path

import pytest

from backend.services.object_storage import FilesystemObjectStorage


async def test_filesystem_storage_writes_only_inside_configured_root(
    tmp_path: Path,
) -> None:
    storage = FilesystemObjectStorage(tmp_path)

    await storage.put("feedback/user/image.jpg", b"image-bytes", "image/jpeg")

    assert (tmp_path / "feedback" / "user" / "image.jpg").read_bytes() == b"image-bytes"


async def test_filesystem_storage_reads_image_with_content_type(tmp_path: Path) -> None:
    storage = FilesystemObjectStorage(tmp_path)

    await storage.put("feedback/user/image.jpg", b"image-bytes", "image/jpeg")

    content, content_type = await storage.get("feedback/user/image.jpg")

    assert content == b"image-bytes"
    assert content_type == "image/jpeg"


async def test_filesystem_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = FilesystemObjectStorage(tmp_path)

    with pytest.raises(ValueError):
        await storage.put("../outside.jpg", b"bad", "image/jpeg")

    assert not (tmp_path.parent / "outside.jpg").exists()
