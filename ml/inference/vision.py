"""Vision service — gọi Qwen3.7 Plus (qua OpenCode API) để nhận diện món ăn từ ảnh.

Đây là Tầng 2 (cloud fallback). Tầng 1 là CV model PyTorch local.
Flow: CV local → nếu confidence < 80% → fallback Qwen3.7 Plus.
"""

import base64
import json
from pathlib import Path

import httpx

from backend.config import settings


class VisionError(Exception):
    """Lỗi khi gọi Vision API."""


async def identify_dish(image_path: str | Path) -> dict:
    """Nhận diện món ăn từ ảnh.

    Gửi ảnh lên Qwen3.7 Plus, trả về:
        - dish_name: tên món ăn
        - ingredients: danh sách thành phần kèm gram ước lượng
        - confidence: độ tự tin (0-1)

    Raises:
        VisionError: nếu API lỗi hoặc response không hợp lệ.
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise VisionError(f"File không tồn tại: {image_path}")

    # Encode ảnh base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # Xác định MIME type
    suffix = image_path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(suffix, "image/jpeg")

    # Prompt cho nhận diện món Việt
    system_prompt = (
        "Bạn là chuyên gia ẩm thực Việt Nam. "
        "Khi nhìn ảnh món ăn, bạn phân tích và trả về JSON với cấu trúc chính xác sau:\n"
        '{\n'
        '  "dish_name": "tên món ăn (tiếng Việt)",\n'
        '  "ingredients": [\n'
        '    {"name": "tên thành phần", "gram": số_gram_ước_lượng}\n'
        '  ],\n'
        '  "confidence": độ_tự_tin_từ_0_đến_1\n'
        '}\n'
        "Lưu ý:\n"
        "- Ước lượng gram THỰC TẾ cho 1 phần ăn thông thường\n"
        "- Chỉ trả về JSON, không thêm text nào khác\n"
        "- Nếu không nhận diện được món, confidence = 0"
    )

    # Build request body — dùng OpenAI-compatible vision format
    request_body = {
        "model": settings.vision_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    },
                    {
                        "type": "text",
                        "text": "Hãy nhận diện món ăn trong ảnh này.",
                    },
                ],
            },
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    headers = {
        "Authorization": f"Bearer {settings.vision_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.vision_api_base}/chat/completions",
            json=request_body,
            headers=headers,
        )

    if response.status_code != 200:
        raise VisionError(
            f"Vision API lỗi {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # Parse JSON từ response
    try:
        result = _parse_json_response(content)
    except json.JSONDecodeError as e:
        raise VisionError(f"Không parse được JSON từ response: {content[:300]}") from e

    # Validate fields
    required_fields = ["dish_name", "ingredients", "confidence"]
    for field in required_fields:
        if field not in result:
            raise VisionError(f"Thiếu field '{field}' trong response: {result}")

    for ing in result["ingredients"]:
        if "name" not in ing or "gram" not in ing:
            raise VisionError(f"Ingredient thiếu name/gram: {ing}")

    return result


def _parse_json_response(content: str) -> dict:
    """Parse JSON từ LLM response — xử lý cả trường hợp bọc trong ```json."""

    content = content.strip()

    # Nếu LLM bọc trong markdown code block
    if content.startswith("```"):
        lines = content.split("\n")
        # Bỏ dòng đầu (```json) và dòng cuối (```)
        content = "\n".join(lines[1:-1])

    return json.loads(content)
