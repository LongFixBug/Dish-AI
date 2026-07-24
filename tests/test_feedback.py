"""Regression tests cho chức năng lưu ảnh training từ Streamlit."""

from pathlib import Path

from backend.api import feedback


def test_feedback_accepts_label_as_multipart_form(client, tmp_path, monkeypatch) -> None:
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr(feedback, "FEEDBACK_DIR", feedback_dir)
    monkeypatch.setattr(feedback, "LOG_PATH", feedback_dir / "feedback_log.jsonl")

    response = client.post(
        "/api/v1/feedback/training-data",
        files={
            "file": ("com_suon.webp", b"fake-webp-content", "image/webp"),
            "correct_dish_name": (None, "Cơm sườn"),
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["dish_name"] == "com_suon"
    assert data["total_images"] == 1
    assert "scripts/split_feedback_images.py" in data["message"]
    assert Path(data["saved_path"]).exists()
    assert feedback.LOG_PATH.exists()


def test_feedback_rejects_blank_label(client, tmp_path, monkeypatch) -> None:
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr(feedback, "FEEDBACK_DIR", feedback_dir)
    monkeypatch.setattr(feedback, "LOG_PATH", feedback_dir / "feedback_log.jsonl")

    response = client.post(
        "/api/v1/feedback/training-data",
        files={
            "file": ("food.jpg", b"fake-jpeg-content", "image/jpeg"),
            "correct_dish_name": (None, "   "),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Thiếu correct_dish_name."
