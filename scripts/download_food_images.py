"""Download ảnh train cho 12 món Việt (icrawler Bing Image Search).

Giai đoạn B: mở rộng từ 3 → 12 món, 50 ảnh/món train. Keyword có suffix địa
danh để lọc ảnh sai. sleep 5s giữa món tránh Bing rate limit.

Sau download: chạy clean_images.py để xóa ảnh corrupt, rồi review thủ công
5-10 ảnh/món (Bing hay trả ảnh nhận diện sai).

Usage:
    python scripts/download_food_images.py   # → data/images/train/
"""

import os
import time

from icrawler.builtin import BingImageCrawler

# 12 món: 3 cũ + 9 mới. Keyword có suffix "việt nam"/địa danh để lọc ảnh sai.
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

save_root = "data/images/train"
MAX_NUM = 50  # tăng từ 25 → 50 (roadmap mục tiêu 500-1000 ảnh)
SLEEP_BETWEEN = 5  # giây giữa món — tránh Bing rate limit

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
