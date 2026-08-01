"""Regression tests cho chức năng lưu ảnh training từ client."""

import uuid
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
from sqlalchemy import delete

import backend.services.dish_image_index as dish_image_index
import backend.services.image_embeddings as image_embeddings
from backend.api import feedback
from backend.db.models import FeedbackSubmission, RecognitionEvent, User
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


async def test_index_feedback_image_upserts_feedback_entry(monkeypatch) -> None:
    """Ảnh feedback được embed và upsert vào album với payload đúng contract."""
    monkeypatch.setattr(feedback.settings, "image_embed_enabled", True)
    captured: dict = {}

    async def fake_embed(data: bytes) -> list[float]:
        captured["bytes"] = data
        return [0.25] * 4

    async def fake_upsert(entries, vectors) -> int:
        captured["entries"] = entries
        captured["vectors"] = vectors
        return len(entries)

    monkeypatch.setattr(image_embeddings, "embed_image", fake_embed)
    monkeypatch.setattr(dish_image_index, "upsert_dish_image_vectors", fake_upsert)

    object_key = "feedback/2026/07/user-1/abc123.webp"
    await feedback._index_feedback_image(
        object_key=object_key,
        image_bytes=b"webp-bytes",
        dish_name="Phở bò",
        class_slug="pho_bo",
    )

    assert captured["bytes"] == b"webp-bytes"
    assert captured["vectors"] == [[0.25] * 4]
    entry = captured["entries"][0]
    assert entry.record_id == str(uuid.uuid5(uuid.NAMESPACE_URL, object_key))
    assert entry.dish_name == "Phở bò"
    assert entry.class_slug == "pho_bo"
    assert entry.source == "feedback"


async def test_index_feedback_image_swallows_album_failure(monkeypatch) -> None:
    """Album sập (embed OK nhưng Qdrant lỗi) → helper nuốt lỗi, không raise."""

    async def fake_embed(_data: bytes) -> list[float]:
        return [0.0] * 4

    async def failing_upsert(_entries, _vectors) -> int:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(image_embeddings, "embed_image", fake_embed)
    monkeypatch.setattr(
        dish_image_index, "upsert_dish_image_vectors", failing_upsert
    )

    await feedback._index_feedback_image(
        object_key="feedback/2026/07/user-1/def456.webp",
        image_bytes=b"webp-bytes",
        dish_name="Phở bò",
        class_slug="pho_bo",
    )


async def test_index_feedback_image_disabled_skips_album(monkeypatch) -> None:
    async def embed_must_not_run(_data: bytes) -> list[float]:
        raise AssertionError("Không được embed khi image_embed_enabled=False")

    monkeypatch.setattr(feedback.settings, "image_embed_enabled", False)
    monkeypatch.setattr(image_embeddings, "embed_image", embed_must_not_run)

    await feedback._index_feedback_image(
        object_key="feedback/2026/07/user-1/ghi789.webp",
        image_bytes=b"webp-bytes",
        dish_name="Phở bò",
        class_slug="pho_bo",
    )


async def test_feedback_still_succeeds_when_album_upsert_raises(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    """Endpoint vẫn 2xx khi index album thất bại — lưu phản hồi là ưu tiên."""
    monkeypatch.setattr(feedback.settings, "image_embed_enabled", True)
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

    async def fake_embed(_data: bytes) -> list[float]:
        return [0.0] * 4

    async def failing_upsert(_entries, _vectors) -> int:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(image_embeddings, "embed_image", fake_embed)
    monkeypatch.setattr(
        dish_image_index, "upsert_dish_image_vectors", failing_upsert
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
