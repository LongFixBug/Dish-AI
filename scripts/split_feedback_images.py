"""Deprecated compatibility entry point for the old feedback splitter.

The old JSONL flow could copy an unreviewed or non-consented upload into the
training set.  Camera feedback must now go through the database review gate:
``scripts/export_camera_feedback_dataset.py``.
"""

from __future__ import annotations


def main() -> None:
    print(
        "❌ Script cũ đã bị vô hiệu hóa để tránh train ảnh chưa consent/review.\n"
        "   Dùng: uv run python scripts/export_camera_feedback_dataset.py\n"
        "   Sau khi manifest ready=true, dùng prepare_camera_retrain_dataset.py."
    )


if __name__ == "__main__":
    main()
