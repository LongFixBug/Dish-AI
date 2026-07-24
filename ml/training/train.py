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

DATA_DIR = PROJECT_ROOT / "data" / "images"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)
BEST_CHECKPOINT_PATH = CHECKPOINT_DIR / "best_model.pth"

DEVICE = torch.device(
    "mps" if torch.backends.mps.is_available()
    else "cuda" if torch.cuda.is_available()
    else "cpu"
)


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


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    classes: list[str] | None = None,
) -> tuple[float, float, dict[int, float]]:
    """Evaluate model trên validation/test set.

    Returns:
        (avg_loss, accuracy, per_class_acc).
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

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

        if n_classes:
            for true_c, pred_c in zip(labels.tolist(), predicted.tolist()):
                per_class_total[true_c] += 1
                if true_c == pred_c:
                    per_class_correct[true_c] += 1

    avg_loss = total_loss / len(loader)
    accuracy = 100.0 * correct / total
    per_class_acc = {}
    for c in range(n_classes):
        if per_class_total[c] > 0:
            per_class_acc[c] = 100.0 * per_class_correct[c] / per_class_total[c]
    return avg_loss, accuracy, per_class_acc


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


def main(resume: bool = False, ckpt: str | None = None, data_dir: str | None = None) -> None:
    global DATA_DIR
    if data_dir:
        DATA_DIR = Path(data_dir)
        if not DATA_DIR.is_absolute():
            DATA_DIR = PROJECT_ROOT / DATA_DIR
    print(f"🔥 Device: {DEVICE}")
    print(f"📂 Data: {DATA_DIR}")
    print()

    # ── Load datasets ────────────────────────────────────────────────
    print("📦 Loading datasets...")
    try:
        train_ds = VietFoodDataset(DATA_DIR, split="train")
        val_ds = VietFoodDataset(DATA_DIR, split="val")
    except FileNotFoundError as e:
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

    train_loader = DataLoader(
        train_ds,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
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
    if USE_CLASS_WEIGHT:
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
        val_loss, val_acc, per_class_acc = evaluate(
            model, val_loader, criterion, classes=train_ds.classes
        )
        print(f"   📊 Val    — Loss: {val_loss:.4f} | Acc: {val_acc:.1f}%")
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
            "val_worst_class_acc": round(worst, 2) if worst is not None else None,
            "val_per_class_acc": {
                train_ds.classes[c]: round(a, 2)
                for c, a in per_class_acc.items()
            },
        })

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc

            checkpoint_data = {
                "epoch": epoch,
                "arch": ARCH,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "val_acc": val_acc,
                "classes": train_ds.classes,
                "history": history,
            }

            # Giữ lại checkpoint theo epoch để debug hoặc so sánh sau này.
            epoch_checkpoint_path = (
                CHECKPOINT_DIR / f"efficientnet_vietfood_{timestamp}_epoch{epoch}.pth"
            )
            torch.save(checkpoint_data, epoch_checkpoint_path)

            # Đây là checkpoint duy nhất backend sẽ dùng khi predict.
            torch.save(checkpoint_data, BEST_CHECKPOINT_PATH)

            print(f"   💾 Best model saved: {epoch_checkpoint_path.name}")
            print(f"   ⭐ Serving model updated: {BEST_CHECKPOINT_PATH.name}")

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


if __name__ == "__main__":
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
    args = parser.parse_args()
    if args.no_class_weight:
        import ml.training.train as _self
        _self.USE_CLASS_WEIGHT = False
    main(resume=args.resume, ckpt=args.ckpt, data_dir=args.data_dir)
