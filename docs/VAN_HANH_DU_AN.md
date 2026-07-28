# Hướng dẫn chạy & vận hành dự án FoodAI

> Tài liệu này viết cho người **không cần biết gì về AI** vẫn đọc hiểu được.
> Mọi thuật ngữ kỹ thuật đều có giải thích trong ngoặc `( )` ngay bên cạnh.

---

## 1. Dự án này làm gì?

FoodAI là ứng dụng **nhận diện món ăn Việt Nam từ ảnh chụp** rồi **tính toán dinh dưỡng** (calo, đạm, béo, tinh bột...).

Luồng hoạt động đơn giản:

```
Người dùng chụp ảnh món ăn
        │
        ▼
Hệ thống "nhìn" ảnh và đoán tên món (vd: "phở bò")
        │
        ▼
Tra cứu bảng dinh dưỡng trong cơ sở dữ liệu
        │
        ▼
Trả về: tên món + calo + các chất dinh dưỡng
```

---

## 2. Bức tranh tổng thể — các "bộ phận" của hệ thống

Dự án gồm nhiều **service** (dịch vụ — hiểu là các chương trình nhỏ chạy song song, mỗi cái đảm nhiệm một việc). Chúng nói chuyện với nhau qua **port** (cổng — giống số phòng trong một tòa nhà, để biết gõ cửa đúng chỗ).

| Bộ phận | Port (cổng) | Vai trò dễ hiểu |
|---|---|---|
| **API backend** (FastAPI — khung viết máy chủ bằng Python) | 8000 | "Bộ não điều phối" — nhận yêu cầu từ app, gọi các bộ phận khác, trả kết quả |
| **PostgreSQL** (cơ sở dữ liệu quan hệ — nơi lưu dữ liệu dạng bảng, như Excel khổng lồ) | 5432 | "Sổ cái chính" — lưu danh sách món ăn, bảng dinh dưỡng. Đây là nguồn dữ liệu gốc, mất là mất thật |
| **Qdrant** (vector database — cơ sở dữ liệu chuyên tìm kiếm theo "độ giống nhau" thay vì tìm đúng chữ) | 6333 | "Người tìm kiếm thông minh" — gõ "sườn nướng" vẫn tìm ra "sườn heo nướng mật ong". Có thể xóa và dựng lại từ PostgreSQL, không sợ mất |
| **LLM server** (Large Language Model — mô hình ngôn ngữ lớn, chương trình AI hiểu và sinh văn bản, chạy bằng llama.cpp ngay trên máy) | 8080 | "Người viết lách" — hỗ trợ trả lời chat, xử lý văn bản |
| **Embedding server** (embedding — kỹ thuật biến câu chữ thành dãy số, để máy so sánh 2 câu có "nghĩa giống nhau" không) | 8081 | "Người phiên dịch chữ → số" — phục vụ tìm kiếm thông minh ở trên |
| **Image embedding server** (SigLIP 2 — mô hình AI biến **ảnh** thành dãy số để so sánh ảnh với ảnh) | 8082 | "Người phiên dịch ảnh → số" — giúp so ảnh món ăn mới chụp với kho ảnh mẫu |
| **Vision API** (Qwen Vision — dịch vụ AI "nhìn ảnh" chạy trên cloud, tức máy chủ của nhà cung cấp, gọi qua internet, **tốn tiền theo lượt gọi**) | (không có port, gọi qua internet) | "Chuyên gia nhìn ảnh" — khi các cách nhận diện tại chỗ không chắc chắn, mới nhờ đến chuyên gia này |
| **Redis** (bộ nhớ đệm — nơi lưu tạm kết quả để lần sau lấy nhanh, không phải tính lại) | (nội bộ Docker) | "Giấy nhớ dán tường" — tăng tốc |
| **MinIO** (kho lưu file, tương thích chuẩn S3 của Amazon) | 9000 / 9001 | "Nhà kho chứa ảnh" — lưu file ảnh người dùng gửi lên |

> 💡 Ghi nhớ quan trọng: **PostgreSQL là "sự thật duy nhất"** (source of truth). Qdrant chỉ là bản chỉ mục phụ, hỏng thì chạy lại script để dựng lại được.

---

## 3. Cần cài gì trước (làm 1 lần duy nhất)

1. **Docker** (công cụ đóng gói và chạy phần mềm trong "hộp" cách ly, không cần cài từng thứ vào máy) — dùng để chạy PostgreSQL, Qdrant, Redis, MinIO.
2. **uv** (trình quản lý Python hiện đại — tự cài đúng phiên bản Python và thư viện cho dự án).
3. **llama.cpp** (chương trình chạy mô hình AI ngay trên máy cá nhân, không cần internet) — cụ thể là lệnh `llama-server`.
4. **File model** (model — "bộ não" AI đã huấn luyện sẵn, tải về dạng file dung lượng lớn) đặt trong thư mục `models/`:
   - `Qwen3-Embedding-0.6B-Q8_0.gguf` (dùng cho tìm kiếm thông minh)
   - `qwen2.5-7b-instruct-q4_k_m.gguf` (dùng cho chat/LLM)
   - Có thể tải bằng: `bash scripts/download_models.sh`
