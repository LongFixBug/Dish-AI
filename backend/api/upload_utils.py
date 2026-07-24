"""Shared validation helpers for image upload endpoints."""

from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


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
