"""Local EfficientNet inference for Vietnamese food classification."""

import json
from pathlib import Path
from typing import Any, Optional

from backend.config import settings
from ml.model_registry import load_manifest, validate_manifest

# ─── Constants ───────────────────────────────────────────────────────
ARCH = "efficientnet_b0"  # timm model — phải khớp train script
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CLASS_MAPPING = CHECKPOINT_DIR / "class_mapping.json"
IMAGE_SIZE = 224


BEST_CHECKPOINT = CHECKPOINT_DIR / "best_model.pth"
BEST_MANIFEST = CHECKPOINT_DIR / "best_model.manifest.json"
DEFAULT_SERVING_THRESHOLD = 0.85


def _resolve_serving_metadata(checkpoint: dict) -> tuple[str, float]:
    version = checkpoint.get("model_version")
    if not isinstance(version, str) or not version:
        version = "unversioned"
    raw_threshold = checkpoint.get("cv_confidence_threshold")
    try:
        threshold = float(raw_threshold)
    except (TypeError, ValueError):
        threshold = DEFAULT_SERVING_THRESHOLD
    return version, min(1.0, max(0.5, threshold))


def _resolve_checkpoint_classes(
    checkpoint: dict,
    mapping_path: Path = CLASS_MAPPING,
) -> list[str]:
    """Prefer the mapping stored atomically inside the serving checkpoint."""
    saved_classes = checkpoint.get("classes")
    if (
        isinstance(saved_classes, list)
        and saved_classes
        and all(isinstance(name, str) and name for name in saved_classes)
    ):
        return list(saved_classes)
    if not mapping_path.exists():
        return []
    with mapping_path.open(encoding="utf-8") as file:
        legacy_classes = json.load(file).get("classes", [])
    return (
        list(legacy_classes)
        if isinstance(legacy_classes, list)
        and all(isinstance(name, str) and name for name in legacy_classes)
        else []
    )


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
        manifest_path: Optional[Path] = None,
        require_manifest: bool = False,
    ) -> None:
        """
        Args:
            checkpoint_path: Đường dẫn đến file .pth checkpoint.
            device: "mps", "cuda", hoặc "cpu" (auto-detect lúc load() nếu None,
                để import module không kéo torch vào backend).
        """
        self.device: Optional[str] = device
        self.checkpoint_path = checkpoint_path or DEFAULT_CHECKPOINT
        self.manifest_path = manifest_path or BEST_MANIFEST
        self.require_manifest = require_manifest
        self.model: Any | None = None
        self.classes: list[str] = []
        self._loaded = False
        self.transform: Any | None = None
        self._torch: Any | None = None
        self.model_version = "unavailable"
        self.serving_threshold = DEFAULT_SERVING_THRESHOLD

    def load(self) -> None:
        """Load trained weights; keep local inference disabled if unavailable."""
        self.model = None
        self._loaded = False

        self.classes = []
        if self.checkpoint_path is None or not self.checkpoint_path.exists():
            return

        try:
            import timm
            import torch
            from torchvision import transforms
        except ImportError:
            return

        self.device = self.device or _default_device()
        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
            weights_only=True,
        )
        if self.manifest_path.exists():
            validate_manifest(
                load_manifest(self.manifest_path),
                self.checkpoint_path,
                require_passed_gate=True,
            )
        elif self.require_manifest:
            raise RuntimeError("Production CV model manifest is missing")
        self.model_version, self.serving_threshold = _resolve_serving_metadata(
            checkpoint
        )
        self.classes = _resolve_checkpoint_classes(checkpoint, CLASS_MAPPING)
        if not self.classes:
            return
        checkpoint_arch = checkpoint.get("arch")
        if checkpoint_arch and checkpoint_arch != ARCH:
            raise ValueError(
                f"Checkpoint architecture {checkpoint_arch!r} does not match {ARCH!r}"
            )

        self.model = timm.create_model(ARCH, num_classes=len(self.classes), drop_rate=0.3)
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
        # Một ngưỡng duy nhất cho cả tên món lẫn source. Trước đây dish_name dùng
        # số 0.3 cứng, nên một dự đoán bị coi là "fallback_required" vẫn kèm tên
        # món và tên đó lọt ra response khi Vision lỗi.
        confident = best_prob >= self.serving_threshold

        return {
            "dish_name": all_predictions[0]["class_name"] if confident else None,
            "confidence": best_prob,
            "all_predictions": all_predictions,
            "source": "local" if confident else "fallback_required",
            "model_version": self.model_version,
        }


# Singleton instance. Production refuses unmanifested local weights.
cv_model = CVModel(require_manifest=settings.is_production)
