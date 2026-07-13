"""CV service — PyTorch model local để phân loại món ăn Việt.

Tầng 1 trong pipeline 2 tầng:
- Nếu confidence >= threshold → dùng kết quả local
- Nếu confidence < threshold → fallback Qwen3.7 Plus (cloud)
"""

import glob
import json
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms, models

from backend.config import settings

# ─── Constants ───────────────────────────────────────────────────────
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
CONFIDENCE_THRESHOLD = 0.6  # Ngưỡng fallback sang cloud (hạ từ 0.8 — 12 class conf phân tán hơn)
CLASS_MAPPING = Path("checkpoints/class_mapping.json")
IMAGE_SIZE = 224


def _find_latest_checkpoint() -> Optional[Path]:
    """Tìm checkpoint mới nhất trong checkpoints/ (glob *_vietfood_*.pth, sorted).

    Future-proof: stage B retrain sinh tên mới (efficientnet_vietfood_*),
    glob tự lấy file cuối theo timestamp trong tên → luôn dùng model mới nhất.
    """
    files = sorted(glob.glob("checkpoints/*_vietfood_*.pth"))
    return Path(files[-1]) if files else None


DEFAULT_CHECKPOINT = _find_latest_checkpoint()


class CVModel:
    """Wrapper cho ResNet50 fine-tuned model."""

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
        self.device = device or (
            "mps" if torch.backends.mps.is_available()
            else "cuda" if torch.cuda.is_available()
            else "cpu"
        )
        self.checkpoint_path = checkpoint_path or DEFAULT_CHECKPOINT
        self.model: Optional[nn.Module] = None
        self.classes: list[str] = []
        self._loaded = False

        # Transform cho inference (giống validation)
        self.transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])

    def load(self) -> None:
        """Load model từ checkpoint.

        Nếu chưa có checkpoint (chưa train), tạo model rỗng để không crash.
        """
        # Load class mapping trước
        if CLASS_MAPPING.exists():
            with open(CLASS_MAPPING) as f:
                self.classes = json.load(f)["classes"]
        else:
            self.classes = []

        if not self.classes:
            self._loaded = False
            return

        # Tạo model architecture
        self.model = models.resnet50(weights=None)
        in_features = self.model.fc.in_features
        self.model.fc = nn.Sequential(
            nn.Dropout(p=0.3),
            nn.Linear(in_features, 512),
            nn.ReLU(),
            nn.Dropout(p=0.3),
            nn.Linear(512, len(self.classes)),
        )

        # Load weights nếu có
        if self.checkpoint_path.exists():
            checkpoint = torch.load(
                self.checkpoint_path,
                map_location=self.device,
                weights_only=True,
            )
            self.model.load_state_dict(checkpoint["model_state_dict"])
        else:
            # Chưa có model trained — vẫn load được nhưng prediction sẽ random
            pass

        self.model = self.model.to(self.device)
        self.model.eval()
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @torch.no_grad()
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

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")

        # Load + transform ảnh
        image = Image.open(image_path).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        # Inference
        outputs = self.model(tensor)
        probabilities = torch.softmax(outputs, dim=1)[0]

        # Top-5 predictions
        top5_prob, top5_idx = torch.topk(probabilities, min(5, len(self.classes)))
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
