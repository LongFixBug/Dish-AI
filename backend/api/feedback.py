"""Feedback endpoint — human-in-the-loop: lưu ảnh + label đúng để train lại CV.

POST /api/v1/feedback/training-data:
  - Nhận ảnh + correct_dish_name (từ Qwen hoặc user tự nhập)
  - Chuẩn hóa tên món → snake_case
  - Lưu ảnh vào data/images/feedback/<ten_mon>/
  - Ghi log vào data/images/feedback/feedback_log.jsonl
  - Trả về số ảnh đã tích lũy cho món đó
"""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["feedback"])

FEEDBACK_DIR = Path("data/images/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "feedback_log.jsonl"


def _normalize_dish_name(name: str) -> str:
    """Chuẩn hóa tên món → snake_case không dấu.

    VD: "Phở bò tái" → "pho_bo_tai"
         "Bún đậu mắm tôm" → "bun_dau_mam_tom"
    """
    # Bỏ dấu tiếng Việt
    nfkd = unicodedata.normalize("NFKD", name)
    no_diacritic = "".join(c for c in nfkd if not unicodedata.combining(c))
    # lowercase, thay khoảng trắng + dấu câu → _
    slug = re.sub(r"[^\w\s-]", "", no_diacritic).strip().lower()
    slug = re.sub(r"[-\s]+", "_", slug)
    return slug


def _append_log(log_path: Path, entry: dict) -> None:
    """Ghi 1 dòng JSONL vào log (sync — gọi qua asyncio.to_thread)."""
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class TrainingDataResponse(BaseModel):
    """Response cho POST /feedback/training-data."""

    success: bool = True
    dish_name: str = Field(description="Tên món đã chuẩn hóa (snake_case)")
    saved_path: str = Field(description="Đường dẫn file ảnh đã lưu")
    total_images: int = Field(description="Tổng số ảnh đã tích lũy cho món này")
    message: str = ""


@router.post("/feedback/training-data", response_model=TrainingDataResponse)
async def save_training_data(
    correct_dish_name: str = Form(...),
    file: UploadFile = File(...),
) -> TrainingDataResponse:
    """Lưu ảnh + label đúng để train lại EfficientNet.

    Args:
        correct_dish_name: Tên món ĐÚNG (từ Qwen hoặc user nhập). Sẽ được chuẩn hóa.
        file: File ảnh (JPEG/PNG/WebP).
    """
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file.content_type}.",
        )

    if not correct_dish_name or not correct_dish_name.strip():
        raise HTTPException(status_code=400, detail="Thiếu correct_dish_name.")

    normalized = _normalize_dish_name(correct_dish_name.strip())

    # Tạo thư mục cho món
    dish_dir = FEEDBACK_DIR / normalized
    dish_dir.mkdir(parents=True, exist_ok=True)

    # Tạo tên file duy nhất: timestamp + tên gốc (sau khi clean)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_filename = re.sub(r"[^\w.]", "_", file.filename or "image.jpg")
    saved_filename = f"{ts}_{safe_filename}"
    saved_path = dish_dir / saved_filename

    content = await file.read()
    saved_path.write_bytes(content)

    # Đếm tổng số ảnh đã tích lũy (chỉ đếm file ảnh, không đếm .DS_Store hay log)
    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    total = sum(1 for f in dish_dir.iterdir() if f.suffix.lower() in image_extensions)

    # Ghi log — dùng asyncio.to_thread cho sync I/O để không block event loop
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dish_name": normalized,
        "original_name": correct_dish_name.strip(),
        "filename": saved_filename,
        "file_size_bytes": len(content),
    }
    await asyncio.to_thread(_append_log, LOG_PATH, log_entry)

    return TrainingDataResponse(
        dish_name=normalized,
        saved_path=str(saved_path),
        total_images=total,
        message=f"Đã lưu ảnh #{total} cho món '{normalized}'. "
                 "Tích lũy đủ (~20-30 ảnh) → chạy "
                 "scripts/split_feedback_images.py rồi ml/training/train.py.",
    )
