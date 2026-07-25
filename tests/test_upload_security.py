"""Image uploads must be decoded, bounded and sanitized before use."""

from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from backend.api.upload_utils import validate_and_sanitize_image


def _image_bytes(
    image_format: str = "JPEG",
    *,
    width: int = 32,
    height: int = 24,
    exif: Image.Exif | None = None,
) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (width, height), (120, 80, 40))
    save_options = {"exif": exif} if exif is not None else {}
    image.save(output, format=image_format, **save_options)
    return output.getvalue()


def test_rejects_spoofed_jpeg_content() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_sanitize_image(b"not-a-real-image", "image/jpeg")

    assert exc.value.status_code == 400
    assert exc.value.detail == "File tải lên không phải ảnh hợp lệ."


def test_rejects_mime_that_does_not_match_decoded_format() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_sanitize_image(_image_bytes("PNG"), "image/jpeg")

    assert exc.value.status_code == 400
    assert "không khớp" in exc.value.detail


def test_rejects_image_over_pixel_budget() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_sanitize_image(
            _image_bytes(width=40, height=30),
            "image/jpeg",
            max_pixels=1_000,
        )

    assert exc.value.status_code == 413
    assert "độ phân giải" in exc.value.detail


def test_reencodes_image_without_exif_metadata() -> None:
    exif = Image.Exif()
    exif[0x010E] = "private description"

    sanitized = validate_and_sanitize_image(
        _image_bytes(exif=exif),
        "image/jpeg",
    )

    decoded = Image.open(BytesIO(sanitized.content))
    assert sanitized.extension == ".jpg"
    assert sanitized.content_type == "image/jpeg"
    assert decoded.size == (32, 24)
    assert len(decoded.getexif()) == 0


def test_reports_dimensions_after_exif_orientation_is_applied() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6

    sanitized = validate_and_sanitize_image(
        _image_bytes(width=32, height=24, exif=exif),
        "image/jpeg",
    )

    decoded = Image.open(BytesIO(sanitized.content))
    assert decoded.size == (24, 32)
    assert (sanitized.width, sanitized.height) == decoded.size
