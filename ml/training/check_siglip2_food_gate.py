import torch
from datasets import load_dataset
from huggingface_hub import hf_hub_download
from transformers import AutoImageProcessor, AutoModelForImageClassification
from datasets import DatasetDict
from torch.utils.data import DataLoader
from pathlib import Path

CHECKPOINT = "google/siglip2-base-patch16-224"

id2label = {
    0: "food",
    1: "non_food",
}

label2id = {
    "food": 0,
    "non_food": 1,
}

device = "mps" if torch.backends.mps.is_available() else "cpu"

PARQUET_PATH = hf_hub_download(
    repo_id="avnishs17/food_not_food",
    repo_type="dataset",
    revision="4d0e6d6e731dd26586e303f8c7f37642fb1da1fe",
    filename="default/train/0000.parquet",
    local_files_only=True,
)

dataset = load_dataset(
    "parquet",
    data_files={"train": PARQUET_PATH},
)["train"]

image = dataset[0]["image"].convert("RGB")

processor = AutoImageProcessor.from_pretrained(CHECKPOINT)

model = AutoModelForImageClassification.from_pretrained(
    CHECKPOINT,
    num_labels=2,
    id2label=id2label,
    label2id=label2id,
    ignore_mismatched_sizes=True,
)

model = model.to(device)
model.eval()

inputs = processor(images=image, return_tensors="pt")
inputs = {
    name: value.to(device)
    for name, value in inputs.items()
}

with torch.no_grad():
    outputs = model(**inputs)

print(f"device: {device}")
print(f"logits shape: {outputs.logits.shape}")

train_and_holdout = dataset.train_test_split(
    test_size=0.30,
    seed=42,
    stratify_by_column="label",
)

val_and_test = train_and_holdout["test"].train_test_split(
    test_size=0.50,
    seed=42,
    stratify_by_column="label",
)

splits = DatasetDict(
    {
        "train": train_and_holdout["train"],
        "validation": val_and_test["train"],
        "test": val_and_test["test"],
    }
)


def collate_fn(examples):
    images = [
        example["image"].convert("RGB")
        for example in examples
    ]

    batch = processor(
        images=images,
        return_tensors="pt",
    )

    batch["labels"] = torch.tensor(
        [example["label"] for example in examples],
        dtype=torch.long,
    )

    return batch


train_loader = DataLoader(
    splits["train"],
    batch_size=8,
    shuffle=True,
    num_workers=0,
    collate_fn=collate_fn,
)

batch = next(iter(train_loader))

print(f"pixel_values shape: {batch['pixel_values'].shape}")
print(f"labels: {batch['labels']}")


# for parameter in model.vision_model.parameters():
#     parameter.requires_grad = False

# optimizer = torch.optim.AdamW(
#     model.classifier.parameters(),
#     lr=1e-3,
#     weight_decay=1e-2,
# )

# model.train()

# train_batch = {
#     name: value.to(device)
#     for name, value in batch.items()
# }

# optimizer.zero_grad(set_to_none=True)

# outputs = model(**train_batch)
# loss = outputs.loss

# loss.backward()
# optimizer.step()

# print(f"single train-step loss: {loss.item():.4f}")

for parameter in model.vision_model.parameters():
    parameter.requires_grad = False

optimizer = torch.optim.AdamW(
    model.classifier.parameters(),
    lr=1e-3,
    weight_decay=1e-2,
)

validation_loader = DataLoader(
    splits["validation"],
    batch_size=8,
    shuffle=False,
    num_workers=0,
    collate_fn=collate_fn,
)


def move_to_device(batch):
    return {
        name: value.to(device)
        for name, value in batch.items()
    }


def train_one_epoch():
    model.train()
    model.vision_model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    for step, raw_batch in enumerate(train_loader, start=1):
        train_batch = move_to_device(raw_batch)

        optimizer.zero_grad(set_to_none=True)

        outputs = model(**train_batch)
        loss = outputs.loss

        loss.backward()
        optimizer.step()

        batch_size = train_batch["labels"].size(0)
        total_loss += loss.item() * batch_size

        predictions = outputs.logits.argmax(dim=1)
        correct += (predictions == train_batch["labels"]).sum().item()
        total += batch_size

        if step % 100 == 0:
            print(
                f"train step {step}/{len(train_loader)} "
                f"loss={loss.item():.4f}"
            )

    return total_loss / total, correct / total


