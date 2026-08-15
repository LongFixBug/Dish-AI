from pathlib import Path
import csv
import json
import shutil
import sys

import torch
from PIL import Image
from transformers import AutoImageProcessor, SiglipVisionModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.training.siglip_fast_lane import (  # noqa: E402
    build_model,
    load_fast_lane_config,
    resolve_device,
)


CONFIG_PATH = PROJECT_ROOT / "data/config/siglip_food_v1.json"
TEST_DIR = PROJECT_ROOT / "data/images/siglip_food_v1/test"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints/siglip_food_v1"
ENCODER_DIR = CHECKPOINT_DIR / "encoder"
HEAD_PATH = CHECKPOINT_DIR / "classifier_head.pt"
OUTPUT_DIR = CHECKPOINT_DIR / "evaluation"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def collect_test_images(classes: tuple[str, ...]) -> tuple[str, dict[str, float]]:
    pairs = []

    for class_name in classes:
        class_dir = TEST_DIR / class_name

        for image_path in sorted(class_dir.iterdir()):
            if image_path.suffix.lower() in IMAGE_EXTENSIONS:
                pairs.append((class_name, image_path))

    return pairs


def load_model(config, device: str):
    processor = AutoImageProcessor.from_pretrained(ENCODER_DIR)

    model = build_model(config.base_model, len(config.classes))

    model.encoder = SiglipVisionModel.from_pretrained(ENCODER_DIR)

    head_checkpoint = torch.load(
        HEAD_PATH,
        map_location="cpu",
        weights_only=True,
    )

    if tuple(head_checkpoint["classes"]) != config.classes:
        raise ValueError("Class trong checkpoint không khớp config")

    model.classifier.load_state_dict(head_checkpoint["classifier_state_dict"])

    model = model.to(device)
    model.eval()

    return model, processor


def predict_one(
    model,
    processor,
    image_path: Path,
    classes: tuple[str, ...],
    device: str,
) -> tuple[str, float]:
    with Image.open(image_path) as opened_image:
        image = opened_image.convert("RGB")

    inputs = processor(
        images=image,
        return_tensors="pt",
    )

    pixel_values = inputs["pixel_values"].to(device)

    with torch.inference_mode():
        logits, _embedding = model(pixel_values)

        probabilities = torch.softmax(logits, dim=1)[0]

    scores = {
        class_name: probability
        for class_name, probability in zip(
            classes,
            probabilities.detach().cpu().tolist(),
            strict=True,
        )
    }

    predicted_slug = max(
        scores,
        key=scores.get,
    )

    return predicted_slug, scores


def create_confusion_matrix(
    classes: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    return {truth: {predicted: 0 for predicted in classes} for truth in classes}


def main() -> None:
    config = load_fast_lane_config(CONFIG_PATH)

    device = resolve_device(
        "mps",
        mps_available=torch.backends.mps.is_available(),
        cuda_available=torch.cuda.is_available(),
    )

    model, processor = load_model(config, device)

    pairs = collect_test_images(config.classes)
    confusion = create_confusion_matrix(config.classes)
    results = []

    for index, (truth_slug, image_path) in enumerate(pairs, start=1):
        predicted_slug, scores = predict_one(
            model,
            processor,
            image_path,
            config.classes,
            device,
        )

        confusion[truth_slug][predicted_slug] += 1

        results.append(
            {
                "image": str(image_path),
                "truth": truth_slug,
                "predicted": predicted_slug,
                "scores": scores,
                "confidence": scores[predicted_slug],
                "correct": truth_slug == predicted_slug,
            }
        )

        if index % 20 == 0:
            print(f"Đã chấm {index}/{len(pairs)} ảnh")
    for class_name in config.classes:
        total = sum(confusion[class_name].values())
        correct = confusion[class_name][class_name]

        recall = correct / total if total else 0

        print(class_name, total, correct, recall)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "classes": list(config.classes),
        "total_images": len(results),
        "correct": sum(row["correct"] for row in results),
        "confusion": confusion,
        "per_image": results,
    }

    report_path = OUTPUT_DIR / "report.json"

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = OUTPUT_DIR / "confusion_matrix.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(["truth", *config.classes])

        for truth_slug in config.classes:
            row = [
                truth_slug,
                *[confusion[truth_slug][predicted_slug] for predicted_slug in config.classes],
            ]

            writer.writerow(row)

    errors_dir = OUTPUT_DIR / "errors"

    for row in results:
        if row["correct"]:
            continue

        source_path = Path(row["image"])

        target_dir = errors_dir / f"{row['truth']}__predicted_{row['predicted']}"

        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / source_path.name

        shutil.copy2(source_path, target_path)

    print("Đã xong evaluator")
    print(f"Report: {report_path}")
    print(f"Confusion CSV: {csv_path}")
    print(f"Ảnh sai: {errors_dir}")


if __name__ == "__main__":
    main()
