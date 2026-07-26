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
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.upload_utils import (
    MAX_IMAGE_UPLOAD_BYTES,
    read_upload_limited,
    validate_and_sanitize_image,
    validate_image_content_type,
)
from backend.api.dependencies import CurrentUser, require_user
from backend.config import settings
from backend.db.models import FeedbackSubmission
from backend.db.postgres import get_session
from backend.services.object_storage import create_object_storage

router = APIRouter(prefix="/api/v1", tags=["feedback"])

MAX_UPLOAD_BYTES = MAX_IMAGE_UPLOAD_BYTES
logger = logging.getLogger("foodai.feedback")
object_storage = create_object_storage(settings)


def _normalize_dish_name(name: str) -> str:
    """Chuẩn hóa tên món → snake_case không dấu.

    VD: "Phở bò tái" → "pho_bo_tai"
         "Bún đậu mắm tôm" → "bun_dau_mam_tom"
    """
    # Bỏ dấu tiếng Việt
    nfkd = unicodedata.normalize("NFKD", name.replace("Đ", "D").replace("đ", "d"))
    no_diacritic = "".join(c for c in nfkd if not unicodedata.combining(c))
    # lowercase, thay khoảng trắng + dấu câu → _
    slug = re.sub(r"[^\w\s-]", "", no_diacritic).strip().lower()
    slug = re.sub(r"[-\s]+", "_", slug)
    return slug


class TrainingDataResponse(BaseModel):
    """Response cho POST /feedback/training-data."""

    success: bool = True
    submission_id: str
    dish_name: str = Field(description="Tên món đã chuẩn hóa (snake_case)")
    saved_path: str = Field(description="Object key của ảnh đã lưu")
    total_images: int = Field(description="Tổng số ảnh đã tích lũy cho món này")
    message: str = ""


@router.post("/feedback/training-data", response_model=TrainingDataResponse)
async def save_training_data(
    correct_dish_name: str = Form(...),
    consent_to_training: bool = Form(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> TrainingDataResponse:
    """Lưu ảnh + label đúng để train lại EfficientNet.

    Args:
        correct_dish_name: Tên món ĐÚNG (từ Qwen hoặc user nhập). Sẽ được chuẩn hóa.
        file: File ảnh (JPEG/PNG/WebP).
    """
    validate_image_content_type(file)
    if not consent_to_training:
        raise HTTPException(
            status_code=400,
            detail="Bạn cần đồng ý sử dụng ảnh cho mục đích cải thiện mô hình.",
        )
    if not correct_dish_name or not correct_dish_name.strip():
        raise HTTPException(status_code=400, detail="Thiếu correct_dish_name.")

    normalized = _normalize_dish_name(correct_dish_name.strip())
    if not normalized:
        raise HTTPException(status_code=400, detail="Tên món không hợp lệ.")

    content = await read_upload_limited(file, max_bytes=MAX_UPLOAD_BYTES)
    image = await asyncio.to_thread(
        validate_and_sanitize_image,
        content,
        file.content_type,
    )

    now = datetime.now(timezone.utc)
    object_key = (
        f"feedback/{now:%Y/%m}/{current_user.id}/"
        f"{uuid.uuid4().hex}{image.extension}"
    )
    try:
        await object_storage.put(
            object_key,
            image.content,
            image.content_type,
        )
        submission = FeedbackSubmission(
            submitted_by=current_user.id,
            dish_name_slug=normalized,
            original_name=correct_dish_name.strip(),
            object_key=object_key,
            content_type=image.content_type,
            file_size_bytes=len(image.content),
            width=image.width,
            height=image.height,
            consent_to_training=True,
            retention_until=now + timedelta(days=settings.feedback_retention_days),
        )
        session.add(submission)
        await session.flush()
        total = await session.scalar(
            select(func.count())
            .select_from(FeedbackSubmission)
            .where(
                FeedbackSubmission.dish_name_slug == normalized,
                FeedbackSubmission.status.in_(("pending", "approved")),
            )
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        try:
            await object_storage.delete(object_key)
        except Exception:
            logger.exception("Failed to remove orphan feedback object %s", object_key)
        logger.exception("Failed to persist feedback metadata")
        raise HTTPException(
            status_code=503,
            detail="Chưa thể lưu phản hồi lúc này. Vui lòng thử lại sau.",
        ) from exc

    return TrainingDataResponse(
        submission_id=str(submission.id),
        dish_name=normalized,
        saved_path=object_key,
        total_images=int(total or 0),
        message="Cảm ơn bạn đã đóng góp. Ảnh đang chờ kiểm duyệt trước khi "
        "được dùng để cải thiện mô hình.",
    )


@router.delete(
    "/feedback/training-data/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_training_data(
    # UUID chứ không phải str: id sai định dạng phải là 422 chứ không phải
    # 500 do asyncpg ném 'invalid input syntax for type uuid'.
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    submission = await session.scalar(
        select(FeedbackSubmission).where(
            FeedbackSubmission.id == str(submission_id),
            FeedbackSubmission.submitted_by == current_user.id,
        )
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phản hồi.")
    if submission.status != "deleted":
        try:
            await object_storage.delete(submission.object_key)
            submission.status = "deleted"
            submission.reviewed_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.exception("Failed to delete feedback %s", submission_id)
            raise HTTPException(
                status_code=503,
                detail="Chưa thể xóa phản hồi lúc này. Vui lòng thử lại sau.",
            ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
