"""Download ảnh validation cho 12 món Việt (icrawler Bing Image Search).

Giai đoạn B: 12 món, 30 ảnh/món val. Giống download_food_images.py nhưng
save_root=data/images/val, max_num=30.

Usage:
    python scripts/download_val_images.py   # → data/images/val/
"""

import os
import time

from icrawler.builtin import BingImageCrawler

dishes = {
    "pho_bo": "phở bò việt nam",
    "bun_cha": "bún chả hà nội",
    "com_tam": "cơm tấm sài gòn",
    "bun_bo_hue": "bún bò huế",
    "banh_mi": "bánh mì thịt việt nam",
    "banh_xeo": "bánh xèo việt nam",
    "goi_cuon": "gỏi cuốn tôm",
    "bun_rieu": "bún riêu cua",
    "chao_long": "cháo lòng",
    "hu_tieu": "hủ tiếu nam vang",
    "bun_thit_nuong": "bún thịt nướng",
    "mi_quang": "mì quảng đà nẵng",
}

save_root = "data/images/val"
MAX_NUM = 30
SLEEP_BETWEEN = 5

for i, (folder_name, keyword) in enumerate(dishes.items()):
    save_dir = os.path.join(save_root, folder_name)
    os.makedirs(save_dir, exist_ok=True)

    print(f"[{i+1}/{len(dishes)}] Đang tải: {keyword} → {folder_name}")

    bing_crawler = BingImageCrawler(
        storage={"root_dir": save_dir},
        downloader_threads=4,
    )
    bing_crawler.crawl(keyword=keyword, max_num=MAX_NUM)

    if i < len(dishes) - 1:
        time.sleep(SLEEP_BETWEEN)

print("✅ Xong! Chạy scripts/clean_images.py rồi review thủ công.")
