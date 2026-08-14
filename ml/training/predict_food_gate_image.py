import sys
from pathlib import Path

import torch
from PIL import Image
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
)
#check % image choose wrong ans

CHECKPOINT_PATH = Path(
    "checkpoints/food_gate/siglip2_food_gate_best.pt"
)

device = "mps" if torch.backends.mps.is_available() else "cpu"

if len(sys.argv) != 2:
    raise ValueError("Cách dùng: uv run python ... <đường_dẫn_ảnh>")

image_path = Path(sys.argv[1])

if not image_path.exists():
    raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")

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
food_probability = probabilities[
    checkpoint["label2id"]["food"]
].item()
non_food_probability = probabilities[
    checkpoint["label2id"]["non_food"]
].item()

print(f"food: {food_probability:.2%}")
print(f"non_food: {non_food_probability:.2%}")