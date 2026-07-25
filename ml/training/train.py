"""Training script cho VietFood CV model.

Fine-tune EfficientNet-B0 (timm) pretrained ImageNet → phân loại món Việt.
Full fine-tune (không freeze backbone) với lr nhỏ 5e-5 — tốt cho food
(texture/quang cảnh quan trọng, không chỉ shape).

Usage:
    python -m ml.training.train                                  # train ảnh raw
    python -m ml.training.train --ckpt checkpoints/xxx.pth --resume
    python -m ml.training.train --no-class-weight                  # baseline

Yêu cầu: ảnh đã được tổ chức trong <data_dir>/{train,val}/<ten_mon>/
(mặc định data/images).
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import timm
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Thêm project root vào path (chạy từ thư mục gốc FoodAI)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.training.dataset import VietFoodDataset  # noqa: E402
from ml.model_registry import (  # noqa: E402
    build_manifest,
    evaluate_quality_gate,
    fingerprint_dataset,
    write_manifest,
)


# ─── Config ──────────────────────────────────────────────────────────
ARCH = "efficientnet_b0"  # timm model name (B0: 5.3M params, input 224)
BATCH_SIZE = 16
NUM_EPOCHS = 18
LEARNING_RATE = 5e-5  # nhỏ hơn ResNet 1e-4 — full fine-tune
IMAGE_SIZE = 224
NUM_WORKERS = 2
# Mặc định BẬT class_weight — cân bằng loss khi số ảnh/class chênh lệch.
# --no-class-weight để tắt (VD khi đã cân bằng data hoặc muốn so sánh baseline).
USE_CLASS_WEIGHT = True
RANDOM_SEED = 42

DATA_DIR = PROJECT_ROOT / "data" / "images"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)
BEST_CHECKPOINT_PATH = CHECKPOINT_DIR / "best_model.pth"
BEST_MANIFEST_PATH = CHECKPOINT_DIR / "best_model.manifest.json"

DEVICE = torch.device(
    "mps" if torch.backends.mps.is_available()
    else "cuda" if torch.cuda.is_available()
    else "cpu"
)


def set_reproducible_seed(seed: int = RANDOM_SEED) -> None:
    """Seed Python and Torch so repeated runs start from the same random state."""
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _class_folders(data_dir: Path, split: str) -> list[str]:
    split_dir = data_dir / split
    if not split_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục {split_dir}.")
    return sorted(path.name for path in split_dir.iterdir() if path.is_dir())


def load_training_datasets(
    data_dir: str | Path,
) -> tuple[VietFoodDataset, VietFoodDataset]:
    """Load train/val with one shared class mapping and reject split drift."""
    root = Path(data_dir)
    train_classes = _class_folders(root, "train")
    val_classes = _class_folders(root, "val")
    if train_classes != val_classes:
        raise ValueError(
            "Validation class folders must exactly match train class folders: "
            f"train={train_classes}, val={val_classes}"
        )
    train_ds = VietFoodDataset(root, classes=train_classes, split="train")
    val_ds = VietFoodDataset(root, classes=train_classes, split="val")
    empty_val_classes = [
        name
        for name, count in zip(train_classes, val_ds.class_counts(), strict=True)
        if count == 0
    ]
    if empty_val_classes:
        raise ValueError(
            f"Validation classes without images: {empty_val_classes}"
        )
    return train_ds, val_ds


def find_latest_checkpoint() -> Path | None:
    """Tìm checkpoint efficientnet mới nhất trong checkpoints/.

    Sắp theo tên file (timestamp dẫn adelante), file cuối = mới nhất gần đúng.
    Ưu tiên: dùng --ckpt <path> để resume chính xác, tránh đoán sai.
    """
    files = sorted(CHECKPOINT_DIR.glob("efficientnet_vietfood_*.pth"))
    return files[-1] if files else None


def load_checkpoint(checkpoint_path: Path) -> dict:
    """Load checkpoint với đầy đủ state."""
    return torch.load(checkpoint_path, map_location=DEVICE, weights_only=True)


def create_model(num_classes: int, checkpoint: dict | None = None) -> nn.Module:
    """Tạo EfficientNet-B0 pretrained (timm) + classifier head cho num_classes.

    Nếu checkpoint được cung cấp, load weights và classes từ checkpoint.
    Nếu num_classes khác với checkpoint, classifier head được reset.
    """
    if checkpoint:
        saved_classes = checkpoint.get("classes", [])
        saved_num_classes = len(saved_classes)

        model = timm.create_model(
            ARCH, pretrained=False, num_classes=saved_num_classes, drop_rate=0.3
        )
        # strict=False để resume linh hoạt khi đổi ARCH/số class. Báo mismatch
        # key ra để biết backbone có load đủ không (classifier reset có chủ ý
        # nên không đáng lo — chỉ lo khi backbone features.* bị thiếu).
        result = model.load_state_dict(
            checkpoint["model_state_dict"], strict=False
        )
        _report_load_mismatch(result, stage="resume")

        if num_classes != saved_num_classes:
            print(
                f"⚠️ Class count changed: {saved_num_classes} -> {num_classes}. "
                "Resetting classifier head."
            )
            model.reset_classifier(num_classes)
    else:
        model = timm.create_model(
            ARCH, pretrained=True, num_classes=num_classes, drop_rate=0.3
        )
    return model


def _report_load_mismatch(result, stage: str = "load") -> None:
    """In missing/unexpected keys sau load_state_dict(strict=False).

    Lọc riêng 'classifier' vì head reset có chủ ý khi đổi số class — chỉ đáng
    lo khi backbone (features., blocks.) bị thiếu/thừa.
    """
    missing = list(result.missing_keys)
    unexpected = list(result.unexpected_keys)

    def _backbone(keys):
        return [k for k in keys if "classifier" not in k]

    miss_bb = _backbone(missing)
    unexp_bb = _backbone(unexpected)

    print(
        f"   [{stage}] missing={len(missing)} (backbone {len(miss_bb)}), "
        f"unexpected={len(unexpected)} (backbone {len(unexp_bb)})"
    )
    if miss_bb:
        print(f"   ⚠️ Backbone mất {len(miss_bb)} key — có thể ARCH lệch checkpoint.")
        print(f"      VD: {miss_bb[:3]}")
    if unexp_bb:
        print(f"   ⚠️ Checkpoint có {len(unexp_bb)} key backbone dư — không nạp vào model.")
        print(f"      VD: {unexp_bb[:3]}")


def compute_class_weights(counts: list[int]) -> torch.Tensor:
    """Tính class_weight cho CrossEntropyLoss (sklearn-style).

    weight[c] = total_samples / (num_classes * count[c]).

    Class ít ảnh → weight cao → sai bị phạt nặng hơn → ép model học lớp thiểu số,
    tránh "accuracy paradox" (acc tổng cao nhưng lớp thiểu số near-random).
    VD: counts=[200, 20] → weights ≈ [0.49, 4.95] (lớp 20 ảnh phạt gấp 10x).
    """
    total = sum(counts)
    n_classes = len(counts)
    weights = torch.tensor(
        [total / (n_classes * max(c, 1)) for c in counts],
        dtype=torch.float32,
    )
    return weights


def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
) -> tuple[float, float]:
    """Train 1 epoch.

    Returns:
        (avg_loss, accuracy).
    """
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (images, labels) in enumerate(loader):
        images, labels = images.to(DEVICE), labels.to(DEVICE)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

        if batch_idx % 10 == 0:
            current_acc = 100.0 * correct / total
            print(
                f"  Batch {batch_idx}/{len(loader)} | "
                f"Loss: {loss.item():.4f} | Acc: {current_acc:.1f}%"
            )

    avg_loss = total_loss / len(loader)
    accuracy = 100.0 * correct / total
    return avg_loss, accuracy


def compute_classification_metrics(
    confusion_matrix: list[list[int]],
    classes: list[str],
) -> dict[str, object]:
    """Calculate macro metrics from a true-row/predicted-column confusion matrix."""
    if len(confusion_matrix) != len(classes) or any(
        len(row) != len(classes) for row in confusion_matrix
    ):
        raise ValueError("Confusion matrix shape must match the class list")

    total = sum(sum(row) for row in confusion_matrix)
    correct = sum(confusion_matrix[index][index] for index in range(len(classes)))
    per_class: dict[str, dict[str, float | int]] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []

    for index, class_name in enumerate(classes):
        true_positive = confusion_matrix[index][index]
        support = sum(confusion_matrix[index])
        predicted_total = sum(row[index] for row in confusion_matrix)
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall > 0
            else 0.0
        )
        if support > 0:
            precisions.append(precision)
            recalls.append(recall)
            f1_scores.append(f1)
        per_class[class_name] = {
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "f1": round(f1 * 100, 2),
            "support": support,
        }

    def _macro(values: list[float]) -> float:
        return round(100 * sum(values) / len(values), 2) if values else 0.0

    return {
        "accuracy": round(100 * correct / total, 2) if total else 0.0,
        "macro_precision": _macro(precisions),
        "macro_recall": _macro(recalls),
        "macro_f1": _macro(f1_scores),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
    }


def compute_calibration_metrics(
    confidences: list[float],
    correctness: list[bool],
    *,
    target_accuracy: float = 0.85,
    bins: int = 10,
) -> dict[str, float]:
    """Calculate ECE and the widest high-confidence operating region."""
    if len(confidences) != len(correctness) or not confidences:
        return {
            "ece": 1.0,
            "recommended_threshold": 1.0,
            "selective_accuracy": 0.0,
            "selective_coverage": 0.0,
        }
    total = len(confidences)
    ece = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [
            item
            for item, confidence in enumerate(confidences)
            if lower <= confidence < upper or (index == bins - 1 and confidence == 1)
        ]
        if not selected:
            continue
        accuracy = sum(correctness[item] for item in selected) / len(selected)
        average_confidence = sum(confidences[item] for item in selected) / len(selected)
        ece += len(selected) / total * abs(accuracy - average_confidence)

    best = (1.0, 0.0, 0.0)
    for threshold in sorted(set(confidences)):
        selected = [
            item for item, confidence in enumerate(confidences)
            if confidence >= threshold
        ]
        accuracy = sum(correctness[item] for item in selected) / len(selected)
        coverage = len(selected) / total
        if accuracy >= target_accuracy and coverage > best[2]:
            best = (threshold, accuracy, coverage)
    return {
        "ece": round(ece, 4),
        "recommended_threshold": round(best[0], 4),
        "selective_accuracy": round(best[1] * 100, 2),
        "selective_coverage": round(best[2], 4),
    }


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    classes: list[str] | None = None,
) -> tuple[float, float, dict[int, float], dict[str, object]]:
    """Evaluate model trên validation/test set.

    Returns:
        (avg_loss, accuracy, per_class_acc, classification_metrics).
        per_class_acc: {class_idx: accuracy%} — bóc trần lớp thiểu số yếu,
        acc tổng che giấu được.
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    # Confusion theo class: đúng/sai mỗi class
    n_classes = len(classes) if classes else 0
    per_class_correct = [0] * n_classes
    per_class_total = [0] * n_classes
    confusion_matrix = [[0] * n_classes for _ in range(n_classes)]
    confidences: list[float] = []
    correctness: list[bool] = []

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item()
        probabilities = torch.softmax(outputs, dim=1)
        batch_confidences, predicted = probabilities.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        confidences.extend(float(value) for value in batch_confidences.tolist())
        correctness.extend(
            bool(value) for value in predicted.eq(labels).tolist()
        )

        if n_classes:
            for true_c, pred_c in zip(labels.tolist(), predicted.tolist()):
                per_class_total[true_c] += 1
                confusion_matrix[true_c][pred_c] += 1
                if true_c == pred_c:
                    per_class_correct[true_c] += 1

    avg_loss = total_loss / len(loader)
    accuracy = 100.0 * correct / total
    per_class_acc = {}
    for c in range(n_classes):
        if per_class_total[c] > 0:
            per_class_acc[c] = 100.0 * per_class_correct[c] / per_class_total[c]
    metrics = compute_classification_metrics(confusion_matrix, classes or [])
    metrics.update(compute_calibration_metrics(confidences, correctness))
    return avg_loss, accuracy, per_class_acc, metrics