def evaluate():
    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for raw_batch in validation_loader:
            validation_batch = move_to_device(raw_batch)

            outputs = model(**validation_batch)
            loss = outputs.loss

            batch_size = validation_batch["labels"].size(0)
            total_loss += loss.item() * batch_size

            predictions = outputs.logits.argmax(dim=1)
            correct += (
                predictions == validation_batch["labels"]
            ).sum().item()
            total += batch_size

    return total_loss / total, correct / total


EPOCHS = 0

checkpoint_path = Path(
    "checkpoints/food_gate/siglip2_food_gate_best.pt"
)
checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

best_val_loss = float("inf")

for epoch in range(1, EPOCHS + 1):
    train_loss, train_accuracy = train_one_epoch()
    val_loss, val_accuracy = evaluate()

    print(f"\nEpoch {epoch}/{EPOCHS}")
    print(f"train loss: {train_loss:.4f}")
    print(f"train accuracy: {train_accuracy:.2%}")
    print(f"validation loss: {val_loss:.4f}")
    print(f"validation accuracy: {val_accuracy:.2%}")

    if val_loss < best_val_loss:
        best_val_loss = val_loss

        torch.save(
            {
                "checkpoint": CHECKPOINT,
                "model_state_dict": model.state_dict(),
                "id2label": id2label,
                "label2id": label2id,
                "epoch": epoch,
                "validation_loss": val_loss,
                "validation_accuracy": val_accuracy,
            },
            checkpoint_path,
        )

        print(f"Đã lưu model tốt nhất: {checkpoint_path}")

test_loader = DataLoader(
    splits["test"],
    batch_size=8,
    shuffle=False,
    num_workers=0,
    collate_fn=collate_fn,
)

checkpoint = torch.load(checkpoint_path, map_location="cpu")
model.load_state_dict(checkpoint["model_state_dict"])
model = model.to(device)


def evaluate_test():
    model.eval()

    total = 0
    correct = 0

    food_total = 0
    food_correct = 0

    non_food_total = 0
    non_food_correct = 0

    food_to_non_food = 0
    non_food_to_food = 0

    food_id = label2id["food"]
    non_food_id = label2id["non_food"]

    with torch.no_grad():
        for raw_batch in test_loader:
            test_batch = move_to_device(raw_batch)

            outputs = model(**test_batch)
            predictions = outputs.logits.argmax(dim=1)
            labels = test_batch["labels"]

            total += labels.size(0)
            correct += (predictions == labels).sum().item()

            food_mask = labels == food_id
            non_food_mask = labels == non_food_id

            food_total += food_mask.sum().item()
            non_food_total += non_food_mask.sum().item()

            food_correct += (
                (predictions == food_id) & food_mask
            ).sum().item()

            non_food_correct += (
                (predictions == non_food_id) & non_food_mask
            ).sum().item()

            food_to_non_food += (
                (predictions == non_food_id) & food_mask
            ).sum().item()

            non_food_to_food += (
                (predictions == food_id) & non_food_mask
            ).sum().item()

    return {
        "accuracy": correct / total,
        "food_recall": food_correct / food_total,
        "non_food_recall": non_food_correct / non_food_total,
        "food_to_non_food": food_to_non_food,
        "non_food_to_food": non_food_to_food,
    }


test_results = evaluate_test()

print("\n=== HELD-OUT TEST RESULTS ===")
print(f"checkpoint epoch: {checkpoint['epoch']}")
print(f"test accuracy: {test_results['accuracy']:.2%}")
print(f"food recall: {test_results['food_recall']:.2%}")
print(f"non-food recall: {test_results['non_food_recall']:.2%}")
print(f"food bị chặn nhầm thành non-food: {test_results['food_to_non_food']}")
print(f"non-food bị lọt thành food: {test_results['non_food_to_food']}")