5. **File `.env`** (file cấu hình bí mật — chứa mật khẩu, khóa API; không bao giờ đưa lên git) — hỏi người quản lý dự án để lấy nội dung, đặc biệt là khóa gọi Vision API.

---

## 4. Cách chạy nhanh nhất (khuyên dùng)

Chỉ cần **một lệnh**, script sẽ tự bật lần lượt mọi thứ và bỏ qua cái nào đã chạy sẵn:

```bash
bash scripts/dev_up.sh
```

Script này tự làm 4 bước:

1. Bật **PostgreSQL + Qdrant** bằng Docker.
2. Chạy **migration** (migration — script cập nhật cấu trúc bảng trong cơ sở dữ liệu lên phiên bản mới nhất, giống "bản vá" cho database).
3. Bật **llama.cpp** (LLM cổng 8080 + embedding cổng 8081). Nếu máy chưa cài `llama-server` thì bỏ qua — tìm kiếm thông minh sẽ yếu đi nhưng tra cứu chính xác vẫn chạy.
4. Bật **API** ở cổng 8000, log (nhật ký chạy — nơi ghi lại mọi hoạt động và lỗi) ghi vào `logs/api.log`.

Nếu không cần AI chat/tìm kiếm thông minh (tiết kiệm RAM):

```bash
bash scripts/dev_up.sh --no-llm
```

Bật thêm server so sánh ảnh (cần cho tính năng nhận diện ảnh):

```bash
bash scripts/start_image_embed.sh
```

**Dừng toàn bộ:**

```bash
bash scripts/dev_down.sh
```

---

## 5. Kiểm tra hệ thống có sống không

Sau khi chạy `dev_up.sh`, kiểm tra bằng:

| Việc cần kiểm tra | Cách làm |
|---|---|
| API còn sống? | Mở trình duyệt: `http://127.0.0.1:8000/live` (trả về OK là sống) |
| API sẵn sàng phục vụ? (đã nối được database chưa) | `http://127.0.0.1:8000/ready` |
| Xem & thử mọi endpoint (endpoint — một "địa chỉ chức năng" của API, vd `/dishes/lookup` là chức năng tra món) | `http://127.0.0.1:8000/docs` — trang tài liệu tự động, bấm thử trực tiếp được |
| Chạy bộ kiểm tra nhanh | `bash scripts/smoke_test.sh` (smoke test — kiểm tra "khói": bật máy lên xem có bốc khói không, tức kiểm tra nhanh các chức năng chính. Script này **không** gọi Vision API nên không tốn tiền) |
| Xem lỗi khi có sự cố | Đọc file `logs/api.log` |

---

## 6. Chạy từng phần thủ công (khi cần hiểu sâu hoặc debug)

```bash
# 1. Bật database
docker compose up -d postgres qdrant

# 2. Cập nhật cấu trúc database
uv run alembic upgrade head

# 3. Bật server AI cục bộ (LLM + embedding)
bash scripts/start_llama.sh

# 4. Bật server so sánh ảnh
bash scripts/start_image_embed.sh

# 5. Bật API (--reload: tự khởi động lại khi sửa code)
DEBUG=false uv run uvicorn backend.main:app --reload --port 8000
```

> 💡 `DEBUG=false` để tắt chế độ in mọi câu lệnh database ra màn hình (rất nhiễu).

---

## 7. Nạp dữ liệu lần đầu (seed — "gieo hạt" dữ liệu ban đầu vào database trống)

Chạy **theo đúng thứ tự** sau, chỉ cần làm khi dựng database mới từ đầu:

```bash
uv run alembic upgrade head                        # 1. Tạo cấu trúc bảng
uv run python scripts/parse_usda.py                # 2. Đọc dữ liệu dinh dưỡng gốc → file data/*.json
uv run python scripts/parse_vn_foods.py
uv run python scripts/seed_nutrition.py            # 3. Nạp bảng dinh dưỡng vào database
uv run python scripts/recreate_vn_dishes.py        # 4. Tạo danh mục món ăn Việt
uv run python scripts/rebuild_dish_servings.py --apply   # 5. Ước lượng khẩu phần (gram) cho từng món
uv run python scripts/reindex_qdrant.py            # 6. Dựng chỉ mục tìm kiếm thông minh
```

Về dữ liệu:
- `data/usda_ingredients.json` — ~8.000 nguyên liệu từ USDA (Bộ Nông nghiệp Mỹ, nguồn dinh dưỡng chuẩn).
- `data/vn_foods.json` — ~2.000 món/nguyên liệu Việt Nam, gồm 2 loại:
  - `vnfood`: dinh dưỡng **tính trên mỗi gram** (muốn ăn bao nhiêu nhân lên bấy nhiêu).
  - `vnmeal`: dinh dưỡng **tổng cho cả một suất ăn** (vd 1 tô phở). ⚠️ Không tự ý quy đổi về "trên 100g" vì chưa có số cân đo thực tế.

