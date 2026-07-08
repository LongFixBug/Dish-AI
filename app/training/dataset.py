"""VietFoodDataset — PyTorch Dataset cho ảnh món ăn Việt Nam.

Hỗ trợ 3 chế độ:
- train: augmentation (flip, rotate, color jitter)
- val/test: chỉ resize + normalize
"""

from pathlib import Path
from typing import Optional

import torch
from torch.utils.data import Dataset
from torchvision import transforms
from PIL import Image


class VietFoodDataset(Dataset):
    """Dataset ảnh món Việt cho phân loại (classification).

    Cấu trúc thư mục:
        data/images/train/
            pho_bo/
                img001.jpg
                img002.jpg
            bun_cha/
                img001.jpg
            ...

    Mỗi thư mục con = 1 class (tên món).
    """

    # Danh sách món Việt phổ biến (sẽ mở rộng dần)
    DEFAULT_CLASSES = [
        "pho_bo",
        "pho_ga",
        "bun_bo_hue",
        "bun_cha",
        "com_tam",
        "banh_mi",
        "banh_xeo",
        "goi_cuon",
        "bun_rieu",
        "chao_long",
    ]

    # Mean & std của ImageNet (pretrained models expect this)
    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]

    def __init__(
        self,
        data_dir: str | Path,
        classes: Optional[list[str]] = None,
        split: str = "train",
        image_size: int = 224,
    ) -> None:
        """Khởi tạo dataset.

        Args:
            data_dir: Thư mục gốc chứa train/val/test.
            classes: Danh sách tên class (None = tự detect từ thư mục).
            split: "train", "val", hoặc "test".
            image_size: Kích thước ảnh đầu vào (ResNet cần 224).
        """
        self.data_dir = Path(data_dir)
        self.split = split
        self.image_size = image_size

        # Detect classes từ thư mục (nếu không chỉ định)
        split_dir = self.data_dir / split
        if not split_dir.exists():
            raise FileNotFoundError(
                f"Không tìm thấy thư mục {split_dir}. "
                f"Hãy tạo cấu trúc: data/images/{split}/<ten_mon>/<anh>.jpg"
            )

        if classes is None:
            self.classes = sorted(
                d.name for d in split_dir.iterdir() if d.is_dir()
            )
        else:
            self.classes = classes

        if not self.classes:
            raise ValueError(f"Không tìm thấy class nào trong {split_dir}")

        # Build index: list of (image_path, class_index)
        self.samples: list[tuple[Path, int]] = []
        for class_idx, class_name in enumerate(self.classes):
            class_dir = split_dir / class_name
            if not class_dir.is_dir():
                continue
            for img_path in class_dir.iterdir():
                if img_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    self.samples.append((img_path, class_idx))

        if not self.samples:
            raise ValueError(
                f"Không tìm thấy ảnh nào trong {split_dir}. "
                f"Thêm ảnh vào các thư mục con theo class."
            )

        # Transform theo split
        self.transform = self._build_transform()

    def _build_transform(self):
        """Build transform pipeline cho từng split."""
        size = self.image_size

        if self.split == "train":
            return transforms.Compose([
                transforms.RandomResizedCrop(size, scale=(0.8, 1.0)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomRotation(degrees=15),
                transforms.ColorJitter(
                    brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1
                ),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=self.IMAGENET_MEAN, std=self.IMAGENET_STD
                ),
            ])
        else:
            return transforms.Compose([
                transforms.Resize((size, size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=self.IMAGENET_MEAN, std=self.IMAGENET_STD
                ),
            ])

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, class_idx = self.samples[idx]
        image = Image.open(img_path).convert("RGB")
        tensor = self.transform(image)
        return tensor, class_idx

    def get_class_name(self, idx: int) -> str:
        """Trả về tên class (tiếng Việt, không dấu gạch dưới)."""
        return self.classes[idx].replace("_", " ").title()

    @property
    def num_classes(self) -> int:
        return len(self.classes)
