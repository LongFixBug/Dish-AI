"""Split feedback images into train/val folders for CV training.

Reads data/images/feedback/feedback_log.jsonl, copies images into:
    data/images/train/<dish_name>/
    data/images/val/<dish_name>/

Split ratio: 80% train, 20% val (stratified by class).
Skips files that no longer exist or already present in train/val.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


FEEDBACK_LOG = Path("data/images/feedback/feedback_log.jsonl")
FEEDBACK_DIR = Path("data/images/feedback")
TRAIN_DIR = Path("data/images/train")
VAL_DIR = Path("data/images/val")
TRAIN_RATIO = 0.8


def _snake_case(name: str) -> str:
    """Convert dish name to snake_case folder name."""
    return (
        name.lower()
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
    )


def main() -> None:
    if not FEEDBACK_LOG.exists():
        print(f"❌ Feedback log not found: {FEEDBACK_LOG}")
        return

    # Read log entries
    entries: list[dict] = []
    with open(FEEDBACK_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("⚠️ No feedback entries found.")
        return

    # Group by class
    by_class: dict[str, list[Path]] = {}
    for entry in entries:
        filename = entry.get("filename")
        dish_name = entry.get("dish_name") or entry.get("correct_dish_name")
        if not filename or not dish_name:
            continue

        # Try direct path first, then any nested folder
        src = FEEDBACK_DIR / filename
        if not src.exists():
            candidates = list(FEEDBACK_DIR.rglob(filename))
            if not candidates:
                print(f"⚠️ File not found, skipping: {filename}")
                continue
            src = candidates[0]

        class_name = _snake_case(dish_name)
        by_class.setdefault(class_name, []).append(src)

    # Copy with 80/20 split
    copied_train = 0
    copied_val = 0
    for class_name, files in sorted(by_class.items()):
        files = sorted(set(files))
        split_idx = max(1, int(len(files) * TRAIN_RATIO)) if len(files) >= 2 else len(files)
        train_files = files[:split_idx]
        val_files = files[split_idx:]
        if not val_files and len(train_files) >= 2:
            # Ensure at least 1 validation sample when possible
            val_files = [train_files[-1]]
            train_files = train_files[:-1]

        train_class_dir = TRAIN_DIR / class_name
        val_class_dir = VAL_DIR / class_name
        train_class_dir.mkdir(parents=True, exist_ok=True)
        val_class_dir.mkdir(parents=True, exist_ok=True)

        for src in train_files:
            dst = train_class_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied_train += 1

        for src in val_files:
            dst = val_class_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied_val += 1

        print(
            f"📁 {class_name}: {len(train_files)} train, {len(val_files)} val"
        )

    print(f"\n✅ Copied {copied_train} images to train, {copied_val} to val.")


if __name__ == "__main__":
    main()
