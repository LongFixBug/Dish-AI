"""Local EfficientNet inference for Vietnamese food classification."""

import json
from pathlib import Path
from typing import Any, Optional

# ─── Constants ───────────────────────────────────────────────────────
ARCH = "efficientnet_b0"  # timm model — phải khớp train script
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
CONFIDENCE_THRESHOLD = 0.4
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CLASS_MAPPING = CHECKPOINT_DIR / "class_mapping.json"
IMAGE_SIZE = 224


BEST_CHECKPOINT = CHECKPOINT_DIR / "best_model.pth"


def _find_best_checkpoint() -> Optional[Path]:
    """Return the serving checkpoint, with legacy checkpoints as fallback."""
    if BEST_CHECKPOINT.exists():
        return BEST_CHECKPOINT

    files = list(CHECKPOINT_DIR.glob("efficientnet_vietfood_*.pth"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


DEFAULT_CHECKPOINT = _find_best_checkpoint()


def _default_device() -> str:
    """Choose a Torch device only when optional local-CV dependencies exist."""
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


class CVModel:
    """Wrapper cho EfficientNet-B0 fine-tuned model (timm)."""

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        device: Optional[str] = None,
    ) -> None:
        """
        Args:
            checkpoint_path: Đường dẫn đến file .pth checkpoint.
            device: "mps", "cuda", hoặc "cpu" (auto-detect nếu None).
        """
        self.device = device or _default_device()
        self.checkpoint_path = checkpoint_path or DEFAULT_CHECKPOINT
        self.model: Any | None = None
        self.classes: list[str] = []
        self._loaded = False
        self.transform: Any | None = None
        self._torch: Any | None = None

    def load(self) -> None:
        """Load trained weights; keep local inference disabled if unavailable."""
        self.model = None
        self._loaded = False

        if CLASS_MAPPING.exists():
            with CLASS_MAPPING.open(encoding="utf-8") as f:
                self.classes = json.load(f)["classes"]
        else:
            self.classes = []

        if (
            not self.classes
            or self.checkpoint_path is None
            or not self.checkpoint_path.exists()
        ):
            return

        try:
            import timm
            import torch
            from torchvision import transforms
        except ImportError:
            return

        self.model = timm.create_model(ARCH, num_classes=len(self.classes), drop_rate=0.3)

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
            weights_only=True,
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])

        self.model = self.model.to(self.device)
        self.model.eval()
        self._torch = torch
        self.transform = transforms.Compose([
            transforms.Resize(IMAGE_SIZE),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, image_path: str | Path) -> dict:
        """Dự đoán món ăn từ ảnh.

        Args:
            image_path: Đường dẫn đến file ảnh.

        Returns:
            {
                "dish_name": str | None,
                "confidence": float (0-1),
                "all_predictions": list of {class_name, probability},
                "source": "local" | "fallback_required",
            }

        Nếu model chưa load → trả dict source="fallback_required" (không raise)
        để analyze skip sang vision graceful.
        """
        if not self._loaded:
            return {
                "dish_name": None,
                "confidence": 0.0,
                "all_predictions": [],
                "source": "fallback_required",
            }
        if self._torch is None or self.transform is None or self.model is None:
            raise RuntimeError("CV model is marked loaded without inference dependencies")

        from PIL import Image

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")

        # Load + transform ảnh
        image = Image.open(image_path).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        # Inference
        with self._torch.no_grad():
            outputs = self.model(tensor)
            probabilities = self._torch.softmax(outputs, dim=1)[0]

        # Top-5 predictions
        top5_prob, top5_idx = self._torch.topk(probabilities, min(5, len(self.classes)))
        all_predictions = [
            {
                "class_name": self.classes[idx].replace("_", " ").title(),
                "probability": round(prob.item(), 4),
            }
            for prob, idx in zip(top5_prob, top5_idx)
        ]

        best_prob = all_predictions[0]["probability"]

        return {
            "dish_name": all_predictions[0]["class_name"] if best_prob >= 0.3 else None,
            "confidence": best_prob,
            "all_predictions": all_predictions,
            "source": "local" if best_prob >= CONFIDENCE_THRESHOLD else "fallback_required",
        }


# Singleton instance
cv_model = CVModel()
