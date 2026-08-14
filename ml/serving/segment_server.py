"""Sidecar tách chủ thể khỏi ảnh món ăn (port 8083).

Trả về PNG nền trong suốt để app dán thành sticker. Model u2net chỉ được nạp
lười ở request đầu tiên, và import module này KHÔNG kéo theo onnxruntime nên
test lẫn tooling vẫn nhẹ.

API contract:
- ``POST /v1/segment`` body ``{"image": "<base64>", "max_side": 512}`` →
  ``{"image": "<base64 PNG>", "width": int, "height": int}``
- ``GET /health`` → ``{"status": "ok", "model": str}``
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from PIL import Image, ImageFilter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "u2net"
MODEL_NAME = os.environ.get("SEGMENT_MODEL", DEFAULT_MODEL)

# Sticker dán lên ô lịch nên không cần to; ảnh càng nhỏ càng nhanh và càng
# đỡ tốn chỗ trên máy người dùng.
DEFAULT_MAX_SIDE = 512
MIN_MAX_SIDE = 64
MAX_MAX_SIDE = 2048
MAX_IMAGE_BYTES = 12 * 1024 * 1024

# Vành trắng bao quanh chủ thể — thứ khiến mắt người đọc ra "sticker" chứ
# không phải "ảnh bị khoét nền".
DEFAULT_OUTLINE_WIDTH = 8
MAX_OUTLINE_WIDTH = 40

app = FastAPI(title="FoodAI Subject Segmentation Sidecar")


class SegmentRequest(BaseModel):
    """Một ảnh base64 cần tách nền."""

    image: str = Field(min_length=1)
    max_side: int = Field(default=DEFAULT_MAX_SIDE, ge=MIN_MAX_SIDE, le=MAX_MAX_SIDE)
    outline_width: int = Field(default=DEFAULT_OUTLINE_WIDTH, ge=0, le=MAX_OUTLINE_WIDTH)


class SegmentResponse(BaseModel):
    """PNG nền trong suốt kèm kích thước thật sau khi thu nhỏ."""

    image: str
    width: int
    height: int
    model: str


@dataclass(frozen=True)
class SegmentBackend:
    """Hàm tách nền đã nạp sẵn model."""

    model_name: str
    remove: Callable[[Image.Image], Image.Image]


_backend: SegmentBackend | None = None
_backend_lock = threading.Lock()


def decode_image(encoded: str) -> Image.Image:
    """Giải base64 thành ảnh RGB, từ chối rõ ràng khi dữ liệu hỏng."""
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Ảnh base64 không hợp lệ") from exc
    if not raw:
        raise HTTPException(status_code=422, detail="Ảnh rỗng")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh quá lớn")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            return image.convert("RGB")
    except Exception as exc:  # noqa: BLE001 — mọi lỗi giải mã đều là ảnh hỏng
        raise HTTPException(status_code=422, detail="Không đọc được ảnh") from exc


def shrink_to_fit(image: Image.Image, max_side: int) -> Image.Image:
    """Thu nhỏ giữ tỉ lệ sao cho cạnh dài nhất không vượt ``max_side``.

    Ảnh vốn đã nhỏ hơn thì giữ nguyên: phóng to chỉ làm mờ chứ không thêm
    chi tiết nào cho việc tách nền.
    """
    longest = max(image.size)
    if longest <= max_side:
        return image
    scale = max_side / longest
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def crop_to_subject(image: Image.Image) -> Image.Image:
    """Cắt sát viền chủ thể để sticker không có vành trong suốt thừa.

    Ảnh tách trượt (không còn pixel nào đục) thì giữ nguyên thay vì trả về
    ảnh rỗng làm hỏng phía gọi.
    """
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    return image if box is None else image.crop(box)


def add_sticker_outline(image: Image.Image, width: int) -> Image.Image:
    """Bọc chủ thể bằng vành trắng đều, kiểu sticker dán vở.

    Cách làm: nong vùng đục của kênh alpha ra ``width`` pixel (phép giãn ảnh),
    lấy phần nong ra đó làm mặt nạ cho một lớp trắng, rồi đặt chủ thể lên trên.
    Ảnh phải được nới rộng trước, nếu không vành sẽ bị chính khung ảnh xén mất.
    """
    if width <= 0:
        return image
    padded = Image.new(
        "RGBA",
        (image.width + width * 2, image.height + width * 2),
        (255, 255, 255, 0),
    )
    padded.paste(image, (width, width))

    # MaxFilter cần kích thước lẻ; bán kính w tương ứng cửa sổ 2w+1.
    grown = padded.getchannel("A").filter(ImageFilter.MaxFilter(width * 2 + 1))
    # Làm mượt nhẹ cho vành bớt răng cưa, rồi ép lại thành đục hẳn để vành
    # không bị mờ dần ở rìa.
    grown = grown.filter(ImageFilter.GaussianBlur(radius=width / 4))
    grown = grown.point(lambda value: 255 if value >= 128 else 0)

    halo = Image.new("RGBA", padded.size, (255, 255, 255, 255))
    halo.putalpha(grown)
    return Image.alpha_composite(halo, padded)


def _load_backend() -> SegmentBackend:
    """Nạp u2net một lần duy nhất, có khoá để hai request đầu không nạp đôi."""
    global _backend
    if _backend is not None:
        return _backend
    with _backend_lock:
        if _backend is not None:
            return _backend
        from rembg import new_session, remove  # nặng: chỉ import khi thật sự cần

        logger.info("Loading segmentation model %s", MODEL_NAME)
        session = new_session(MODEL_NAME)

        def _remove(image: Image.Image) -> Image.Image:
            return remove(image, session=session).convert("RGBA")

        _backend = SegmentBackend(model_name=MODEL_NAME, remove=_remove)
        return _backend


def encode_png(image: Image.Image) -> str:
    """Đóng gói ảnh RGBA thành PNG base64."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@app.get("/health")
def health() -> dict[str, str]:
    """Sống chưa — không nạp model để healthcheck còn nhanh."""
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/v1/segment", response_model=SegmentResponse)
def segment(request: SegmentRequest) -> SegmentResponse:
    """Tách chủ thể khỏi nền, trả PNG trong suốt đã cắt sát viền."""
    source = shrink_to_fit(decode_image(request.image), request.max_side)
    backend = _load_backend()
    try:
        cut = crop_to_subject(backend.remove(source))
        cut = add_sticker_outline(cut, request.outline_width)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Segmentation failed")
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ tách ảnh đang bận, hãy thử lại.",
        ) from exc
    return SegmentResponse(
        image=encode_png(cut),
        width=cut.width,
        height=cut.height,
        model=backend.model_name,
    )
