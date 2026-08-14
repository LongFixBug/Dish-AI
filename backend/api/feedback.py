"""Feedback endpoint — human-in-the-loop: lưu ảnh + label đúng để cải thiện
catalog recognition.

POST /api/v1/feedback/training-data nhận ảnh có consent và đưa vào hàng chờ
review; chỉ ảnh được admin duyệt mới có thể export để train.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.upload_utils import (
    MAX_IMAGE_UPLOAD_BYTES,
    read_upload_limited,
    validate_and_sanitize_image,
    validate_image_content_type,
)
from backend.api.dependencies import CurrentUser, require_admin, require_user
from backend.config import settings
from backend.db.models import FeedbackSubmission, RecognitionEvent
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
    capture_source: Literal["camera", "upload"]
    message: str = ""


class FeedbackReviewRequest(BaseModel):
    """Nhãn cuối cùng do reviewer xác nhận trước khi train."""

    status: Literal["approved", "rejected"]
    reviewed_dish_name: str | None = Field(default=None, max_length=300)
    reviewer_note: str | None = Field(default=None, max_length=500)

    @field_validator("reviewed_dish_name", "reviewer_note", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def require_label_when_approved(self) -> "FeedbackReviewRequest":
        if self.status == "approved" and not self.reviewed_dish_name:
            raise ValueError("Duyệt ảnh phải có reviewed_dish_name.")
        return self


class FeedbackReviewItem(BaseModel):
    """Metadata đủ để admin review, không trả bytes ảnh trong API queue."""

    id: str
    object_key: str
    original_name: str
    submitted_label: str
    reviewed_label: str | None
    capture_source: Literal["camera", "upload"]
    consent_to_training: bool
    status: Literal["pending", "approved", "rejected", "deleted"]
    recognition_event_id: str | None
    reviewer_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


def _review_item(submission: FeedbackSubmission) -> FeedbackReviewItem:
    return FeedbackReviewItem(
        id=str(submission.id),
        object_key=submission.object_key,
        original_name=submission.original_name,
        submitted_label=submission.dish_name_slug,
        reviewed_label=submission.reviewed_dish_slug,
        capture_source=submission.capture_source,
        consent_to_training=submission.consent_to_training,
        status=submission.status,
        recognition_event_id=(
            str(submission.recognition_event_id)
            if submission.recognition_event_id
            else None
        ),
        reviewer_note=submission.reviewer_note,
        created_at=submission.created_at,
        reviewed_at=submission.reviewed_at,
    )


@router.post("/feedback/training-data", response_model=TrainingDataResponse)
async def save_training_data(
    correct_dish_name: str = Form(...),
    consent_to_training: bool = Form(...),
    recognition_event_id: uuid.UUID | None = Form(default=None),
    capture_source: Literal["camera", "upload"] = Form(default="upload"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> TrainingDataResponse:
    """Lưu ảnh + label đúng để cải thiện nhận diện/catalog.

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

    event_id: str | None = None
    if recognition_event_id is not None:
        event = await session.scalar(
            select(RecognitionEvent).where(
                RecognitionEvent.id == str(recognition_event_id),
                RecognitionEvent.submitted_by == current_user.id,
            )
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt nhận diện.")
        event_id = str(event.id)

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
            recognition_event_id=event_id,
            dish_name_slug=normalized,
            original_name=correct_dish_name.strip(),
            object_key=object_key,
            content_type=image.content_type,
            file_size_bytes=len(image.content),
            width=image.width,
            height=image.height,
            capture_source=capture_source,
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
        capture_source=capture_source,
        message="Cảm ơn bạn đã đóng góp. Ảnh đang chờ kiểm duyệt trước khi "
        "được dùng để cải thiện mô hình.",
    )


@router.get(
    "/feedback/review-queue",
    response_model=list[FeedbackReviewItem],
)
async def list_feedback_review_queue(
    queue_status: Literal["pending", "approved", "rejected", "deleted"] = Query(
        default="pending", alias="status"
    ),
    limit: int = Query(default=200, ge=1, le=500),
    _admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[FeedbackReviewItem]:
    """Danh sách ảnh để admin xác nhận nhãn trước khi xuất dataset."""
    result = await session.execute(
        select(FeedbackSubmission)
        .where(FeedbackSubmission.status == queue_status)
        .order_by(FeedbackSubmission.created_at.asc())
        .limit(limit)
    )
    return [_review_item(row) for row in result.scalars().all()]


@router.get("/feedback/training-data/{submission_id}/image")
async def get_feedback_review_image(
    submission_id: uuid.UUID,
    _admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Return one pending/reviewed image for the admin review screen."""
    submission = await session.scalar(
        select(FeedbackSubmission).where(FeedbackSubmission.id == str(submission_id))
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phản hồi.")
    try:
        content, content_type = await object_storage.get(submission.object_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh phản hồi.") from exc
    except Exception as exc:
        logger.exception("Failed to read feedback image %s", submission_id)
        raise HTTPException(
            status_code=503,
            detail="Chưa thể mở ảnh phản hồi lúc này.",
        ) from exc
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "no-store"},
    )


@router.patch(
    "/feedback/training-data/{submission_id}/review",
    response_model=FeedbackReviewItem,
)
async def review_training_data(
    submission_id: uuid.UUID,
    payload: FeedbackReviewRequest,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> FeedbackReviewItem:
    """Approve/reject một feedback row và lưu canonical label của reviewer."""
    submission = await session.scalar(
        select(FeedbackSubmission).where(FeedbackSubmission.id == str(submission_id))
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phản hồi.")
    if payload.status == "approved" and not submission.consent_to_training:
        raise HTTPException(
            status_code=400,
            detail="Không thể duyệt ảnh chưa có consent training.",
        )

    submission.status = payload.status
    submission.reviewed_dish_slug = (
        _normalize_dish_name(payload.reviewed_dish_name or "")
        if payload.status == "approved"
        else None
    )
    submission.reviewer_note = payload.reviewer_note
    submission.reviewed_by = admin.id
    submission.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(submission)
    return _review_item(submission)


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
