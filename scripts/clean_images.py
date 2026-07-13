# 1. Import
import os
from PIL import Image

# 2. Thư mục gốc chứa ảnh
DATA_DIR = "data/images"

# 3. Biến đếm
deleted = 0

# 4. Duyệt qua tất cả file trong DATA_DIR bằng os.walk()
#    os.walk() trả về 3 thứ: (thư_mục_hiện_tại, danh_sách_thư_mục_con, danh_sách_file)
for root, dirs, files in os.walk(DATA_DIR):
    for file_name in files:
        # 4a. Chỉ xử lý file ảnh (đuôi .jpg, .png, .jpeg, .webp)
        if not file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue

        # 4b. Tạo đường dẫn đầy đủ
        file_path = os.path.join(root, file_name)

        # 4c. Thử mở ảnh bằng PIL
        try:
            img = Image.open(file_path)
            img.verify()  # kiểm tra file có đúng là ảnh không
        except Exception as e:
            # 4d. Nếu lỗi → xóa file
            print(f"❌ Xóa ảnh lỗi: {file_path}  ({e})")
            os.remove(file_path)
            deleted += 1

# 5. In tổng kết
print(f"\n✅ Đã xóa {deleted} ảnh lỗi")