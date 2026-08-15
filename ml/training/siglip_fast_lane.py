"""Fine-tune a SigLIP2 vision encoder for FoodAI's popular-dish fast lane.

This trainer is intentionally separate from ``ml.training.train``.  That file
is the historical EfficientNet classifier; this module keeps the output as a
Hugging Face ``SiglipVisionModel`` so the image sidecar can load the resulting
encoder and produce Qdrant-compatible vectors.

Dataset layout::

    data/images/siglip_fast_lane/
        train/<class_slug>/*.jpg
        val/<class_slug>/*.jpg
        test/<class_slug>/*.jpg

``test`` is optional while iterating, but a release must be evaluated on it.
The runtime reference album remains separate from these training images.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "data" / "config" / "siglip_fast_lane.json"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "images" / "siglip_fast_lane"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "checkpoints" / "siglip_fast_lane"
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

sys.path.insert(0, str(PROJECT_ROOT))

from ml.model_registry import fingerprint_dataset  # noqa: E402


class FastLaneDatasetError(ValueError):
    """Dataset layout or class-contract error that must stop training."""


@dataclass(frozen=True)
class FastLaneConfig:
    """Reproducible hyperparameters for one fast-lane experiment."""

    schema_version: int
    base_model: str
    classes: tuple[str, ...]
    image_size: int = 224
    batch_size: int = 8
    epochs: int = 8
    learning_rate: float = 1e-5
    head_learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    train_last_blocks: int = 2
    seed: int = 42
    num_workers: int = 0


def _positive_int(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _positive_float(payload: dict[str, Any], key: str, default: float) -> float:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return float(value)


def _nonnegative_int(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def load_fast_lane_config(path: str | Path = DEFAULT_CONFIG_PATH) -> FastLaneConfig:
    """Load and validate the versioned fast-lane class contract."""
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read fast-lane config: {config_path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Fast-lane config must use schema_version 1")

    raw_classes = payload.get("classes")
    if (
        not isinstance(raw_classes, list)
        or len(raw_classes) < 2
        or any(not isinstance(name, str) or not name.strip() for name in raw_classes)
    ):
        raise ValueError("Fast-lane config must contain at least two non-empty classes")
    classes = tuple(sorted(name.strip() for name in raw_classes))
    if len(set(classes)) != len(classes):
        raise ValueError("Fast-lane config contains duplicate classes")
    if len(classes) > 32:
        raise ValueError("Fast-lane config should contain at most 32 classes")

    base_model = payload.get("base_model", "google/siglip2-base-patch16-224")
    if not isinstance(base_model, str) or not base_model.strip():
        raise ValueError("base_model must be a non-empty string")

    return FastLaneConfig(
        schema_version=1,
        base_model=base_model.strip(),
        classes=classes,
        image_size=_positive_int(payload, "image_size", 224),
        batch_size=_positive_int(payload, "batch_size", 8),
        epochs=_positive_int(payload, "epochs", 8),
        learning_rate=_positive_float(payload, "learning_rate", 1e-5),
        head_learning_rate=_positive_float(payload, "head_learning_rate", 1e-3),
        weight_decay=_positive_float(payload, "weight_decay", 1e-4),
        train_last_blocks=_positive_int(payload, "train_last_blocks", 2),
        seed=_positive_int(payload, "seed", 42),
        num_workers=_nonnegative_int(payload, "num_workers", 0),
    )


def _image_paths(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _validate_split(
    root: Path,
    split: str,
    classes: tuple[str, ...],
    *,
    optional: bool,
) -> dict[str, int]:
    split_dir = root / split
    if not split_dir.is_dir():
        if optional:
            return {}
        raise FastLaneDatasetError(f"Missing required split directory: {split_dir}")

    present = {path.name for path in split_dir.iterdir() if path.is_dir()}
    if optional and (
        not present
        or not any(_image_paths(split_dir / class_name) for class_name in present)
    ):
        # The scaffold may contain empty class folders before the operator has
        # prepared the independent test set. Treat that state as "not supplied"
        # while still rejecting a partially populated test split below.
        return {}
    unknown = sorted(present - set(classes))
    if unknown:
        raise FastLaneDatasetError(
            f"{split} contains classes outside config: {unknown}"
        )
    missing = sorted(set(classes) - present)
    if missing:
        raise FastLaneDatasetError(f"{split} is missing class folders: {missing}")

    counts: dict[str, int] = {}
    empty = []
    for class_name in classes:
        count = len(_image_paths(split_dir / class_name))
        counts[class_name] = count
        if count == 0:
            empty.append(class_name)
    if empty:
        raise FastLaneDatasetError(f"{split} has no readable image files for: {empty}")
    return counts


def validate_dataset_layout(
    data_dir: str | Path,
    classes: tuple[str, ...] | list[str],
    *,
    require_test: bool = False,
) -> dict[str, dict[str, int]]:
    """Validate train/val and optionally test; return per-class counts."""
    root = Path(data_dir)
    if not root.is_dir():
        raise FastLaneDatasetError(f"Dataset directory does not exist: {root}")
    ordered_classes = tuple(sorted(classes))
    if len(ordered_classes) < 2 or len(set(ordered_classes)) != len(ordered_classes):
        raise FastLaneDatasetError("Dataset class contract must contain unique classes")
    return {
        "train": _validate_split(root, "train", ordered_classes, optional=False),
        "val": _validate_split(root, "val", ordered_classes, optional=False),
        "test": _validate_split(root, "test", ordered_classes, optional=not require_test),
    }


def resolve_device(
    requested: str,
    *,
    mps_available: bool,
    cuda_available: bool,
) -> str:
    """Resolve a stable device string without importing Torch at module import."""
    normalized = requested.strip().lower()
    if normalized not in {"auto", "cpu", "cuda", "mps"}:
        raise ValueError("device must be auto, cpu, cuda, or mps")
    if normalized == "auto":
        if mps_available:
            return "mps"
        if cuda_available:
            return "cuda"
        return "cpu"
    if normalized == "mps" and not mps_available:
        raise ValueError("device=mps but MPS is unavailable")
    if normalized == "cuda" and not cuda_available:
        raise ValueError("device=cuda but CUDA is unavailable")
    return normalized


def set_seed(seed: int) -> None:
    """Seed Python and Torch when the actual training command is invoked."""
    import torch

    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class FastLaneImageDataset:
    """Small ImageFolder-style dataset with SigLIP's processor contract."""

    def __init__(
        self,
        data_dir: str | Path,
        classes: tuple[str, ...],
        split: str,
        processor,
        image_size: int,
    ) -> None:
        from PIL import Image
        from torch.utils.data import Dataset
        from torchvision import transforms

        class _Dataset(Dataset):
            def __init__(self) -> None:
                self.samples: list[tuple[Path, int]] = []
                root = Path(data_dir) / split
                self.transform = transforms.Compose(
                    [
                        transforms.RandomResizedCrop(image_size, scale=(0.75, 1.0)),
                        transforms.RandomHorizontalFlip(p=0.5),
                        transforms.ColorJitter(
                            brightness=0.2,
                            contrast=0.2,
                            saturation=0.2,
                            hue=0.05,
                        ),
                    ]
                    if split == "train"
                    else []
                )
                for label, class_name in enumerate(classes):
                    self.samples.extend(
                        (path, label)
                        for path in _image_paths(root / class_name)
                    )

            def __len__(self) -> int:
                return len(self.samples)

            def __getitem__(self, index: int):
                path, label = self.samples[index]
                try:
                    with Image.open(path) as image:
                        image = image.convert("RGB")
                        image = self.transform(image)
                        pixel_values = processor(
                            images=image,
                            return_tensors="pt",
                        )["pixel_values"][0]
                except (OSError, ValueError) as exc:
                    raise FastLaneDatasetError(f"Cannot read image {path}") from exc
                return pixel_values, label

        self._dataset = _Dataset()

    def __len__(self) -> int:
        return len(self._dataset)

    def __getitem__(self, index: int):
        return self._dataset[index]


