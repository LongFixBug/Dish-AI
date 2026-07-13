import os
from icrawler.builtin import BingImageCrawler

dishes = {
    "pho_bo": "phở bò việt nam",
    "bun_cha": "bún chả hà nội",
    "com_tam": "cơm tấm sài gòn",
}

save_root = "data/images/train"

for folder_name, keyword in dishes.items():
    save_dir = os.path.join(save_root, folder_name)
    os.makedirs(save_dir, exist_ok=True)

    print(f"Đang tải: {keyword} → {folder_name}")

    bing_crawler = BingImageCrawler(
        storage={"root_dir": save_dir},
        downloader_threads=4,
    )

    bing_crawler.crawl(
        keyword=keyword,
        max_num=25,
    )

print("✅ Xong!")