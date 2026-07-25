"""Decode, bound and sanitize untrusted image uploads."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_IMAGE_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


@dataclass(frozen=True)
class SanitizedImage:
    content: bytes
    content_type: str
    extension: str
    width: int
    height: int


def validate_image_content_type(file: UploadFile) -> None:
    """Reject media types that the CV and Vision pipelines cannot decode."""
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        supported = "JPEG, PNG, WebP"
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file.content_type}. Chỉ {supported}.",
        )


async def read_upload_limited(
    file: UploadFile,
    *,
    max_bytes: int = MAX_IMAGE_UPLOAD_BYTES,
) -> bytes:
    """Read an upload incrementally and stop once it exceeds the size limit."""
    content = bytearray()
    while chunk := await file.read(UPLOAD_CHUNK_BYTES):
        if len(content) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Ảnh quá lớn (tối đa {max_bytes // (1024 * 1024)} MB).",
            )
        content.extend(chunk)

    if not content:
        raise HTTPException(status_code=400, detail="File ảnh rỗng.")
    return bytes(content)


def validate_and_sanitize_image(
    content: bytes,
    declared_content_type: str | None,
    *,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> SanitizedImage:
    """Decode once, enforce pixel limits and re-encode without metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                image_format = (source.format or "").upper()
                if image_format not in IMAGE_FORMATS:
                    raise HTTPException(
                        status_code=400,
                        detail="Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.",
                    )
                expected_type, extension = IMAGE_FORMATS[image_format]
                if declared_content_type != expected_type:
                    raise HTTPException(
                        status_code=400,
                        detail="Định dạng khai báo không khớp nội dung ảnh.",
                    )
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise HTTPException(
                        status_code=413,
                        detail="Ảnh có độ phân giải quá lớn.",
                    )
                source.load()
                sanitized = ImageOps.exif_transpose(source)
                width, height = sanitized.size
                output = BytesIO()
                if image_format == "JPEG":
                    sanitized.convert("RGB").save(
                        output,
                        format="JPEG",
                        quality=90,
                        optimize=True,
                    )
                elif image_format == "PNG":
                    mode = "RGBA" if "A" in sanitized.getbands() else "RGB"
                    sanitized.convert(mode).save(output, format="PNG", optimize=True)
                else:
                    mode = "RGBA" if "A" in sanitized.getbands() else "RGB"
                    sanitized.convert(mode).save(
                        output,
                        format="WEBP",
                        quality=90,
                        method=4,
                    )
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail="File tải lên không phải ảnh hợp lệ.",
        ) from exc

    return SanitizedImage(
        content=output.getvalue(),
        content_type=expected_type,
        extension=extension,
        width=width,
        height=height,
    )
