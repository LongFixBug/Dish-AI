from pathlib import Path

import torch
from PIL import Image
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
)

REAL_EVAL_ROOT = Path("data/images/food_gate_real_eval")
CHECKPOINT_PATH = Path(
    "checkpoints/food_gate/siglip2_food_gate_best.pt"
)
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

device = "mps" if torch.backends.mps.is_available() else "cpu"


def list_images(folder):
    return sorted(
        path
        for path in folder.iterdir()
        if path.suffix.lower() in VALID_EXTENSIONS
    )


food_paths = list_images(REAL_EVAL_ROOT / "food")
non_food_paths = list_images(REAL_EVAL_ROOT / "non_food")

if len(food_paths) != 10 or len(non_food_paths) != 10:
    raise ValueError(
        "Cần đúng 10 ảnh food và 10 ảnh non_food trước khi chấm."
    )

checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu")

processor = AutoImageProcessor.from_pretrained(
    checkpoint["checkpoint"]
)

model = AutoModelForImageClassification.from_pretrained(
    checkpoint["checkpoint"],
    num_labels=2,
    id2label=checkpoint["id2label"],
    label2id=checkpoint["label2id"],
    ignore_mismatched_sizes=True,
)

model.load_state_dict(checkpoint["model_state_dict"])
model = model.to(device)
model.eval()

label2id = checkpoint["label2id"]
id2label = checkpoint["id2label"]

correct = 0
total = 0
food_correct = 0
non_food_correct = 0
mistakes = []
confidence_rows = []

for expected_label, image_paths in {
    "food": food_paths,
    "non_food": non_food_paths,
}.items():
    for image_path in image_paths:
        with Image.open(image_path) as opened_image:
            image = opened_image.convert("RGB")

        inputs = processor(images=image, return_tensors="pt")
        inputs = {
            name: value.to(device)
            for name, value in inputs.items()
        }

        with torch.no_grad():
            outputs = model(**inputs)

        probabilities = torch.softmax(outputs.logits, dim=1)[0]
        food_score = probabilities[label2id["food"]].item()
        non_food_score = probabilities[label2id["non_food"]].item()

        prediction_id = outputs.logits.argmax(dim=1).item()
        prediction_label = id2label[prediction_id]

        confidence_rows.append(
            {
                "image": image_path.name,
                "expected": expected_label,
                "predicted": prediction_label,
                "food_score": food_score,
                "non_food_score": non_food_score,
            }
        )

        total += 1

        if prediction_label == expected_label:
            correct += 1

            if expected_label == "food":
                food_correct += 1
            else:
                non_food_correct += 1
        else:
            mistakes.append(
                f"{image_path.name}: "
                f"thật={expected_label}, đoán={prediction_label}"
            )

print("\n=== REAL-WORLD SMOKE TEST ===")
print(f"checkpoint epoch: {checkpoint['epoch']}")
print(f"accuracy: {correct / total:.2%}")
print(f"food recall: {food_correct / len(food_paths):.2%}")
print(
    f"non-food recall: "
    f"{non_food_correct / len(non_food_paths):.2%}"
)
print("\n=== ĐIỂM TỪNG ẢNH ===")

for row in sorted(
    confidence_rows,
    key=lambda row: row["non_food_score"],
    reverse=True,
):
    print(
        f"{row['expected']:8} | "
        f"food={row['food_score']:.2%} | "
        f"non_food={row['non_food_score']:.2%} | "
        f"{row['image']}"
    )
if mistakes:
    print("\nẢnh đoán sai:")
    for mistake in mistakes:
        print(f"- {mistake}")
else:
    print("\nKhông có ảnh nào đoán sai.")