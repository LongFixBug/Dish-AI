"""Regression tests cho chức năng lưu ảnh training từ client."""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.api import feedback
from backend.config import settings
from backend.db.models import FeedbackSubmission, RecognitionEvent, User
from backend.main import app
from backend.services.auth import TokenManager
from backend.services.object_storage import FilesystemObjectStorage


def _webp_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), (200, 120, 40)).save(output, format="WEBP")
    return output.getvalue()


async def test_feedback_accepts_label_as_multipart_form(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    test_user_id = "00000000-0000-0000-0000-000000000001"
    created_test_user = await db_session.get(User, test_user_id) is None
    if created_test_user:
        db_session.add(
            User(
                id=test_user_id,
                email="feedback-fixture@example.com",
                display_name="Feedback Fixture",
                password_hash="not-used-in-this-test",
            )
        )
        await db_session.commit()
    event = RecognitionEvent(
        submitted_by=test_user_id,
        source="vision",
        final_dish_name="Cơm sườn",
    )
    db_session.add(event)
    await db_session.commit()
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr(
        feedback,
        "object_storage",
        FilesystemObjectStorage(feedback_dir),
    )
    original_name = f"Cơm sườn {uuid4().hex[:8]}"
    normalized = feedback._normalize_dish_name(original_name)

    try:
        response = client.post(
            "/api/v1/feedback/training-data",
            files={
                "file": ("com_suon.webp", _webp_bytes(), "image/webp"),
                "correct_dish_name": (None, original_name),
                "consent_to_training": (None, "true"),
                "recognition_event_id": (None, event.id),
                "capture_source": (None, "camera"),
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["dish_name"] == normalized
        assert data["total_images"] == 1
        assert data["submission_id"]
        assert "Cảm ơn" in data["message"]
        assert "scripts/" not in data["message"]
        submission = await db_session.get(FeedbackSubmission, data["submission_id"])
        assert submission is not None
        assert submission.recognition_event_id == event.id
        assert submission.capture_source == "camera"
        stored_path = feedback_dir / Path(data["saved_path"])
        assert stored_path.exists()

        deleted = client.delete(
            f"/api/v1/feedback/training-data/{data['submission_id']}"
        )
        assert deleted.status_code == 204
        assert not stored_path.exists()
    finally:
        await db_session.execute(
            delete(FeedbackSubmission).where(
                FeedbackSubmission.dish_name_slug == normalized
            )
        )
        await db_session.execute(delete(RecognitionEvent).where(RecognitionEvent.id == event.id))
        if created_test_user:
            await db_session.execute(delete(User).where(User.id == test_user_id))
        await db_session.commit()


def test_feedback_rejects_blank_label(client, tmp_path, monkeypatch) -> None:
    del tmp_path, monkeypatch

    response = client.post(
        "/api/v1/feedback/training-data",
        files={
            "file": ("food.jpg", b"fake-jpeg-content", "image/jpeg"),
            "correct_dish_name": (None, "   "),
            "consent_to_training": (None, "true"),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Thiếu correct_dish_name."


def test_feedback_rejects_label_without_safe_characters(
    client, tmp_path, monkeypatch
) -> None:
    del tmp_path, monkeypatch

    response = client.post(
        "/api/v1/feedback/training-data",
        files={
            "file": ("food.jpg", b"fake-jpeg-content", "image/jpeg"),
            "correct_dish_name": (None, "!!!"),
            "consent_to_training": (None, "true"),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Tên món không hợp lệ."


def test_feedback_rejects_oversized_upload(client, tmp_path, monkeypatch) -> None:
    del tmp_path, monkeypatch
    oversized = b"x" * (feedback.MAX_UPLOAD_BYTES + 1)

    response = client.post(
        "/api/v1/feedback/training-data",
        files={
            "file": ("food.jpg", oversized, "image/jpeg"),
            "correct_dish_name": (None, "Phở bò"),
            "consent_to_training": (None, "true"),
        },
    )

    assert response.status_code == 413


def test_feedback_requires_explicit_training_consent(client) -> None:
    response = client.post(
        "/api/v1/feedback/training-data",
        files={
            "file": ("food.webp", _webp_bytes(), "image/webp"),
            "correct_dish_name": (None, "Phở bò"),
            "consent_to_training": (None, "false"),
        },
    )

    assert response.status_code == 400
    assert "đồng ý" in response.json()["detail"]


def test_feedback_slug_removes_vietnamese_d_stroke() -> None:
    assert feedback._normalize_dish_name("Đậu hũ") == "dau_hu"


async def test_feedback_still_succeeds_without_local_image_indexer(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    """Feedback vẫn lưu được khi runtime không còn image-indexing sidecar."""
    test_user_id = "00000000-0000-0000-0000-000000000001"
    created_test_user = await db_session.get(User, test_user_id) is None
    if created_test_user:
        db_session.add(
            User(
                id=test_user_id,
                email="feedback-fixture@example.com",
                display_name="Feedback Fixture",
                password_hash="not-used-in-this-test",
            )
        )
        await db_session.commit()
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr(
        feedback,
        "object_storage",
        FilesystemObjectStorage(feedback_dir),
    )

    original_name = f"Cơm sườn {uuid4().hex[:8]}"
    normalized = feedback._normalize_dish_name(original_name)

    try:
        response = client.post(
            "/api/v1/feedback/training-data",
            files={
                "file": ("com_suon.webp", _webp_bytes(), "image/webp"),
                "correct_dish_name": (None, original_name),
                "consent_to_training": (None, "true"),
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["dish_name"] == normalized
        stored_path = feedback_dir / Path(data["saved_path"])
        assert stored_path.exists()
    finally:
        await db_session.execute(
            delete(FeedbackSubmission).where(
                FeedbackSubmission.dish_name_slug == normalized
            )
        )
        if created_test_user:
            await db_session.execute(delete(User).where(User.id == test_user_id))
        await db_session.commit()


def test_feedback_review_request_requires_a_reviewed_label_for_approval() -> None:
    import pytest
    from pydantic import ValidationError

    from backend.api.feedback import FeedbackReviewRequest

    with pytest.raises(ValidationError):
        FeedbackReviewRequest(status="approved")

    request = FeedbackReviewRequest(
        status="approved",
        reviewed_dish_name=" Phở bò ",
        reviewer_note="Ảnh rõ, nhãn đã kiểm tra",
    )
    assert request.reviewed_dish_name == "Phở bò"


async def test_admin_can_approve_feedback_with_canonical_label(db_session) -> None:
    admin_id = str(uuid4())
    submission_id = str(uuid4())
    db_session.add(
        User(
            id=admin_id,
            email=f"admin-{admin_id}@example.com",
            display_name="Feedback Admin",
            password_hash="not-used",
            role="admin",
        )
    )
    await db_session.flush()
    db_session.add(
        FeedbackSubmission(
            id=submission_id,
            submitted_by=admin_id,
            dish_name_slug="pho",
            original_name="Phở",
            object_key=f"feedback/test/{submission_id}.jpg",
            content_type="image/jpeg",
            file_size_bytes=10,
            width=10,
            height=10,
            capture_source="camera",
            consent_to_training=True,
            retention_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()
    token, _ = TokenManager.from_settings(settings).create_access_token(
        user_id=admin_id,
        role="admin",
    )

    try:
        with TestClient(
            app,
            headers={"Authorization": f"Bearer {token}"},
        ) as admin_client:
            response = admin_client.patch(
                f"/api/v1/feedback/training-data/{submission_id}/review",
                json={
                    "status": "approved",
                    "reviewed_dish_name": "Phở bò",
                    "reviewer_note": "Ảnh camera rõ",
                },
            )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "approved"
        assert payload["reviewed_label"] == "pho_bo"
        assert payload["capture_source"] == "camera"
    finally:
        await db_session.execute(
            delete(FeedbackSubmission).where(FeedbackSubmission.id == submission_id)
        )
        await db_session.execute(delete(User).where(User.id == admin_id))
        await db_session.commit()


async def test_admin_can_open_feedback_image_for_review(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    admin_id = str(uuid4())
    submission_id = str(uuid4())
    storage = FilesystemObjectStorage(tmp_path)
    monkeypatch.setattr(feedback, "object_storage", storage)
    await storage.put(
        f"feedback/test/{submission_id}.jpg",
        b"review-image",
        "image/jpeg",
    )
    db_session.add(
        User(
            id=admin_id,
            email=f"admin-image-{admin_id}@example.com",
            display_name="Feedback Image Admin",
            password_hash="not-used",
            role="admin",
        )
    )
    await db_session.flush()
    db_session.add(
        FeedbackSubmission(
            id=submission_id,
            submitted_by=admin_id,
            dish_name_slug="pho_bo",
            original_name="Phở bò",
            object_key=f"feedback/test/{submission_id}.jpg",
            content_type="image/jpeg",
            file_size_bytes=len(b"review-image"),
            width=10,
            height=10,
            capture_source="camera",
            consent_to_training=True,
            retention_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()
    token, _ = TokenManager.from_settings(settings).create_access_token(
        user_id=admin_id,
        role="admin",
    )

    try:
        with TestClient(
            app,
            headers={"Authorization": f"Bearer {token}"},
        ) as admin_client:
            response = admin_client.get(
                f"/api/v1/feedback/training-data/{submission_id}/image"
            )

        assert response.status_code == 200, response.text
        assert response.content == b"review-image"
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["cache-control"] == "no-store"
    finally:
        await db_session.execute(
            delete(FeedbackSubmission).where(FeedbackSubmission.id == submission_id)
        )
        await db_session.execute(delete(User).where(User.id == admin_id))
        await db_session.commit()
