"""Training script cho VietFood CV model.

Fine-tune EfficientNet-B0 (timm) pretrained ImageNet → phân loại món Việt.
Full fine-tune (không freeze backbone) với lr nhỏ 5e-5 — tốt cho food
(texture/quang cảnh quan trọng, không chỉ shape).

Usage:
    python -m ml.training.train

Yêu cầu: ảnh đã được tổ chức trong data/images/{train,val}/<ten_mon>/
"""

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

DATA_DIR = PROJECT_ROOT / "data" / "images"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

DEVICE = torch.device(
    "mps" if torch.backends.mps.is_available()
    else "cuda" if torch.cuda.is_available()
    else "cpu"
)


def create_model(num_classes: int) -> nn.Module:
    """Tạo EfficientNet-B0 pretrained (timm) + classifier head cho num_classes.

    Full fine-tune (không freeze) — drop_rate=0.3 dropout built-in.
    timm tự thay classifier head khi truyền num_classes.

    Args:
        num_classes: Số lượng món ăn cần phân loại.

    Returns:
        Model sẵn sàng để train (toàn bộ param requires_grad=True).
    """
    model = timm.create_model(
        ARCH, pretrained=True, num_classes=num_classes, drop_rate=0.3
    )
    return model


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
) -> tuple[float, float]:
    """Evaluate model trên validation/test set.

    Returns:
        (avg_loss, accuracy).
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    avg_loss = total_loss / len(loader)
    accuracy = 100.0 * correct / total
    return avg_loss, accuracy


def main() -> None:
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
    print(f"\n🧠 Creating model ({ARCH}, {train_ds.num_classes} classes)...")
    model = create_model(train_ds.num_classes)
    model = model.to(DEVICE)
    print(f"   Total params: {sum(p.numel() for p in model.parameters()):,}")
    print(f"   Trainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=NUM_EPOCHS
    )

    # ── Training loop ────────────────────────────────────────────────
    best_val_acc = 0.0
    history: list[dict] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n🚀 Starting training ({NUM_EPOCHS} epochs)...")
    print("-" * 60)

    for epoch in range(1, NUM_EPOCHS + 1):
        print(f"\n📅 Epoch {epoch}/{NUM_EPOCHS}")
        print(f"   LR: {scheduler.get_last_lr()[0]:.2e}")

        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, epoch
        )
        print(f"   ✅ Train  — Loss: {train_loss:.4f} | Acc: {train_acc:.1f}%")

        # Validate
        val_loss, val_acc = evaluate(model, val_loader, criterion)
        print(f"   📊 Val    — Loss: {val_loss:.4f} | Acc: {val_acc:.1f}%")

        scheduler.step()

        # Save history
        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 2),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 2),
        })

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            checkpoint_path = CHECKPOINT_DIR / f"efficientnet_vietfood_{timestamp}_epoch{epoch}.pth"
            torch.save({
                "epoch": epoch,
                "arch": ARCH,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": val_acc,
                "classes": train_ds.classes,
                "history": history,
            }, checkpoint_path)
            print(f"   💾 Best model saved: {checkpoint_path.name}")

    print("\n" + "=" * 60)
    print(f"🏁 Training complete! Best val accuracy: {best_val_acc:.1f}%")

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
    main()