def _format_per_class(classes: list[str], per_class_acc: dict[int, float]) -> str:
    """Định dạng bảng per-class accuracy, sắp xếp theo acc tăng dần."""
    rows = []
    for idx, name in enumerate(classes):
        acc = per_class_acc.get(idx)
        if acc is None:
            rows.append((name.replace("_", " ").title(), float("nan")))
        else:
            rows.append((name.replace("_", " ").title(), acc))
    rows.sort(key=lambda r: (r[1] != r[1], r[1]))  # NaN xếp cuối
    lines = [f"   {'class':<16} {'acc':>6}"]
    for name, acc in rows:
        lines.append(f"   {name:<16} {acc:>5.1f}%" if acc == acc else f"   {name:<16}   n/a")
    return "\n".join(lines)


def main(
    resume: bool = False,
    ckpt: str | None = None,
    data_dir: str | None = None,
    *,
    use_class_weight: bool = USE_CLASS_WEIGHT,
    seed: int = RANDOM_SEED,
) -> None:
    global DATA_DIR
    if data_dir:
        DATA_DIR = Path(data_dir)
        if not DATA_DIR.is_absolute():
            DATA_DIR = PROJECT_ROOT / DATA_DIR
    set_reproducible_seed(seed)
    print(f"🔥 Device: {DEVICE}")
    print(f"📂 Data: {DATA_DIR}")
    print(f"🎲 Seed: {seed}")
    print()

    # ── Load datasets ────────────────────────────────────────────────
    print("📦 Loading datasets...")
    try:
        train_ds, val_ds = load_training_datasets(DATA_DIR)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ {e}")
        print("\n💡 Tạo cấu trúc thư mục mẫu trước khi train:")
        print("   mkdir -p data/images/train/pho_bo")
        print("   mkdir -p data/images/val/pho_bo")
        print("   # Thêm ảnh vào thư mục tương ứng")
        return

    print(f"   Classes ({train_ds.num_classes}): {train_ds.classes}")
    print(f"   Train samples: {len(train_ds)}")
    print(f"   Val samples: {len(val_ds)}")

    if train_ds.num_classes < 2:
        print("\n❌ Cần ít nhất 2 class để train. Hiện tại mới có 1 class.")
        return

    train_generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(
        train_ds,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        generator=train_generator,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
    )

    # ── Model ────────────────────────────────────────────────────────
    checkpoint = None
    start_epoch = 1
    best_val_acc = 0.0
    history: list[dict] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_fingerprint = fingerprint_dataset(DATA_DIR)

    print(f"\n🧠 Creating model ({ARCH}, {train_ds.num_classes} classes)...")
    # Ưu tiên --ckpt explicit; nếu không thì mới đoán latest (giới hạn).
    if ckpt:
        checkpoint_path = Path(ckpt)
        if not checkpoint_path.is_absolute():
            checkpoint_path = CHECKPOINT_DIR / checkpoint_path
    elif resume:
        checkpoint_path = find_latest_checkpoint()
    else:
        checkpoint_path = None
    if checkpoint_path and checkpoint_path.exists():
        print(f"🔁 Resuming from checkpoint: {checkpoint_path.name}")
        checkpoint = load_checkpoint(checkpoint_path)
        start_epoch = checkpoint.get("epoch", 0) + 1
        best_val_acc = checkpoint.get("val_acc", 0.0)
        history = checkpoint.get("history", [])
    elif ckpt:
        print(f"❌ Không tìm thấy --ckpt: {checkpoint_path}")
        return

    model = create_model(train_ds.num_classes, checkpoint)
    model = model.to(DEVICE)
    print(f"   Total params: {sum(p.numel() for p in model.parameters()):,}")
    print(f"   Trainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    criterion = nn.CrossEntropyLoss()
    if use_class_weight:
        # Cân bằng loss khi số ảnh/class chênh lệch — tránh "accuracy paradox"
        # (acc tổng cao nhưng lớp thiểu số near-random).
        class_weights = compute_class_weights(train_ds.class_counts()).to(DEVICE)
        print(f"   Class weights: {[round(w, 3) for w in class_weights.tolist()]}")
        criterion = nn.CrossEntropyLoss(weight=class_weights)
    else:
        print("   Class weight: OFF (baseline)")
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    if checkpoint and "optimizer_state_dict" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=NUM_EPOCHS
    )
    if checkpoint and "scheduler_state_dict" in checkpoint:
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])

    # Total epochs is fixed; resume continues until NUM_EPOCHS is reached.
    end_epoch = NUM_EPOCHS
    if start_epoch > end_epoch:
        print(f"\n⚠️ Checkpoint already at epoch {start_epoch - 1}, "
              f"which is >= target {NUM_EPOCHS}. Nothing to train.")
        return

    print(f"\n🚀 Starting training (epochs {start_epoch} → {end_epoch}, "
          f"total {end_epoch - start_epoch + 1} new epochs)...")
    print("-" * 60)

    for epoch in range(start_epoch, end_epoch + 1):
        print(f"\n📅 Epoch {epoch}/{end_epoch}")
        print(f"   LR: {scheduler.get_last_lr()[0]:.2e}")

        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, epoch
        )
        print(f"   ✅ Train  — Loss: {train_loss:.4f} | Acc: {train_acc:.1f}%")

        # Validate (kèm per-class acc — bóc trần lớp thiểu số yếu)
        val_loss, val_acc, per_class_acc, classification_metrics = evaluate(
            model, val_loader, criterion, classes=train_ds.classes
        )
        print(f"   📊 Val    — Loss: {val_loss:.4f} | Acc: {val_acc:.1f}%")
        print(
            "   Macro  — "
            f"P: {classification_metrics['macro_precision']:.2f}% | "
            f"R: {classification_metrics['macro_recall']:.2f}% | "
            f"F1: {classification_metrics['macro_f1']:.2f}%"
        )
        print("   Per-class accuracy (thấp lên đầu — xem model yếu chỗ nào):")
        print(_format_per_class(train_ds.classes, per_class_acc))

        scheduler.step()

        # Tìm lớp yếu nhất (acc thấp nhất) để lưu vào history — theo dõi xu hướng
        valid_accs = [a for a in per_class_acc.values()]
        worst = min(valid_accs) if valid_accs else None

        # Save history
        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 2),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 2),
            "val_macro_precision": classification_metrics["macro_precision"],
            "val_macro_recall": classification_metrics["macro_recall"],
            "val_macro_f1": classification_metrics["macro_f1"],
            "val_confusion_matrix": classification_metrics["confusion_matrix"],
            "val_worst_class_acc": round(worst, 2) if worst is not None else None,
            "val_per_class_acc": {
                train_ds.classes[c]: round(a, 2)
                for c, a in per_class_acc.items()
            },
        })

        # Save best model
        if val_acc > best_val_acc:
            model_version = f"{timestamp}-e{epoch}"
            quality_metrics = {
                "accuracy": round(val_acc, 2),
                "macro_f1": float(classification_metrics["macro_f1"]),
                "worst_class_accuracy": round(worst or 0.0, 2),
                "ece": float(classification_metrics["ece"]),
                "selective_accuracy": float(
                    classification_metrics["selective_accuracy"]
                ),
                "selective_coverage": float(
                    classification_metrics["selective_coverage"]
                ),
            }
            confidence_threshold = float(
                classification_metrics["recommended_threshold"]
            )

            checkpoint_data = {
                "epoch": epoch,
                "arch": ARCH,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "val_acc": val_acc,
                "classes": train_ds.classes,
                "history": history,
                "model_version": model_version,
                "cv_confidence_threshold": confidence_threshold,
                "quality_metrics": quality_metrics,
            }

            # Giữ lại checkpoint theo epoch để debug hoặc so sánh sau này.
            epoch_checkpoint_path = (
                CHECKPOINT_DIR / f"efficientnet_vietfood_{timestamp}_epoch{epoch}.pth"
            )
            torch.save(checkpoint_data, epoch_checkpoint_path)

            print(f"   💾 Best model saved: {epoch_checkpoint_path.name}")
            gate = evaluate_quality_gate(
                quality_metrics,
                evaluation_split="validation",
            )
            if gate.passed:
                best_val_acc = val_acc
                torch.save(checkpoint_data, BEST_CHECKPOINT_PATH)
                manifest = build_manifest(
                    BEST_CHECKPOINT_PATH,
                    model_version=model_version,
                    arch=ARCH,
                    classes=train_ds.classes,
                    metrics=quality_metrics,
                    confidence_threshold=confidence_threshold,
                    dataset_fingerprint=dataset_fingerprint,
                    evaluation_split="validation",
                )
                write_manifest(BEST_MANIFEST_PATH, manifest)
                print(f"   ⭐ Serving model updated: {BEST_CHECKPOINT_PATH.name}")
            else:
                print(f"   ⛔ Not promoted: {gate.failures}")

    # Save class mapping
    mapping_path = CHECKPOINT_DIR / "class_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump({
            "classes": train_ds.classes,
            "num_classes": train_ds.num_classes,
        }, f, indent=2, ensure_ascii=False)
    print(f"📋 Class mapping saved: {mapping_path}")

    # Save training history
    history_path = CHECKPOINT_DIR / f"history_{timestamp}.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"📈 History saved: {history_path}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without executing training, so options are testable."""
    parser = argparse.ArgumentParser(description="Train VietFood CV model")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume/fine-tune from the latest checkpoint",
    )
    parser.add_argument(
        "--ckpt",
        type=str,
        default=None,
        help="Đường dẫn checkpoint cụ thể (tên file hoặc path) — ưu tiên hơn --resume đoán",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Thư mục data gốc (chứa train/val) — mặc định data/images.",
    )
    parser.add_argument(
        "--no-class-weight",
        action="store_true",
        help="Tắt class_weight (mặc định bật) — dùng khi data đã cân bằng "
        "hoặc muốn so sánh baseline.",
    )
    return parser


def run_from_args(args: argparse.Namespace) -> None:
    """Translate CLI flags into explicit main arguments."""
    main(
        resume=args.resume,
        ckpt=args.ckpt,
        data_dir=args.data_dir,
        use_class_weight=not args.no_class_weight,
    )


if __name__ == "__main__":
    run_from_args(build_parser().parse_args())