def _pool_encoder_output(output, torch):
    pooled = getattr(output, "pooler_output", None)
    if pooled is not None:
        return pooled
    hidden = getattr(output, "last_hidden_state", None)
    if hidden is not None:
        return hidden[:, 0]
    raise RuntimeError("SigLIP encoder output has no pooled or hidden image features")


def build_model(base_model: str, num_classes: int):
    """Load a SigLIP vision encoder and a temporary classification head."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from transformers import SiglipVisionModel

    encoder = SiglipVisionModel.from_pretrained(base_model)
    hidden_size = int(getattr(encoder.config, "hidden_size", 0))
    if hidden_size <= 0:
        raise RuntimeError("SigLIP config has no valid hidden_size")

    class _FastLaneModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = encoder
            self.classifier = nn.Linear(hidden_size, num_classes)

        def forward(self, pixel_values):
            output = self.encoder(pixel_values=pixel_values)
            pooled = _pool_encoder_output(output, torch)
            embedding = F.normalize(pooled, p=2, dim=-1)
            return self.classifier(embedding), embedding

    return _FastLaneModel()


def configure_trainable_layers(model, last_blocks: int) -> int:
    """Freeze most of SigLIP and train the head plus the final encoder blocks."""
    if last_blocks < 1:
        raise ValueError("train_last_blocks must be at least 1")
    for parameter in model.encoder.parameters():
        parameter.requires_grad = False
    for parameter in model.classifier.parameters():
        parameter.requires_grad = True

    encoder_root = getattr(model.encoder, "vision_model", model.encoder)
    layers = getattr(getattr(encoder_root, "encoder", None), "layers", None)
    if layers is None:
        raise RuntimeError("Cannot locate SigLIP vision encoder layers")
    for block in list(layers)[-last_blocks:]:
        for parameter in block.parameters():
            parameter.requires_grad = True
    for name in ("post_layernorm", "layernorm", "post_layer_norm"):
        layer = getattr(encoder_root, name, None)
        if layer is not None:
            for parameter in layer.parameters():
                parameter.requires_grad = True
    return sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )


def _metrics(predictions: list[int], labels: list[int], num_classes: int) -> dict[str, float]:
    """Return accuracy and macro precision/recall/F1 for one split."""
    confusion = [[0] * num_classes for _ in range(num_classes)]
    for actual, predicted in zip(labels, predictions, strict=True):
        confusion[actual][predicted] += 1
    total = sum(sum(row) for row in confusion)
    correct = sum(confusion[i][i] for i in range(num_classes))
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    for index in range(num_classes):
        tp = confusion[index][index]
        predicted_total = sum(row[index] for row in confusion)
        support = sum(confusion[index])
        precision = tp / predicted_total if predicted_total else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    return {
        "accuracy": correct / total if total else 0.0,
        "macro_precision": sum(precisions) / num_classes,
        "macro_recall": sum(recalls) / num_classes,
        "macro_f1": sum(f1s) / num_classes,
    }


def _run_epoch(model, loader, criterion, optimizer, device: str, torch, train: bool) -> dict[str, float]:
    model.train(train)
    total_loss = 0.0
    predictions: list[int] = []
    labels: list[int] = []
    for pixel_values, batch_labels in loader:
        pixel_values = pixel_values.to(device)
        batch_labels = batch_labels.to(device)
        if train:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(train):
            logits, _ = model(pixel_values)
            loss = criterion(logits, batch_labels)
            if train:
                loss.backward()
                optimizer.step()
        total_loss += float(loss.item()) * len(batch_labels)
        predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())
        labels.extend(batch_labels.detach().cpu().tolist())
    metrics = _metrics(predictions, labels, model.classifier.out_features)
    metrics["loss"] = total_loss / max(len(labels), 1)
    return metrics


def train_fast_lane(
    config: FastLaneConfig,
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    device_name: str = "auto",
    require_test: bool = False,
) -> dict[str, Any]:
    """Train, evaluate and save a vector-compatible SigLIP encoder release."""
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoImageProcessor

    data_root = Path(data_dir)
    output_root = Path(output_dir)
    counts = validate_dataset_layout(data_root, config.classes, require_test=require_test)
    set_seed(config.seed)
    device = resolve_device(
        device_name,
        mps_available=torch.backends.mps.is_available(),
        cuda_available=torch.cuda.is_available(),
    )
    processor = AutoImageProcessor.from_pretrained(config.base_model)
    train_ds = FastLaneImageDataset(
        data_root, config.classes, "train", processor, config.image_size
    )
    val_ds = FastLaneImageDataset(
        data_root, config.classes, "val", processor, config.image_size
    )
    model = build_model(config.base_model, len(config.classes)).to(device)
    trainable_params = configure_trainable_layers(model, config.train_last_blocks)
    loader_kwargs = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
        "pin_memory": device == "cuda",
    }
    train_loader = DataLoader(train_ds, shuffle=True, **loader_kwargs)
    val_loader = DataLoader(val_ds, shuffle=False, **loader_kwargs)
    encoder_params = [
        p for p in model.encoder.parameters() if p.requires_grad
    ]
    optimizer = torch.optim.AdamW(
        [
            {"params": encoder_params, "lr": config.learning_rate},
            {"params": model.classifier.parameters(), "lr": config.head_learning_rate},
        ],
        weight_decay=config.weight_decay,
    )
    criterion = torch.nn.CrossEntropyLoss()
    best_key = (-1.0, -1.0)
    best_state: dict[str, Any] | None = None
    best_val_metrics: dict[str, float] = {}
    history: list[dict[str, Any]] = []
    for epoch in range(1, config.epochs + 1):
        train_metrics = _run_epoch(model, train_loader, criterion, optimizer, device, torch, True)
        val_metrics = _run_epoch(model, val_loader, criterion, optimizer, device, torch, False)
        history.append({"epoch": epoch, "train": train_metrics, "val": val_metrics})
        key = (val_metrics["macro_f1"], val_metrics["accuracy"])
        if key > best_key:
            best_key = key
            best_val_metrics = dict(val_metrics)
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
    if best_state is None:
        raise RuntimeError("Fast-lane training produced no checkpoint")
    model.load_state_dict(best_state)

    test_metrics: dict[str, float] | None = None
    if counts["test"]:
        test_ds = FastLaneImageDataset(
            data_root, config.classes, "test", processor, config.image_size
        )
        test_loader = DataLoader(test_ds, shuffle=False, **loader_kwargs)
        test_metrics = _run_epoch(
            model,
            test_loader,
            criterion,
            optimizer,
            device,
            torch,
            False,
        )

    output_root.mkdir(parents=True, exist_ok=True)
    encoder_dir = output_root / "encoder"
    model.encoder.save_pretrained(encoder_dir)
    processor.save_pretrained(encoder_dir)
    torch.save(
        {"classes": list(config.classes), "classifier_state_dict": model.classifier.state_dict()},
        output_root / "classifier_head.pt",
    )
    manifest = {
        "schema_version": 1,
        "model_type": "siglip2_fast_lane_vision_encoder",
        "base_model": config.base_model,
        "encoder_dir": str(encoder_dir),
        "classes": list(config.classes),
        "embedding_dim": int(model.encoder.config.hidden_size),
        "data_dir": str(data_root),
        "dataset_fingerprint": fingerprint_dataset(data_root),
        "counts": counts,
        "trainable_parameters": trainable_params,
        "config": asdict(config),
        "history": history,
        "best_val": best_val_metrics,
        "test": test_metrics,
        "test_evaluated": test_metrics is not None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda", "mps"))
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument(
        "--require-test",
        action="store_true",
        help="Require a complete held-out test split before training.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        config = load_fast_lane_config(args.config)
        if args.epochs is not None:
            if args.epochs < 1:
                raise ValueError("--epochs must be a positive integer")
            config = replace(config, epochs=args.epochs)
        if args.batch_size is not None:
            if args.batch_size < 1:
                raise ValueError("--batch-size must be a positive integer")
            config = replace(config, batch_size=args.batch_size)
        manifest = train_fast_lane(
            config,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            device_name=args.device,
            require_test=args.require_test,
        )
    except (FastLaneDatasetError, FileNotFoundError, ValueError) as exc:
        print(f"❌ Fast-lane setup/training chưa sẵn sàng: {exc}")
        raise SystemExit(2) from exc
    print(json.dumps({"output_dir": args.output_dir, "manifest": manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