---

## 8. Chạy kiểm thử (test — code kiểm tra tự động, đảm bảo sửa chỗ này không làm hỏng chỗ khác)

```bash
uv run pytest -q
```

Quy ước dự án: độ phủ test (coverage — tỉ lệ % code được test "chạm" tới) tối thiểu **80%**.

---

## 9. Cách hệ thống nhận diện món ăn (đọc để hiểu, không cần làm gì)

Hệ thống dùng chiến thuật **cascade** (thác nước — thử cách rẻ trước, cách đắt sau, dừng ngay khi đủ tự tin):

```
Ảnh món ăn gửi lên
   │
   ▼
Bước 1: So ảnh với kho ảnh mẫu (SigLIP 2 + Qdrant)
   │  "Ảnh này giống ảnh phở bò trong kho tới 95%" → chốt luôn, MIỄN PHÍ
   │
   ▼ (nếu chưa đủ tự tin)
Bước 2: Model CV cục bộ (CV = Computer Vision — thị giác máy tính;
   │  model ResNet50 được huấn luyện riêng, chạy ngay trên máy, MIỄN PHÍ)
   │
   ▼ (nếu vẫn chưa chắc)
Bước 3: Gọi Vision API trên cloud (TỐN TIỀN theo lượt)
   │  Chuyên gia mạnh nhất, kiêm luôn bóc tách nguyên liệu + ước lượng gram
   ▼
Tra bảng dinh dưỡng → trả kết quả
```

Vì vậy khi test tay, **hạn chế gọi endpoint `/analyze`** trừ khi thật sự cần — mỗi lần gọi có thể tốn một lượt Vision API.

---

## 10. Sự cố thường gặp & cách xử lý

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| API không lên / cổng 8000 im lặng | Lỗi khi khởi động | Đọc `logs/api.log`, tìm dòng có chữ `Error` |
| `/ready` báo lỗi nhưng `/live` OK | Database chưa bật hoặc chưa migrate | `docker compose up -d postgres qdrant` rồi `uv run alembic upgrade head` |
| Tìm kiếm "suon" không ra "sườn" | ILIKE (cách tìm gần đúng của PostgreSQL) phân biệt dấu tiếng Việt | Đây là hạn chế đã biết — tìm kiếm thông minh qua Qdrant sẽ bù; cần server embedding (8081) đang chạy |
| Tìm kiếm thông minh không hoạt động | Server embedding (8081) chưa bật | `bash scripts/start_llama.sh` |
| Thêm món bị lỗi 409 (mã HTTP nghĩa là "xung đột") | Tên món đã tồn tại — tên món là duy nhất trong hệ thống | Đổi tên hoặc dùng món có sẵn |
| Nhận diện ảnh kém / lỗi | Server so sánh ảnh (8082) chưa bật, hoặc hết lượt Vision API | `bash scripts/start_image_embed.sh`; kiểm tra khóa API trong `.env` |
| Kết quả báo nguyên liệu "missing" (thiếu) | Database không có nguyên liệu tên đó — **không phải lỗi phần mềm** | Bổ sung nguyên liệu vào catalog nếu cần |
| Muốn làm sạch, chạy lại chỉ mục tìm kiếm | Qdrant chỉ là bản phụ | `uv run python scripts/reindex_qdrant.py` — an toàn, không mất dữ liệu gốc |

**Sao lưu / phục hồi database:**

```bash
bash scripts/backup_postgres.sh
```

```bash
bash scripts/restore_postgres.sh
```

---

## 11. Từ điển tóm tắt (tra nhanh)

- **API** — cổng giao tiếp để app/website gửi yêu cầu và nhận kết quả từ máy chủ.
- **Backend** — phần chạy trên máy chủ, người dùng không nhìn thấy trực tiếp.
- **Model (mô hình AI)** — "bộ não" đã được huấn luyện sẵn, lưu thành file, nạp lên để dùng.
- **Embedding** — biến chữ hoặc ảnh thành dãy số, để máy đo được "độ giống nhau".
- **Vector database (Qdrant)** — kho chứa các dãy số đó, chuyên tìm "cái nào giống nhất".
- **LLM** — mô hình ngôn ngữ lớn, AI hiểu và sinh văn bản (như ChatGPT).
- **Computer Vision (CV)** — nhánh AI cho máy "nhìn" và hiểu ảnh.
- **Cloud API** — dịch vụ AI thuê ngoài, gọi qua internet, trả tiền theo lượt dùng.
- **Migration** — script cập nhật cấu trúc database theo từng phiên bản.
- **Seed** — nạp dữ liệu ban đầu vào database trống.
- **Log** — file nhật ký ghi lại hoạt động và lỗi của chương trình.
- **Port (cổng)** — số định danh để các chương trình trên cùng máy tìm đúng nhau.
- **Docker** — chạy phần mềm trong "hộp" đóng gói sẵn, khỏi cài đặt lằng nhằng.
- **Smoke test** — kiểm tra nhanh xem hệ thống có "bốc khói" (hỏng cơ bản) không.
