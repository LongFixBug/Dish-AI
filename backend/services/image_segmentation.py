"""Tách chủ thể ảnh món ăn thành sticker qua sidecar (port 8083).

Sticker là thứ trang trí — sidecar chết thì luồng phân tích vẫn phải chạy
bình thường, nên caller nhận ``None`` chứ không nhận lỗi.
"""

import base64
import logging

from backend.config import settings
from backend.services.resilience import ResilientHttpClient

SEGMENT_API = f"{settings.segment_url}/v1/segment"
TIMEOUT = 60.0

logger = logging.getLogger("foodai")

segment_http_client = ResilientHttpClient(
    service="image_segmentation",
    timeout_seconds=TIMEOUT,
    max_concurrency=settings.segment_max_concurrency,
)


async def cut_out_subject(data: bytes) -> bytes | None:
    """Trả PNG nền trong suốt kèm viền trắng, hoặc ``None`` khi không làm được.

    Mọi sự cố của sidecar đều bị nuốt kèm cảnh báo: người dùng thà thấy ảnh
    gốc còn hơn phân tích thất bại chỉ vì cái sticker.
    """
    if not settings.segment_enabled:
        return None
    try:
        response = await segment_http_client.post(
            SEGMENT_API,
            json={
                "image": base64.b64encode(data).decode("ascii"),
                "max_side": settings.segment_max_side,
                "outline_width": settings.segment_outline_width,
            },
        )
        payload = response.json()
        encoded = payload.get("image")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("sidecar trả về ảnh rỗng")
        return base64.b64decode(encoded)
    except Exception:  # noqa: BLE001 — sticker hỏng không được làm hỏng /analyze
        logger.warning("Không tạo được sticker, bỏ qua", exc_info=True)
        return None
