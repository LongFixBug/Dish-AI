# FoodAI — Hướng dẫn cho Codex khi vào project

## Tóm tắt project

Nhận diện món ăn Việt từ ảnh + phân tích dinh dưỡng. Stack: FastAPI + PostgreSQL + Qdrant + llama.cpp (embedding + LLM) + Qwen3.7 Plus Vision (cloud API).

 người dùng là fresher AI Engineer, đang học bằng cách tự viết code (Codex chỉ hướng dẫn/giải thích, KHÔNG viết code thay — ngoại trừ khi yêu cầu rõ ràng). Giải thích: dịch từng dòng sang tiếng Việt tự nhiên + ẩn dụ đời thường.

## Chạy project (kiểm tra trước khi làm)

- **Data stores**: `docker compose up -d postgres qdrant`. PostgreSQL (port **5432**) là source of truth; Qdrant (port **6333**) chỉ là semantic index có thể dựng lại.
- **Embedding server** (llama.cpp, port 8081): KHÔNG nằm trong docker-compose, phải start thủ công:
  `llama-server --model models/Qwen3-Embedding-0.6B-Q8_0.gguf --embedding --port 8081 --host 0.0.0.0`
  File model thật: `models/Qwen3-Embedding-0.6B-Q8_0.gguf` (tên viết HOA, khác `.env`).
- **LLM server** (port 8080): `scripts/start_llama.sh`.
- **API**: `uvicorn backend.main:app --reload` (port 8000).
- **Env**: dùng `DEBUG=false python ...` để tắt SQLAlchemy echo (config `debug=true` bật echo gây nhiễu output).

Quy trình DB/seed: `alembic upgrade head` → `parse_*.py` → `data/*.json` → `seed_nutrition.py` → `recreate_vn_dishes.py` → `rebuild_dish_servings.py --apply` → `reindex_qdrant.py`.

## Cấu trúc code

- `backend/main.py` — FastAPI app + router: auth, chat, analyze, dishes, feedback, meals, nutrition goals, suggestions.
- `backend/api/` — endpoint mỏng, dùng `Depends(get_session)` và chuyển business logic xuống service.
- `backend/services/` — business logic cho auth, catalog/Qdrant, image cascade, chat, meal log, nutrition goal và suggestion.
- `backend/db/models.py` — ORM cho user/auth, catalog dinh dưỡng, candidate chờ duyệt, feedback, nutrition goal và meal log; không lưu vector trong PostgreSQL.
- `backend/db/postgres.py` — `get_session()` async, `async_session`.
- `schemas/` — Pydantic ở ROOT (không trong backend/). `nutrition.py` giữ các hàm toán dùng chung; `analyze.py` là contract nhận diện ảnh.
- `ml/inference/` — `cv.py` (EfficientNet-B0 local), `vision.py` (Qwen3.7 cloud, output tối đa 3 món + gram + nutrition estimate).
- `alembic/` — nơi duy nhất chứa migration schema chính thức; lịch sử cũ xem qua Git.
- `data/` — `usda_ingredients.json` (8060), `vn_foods.json` (2088: 838 `vnfood` + 1250 `vnmeal`).
  - `vnfood` là per-gram; `vnmeal` là **tổng dinh dưỡng cho một khẩu phần**. Không đổi tổng `vnmeal` thành per-100g khi chưa có khối lượng đo thực tế.

## Luồng nhận diện và tra catalog hiện tại

- `POST /api/v1/analyze`: image-kNN có thể tự chốt; nếu chưa đủ chắc thì local CV tạo prior/candidate và Qwen Vision quyết định fallback.
- Mỗi tên món được resolve qua PostgreSQL exact trước, Qdrant semantic sau; mọi hit Qdrant phải quay lại PostgreSQL bằng UUID.
- Món chưa có catalog chỉ dùng estimate trong response hiện tại và được đưa vào `dish_candidates`; không tự ghi thành dữ liệu tin cậy.
- `GET /api/v1/dishes/lookup` là endpoint read-only cho catalog món đã duyệt.
- Tái dùng `calculate_item_nutrition()` + `calculate_totals()` từ `schemas/nutrition.py`, KHÔNG viết lại toán.

## Lưu ý quan trọng

- Qdrant chỉ là index dẫn đường; kết quả cuối và dinh dưỡng luôn lấy từ PostgreSQL.
- Output Vision là input không tin cậy: luôn normalize confidence/gram/nutrition và fallback có kiểm soát.
- `typical_grams` của `vnmeal` là ước lượng có provenance (`source`, `confidence`, `rule`), không phải số đo từ Viện Dinh dưỡng. Chạy `scripts/rebuild_dish_servings.py` chỉ khi chủ động muốn tái tạo toàn bộ các ước lượng này.
- `plan.md` là nhật ký quyết định lịch sử; ưu tiên code, migration và test hiện tại khi nội dung cũ mâu thuẫn.

## Conventions

- Commit: `<type>: <description>` (feat/fix/refactor/docs/test/chore/perf/ci). Không ghi Co-Authored-By.
- Code: immutable, KISS/DRY/YAGNI, file 200-400 dòng, hàm <50 dòng.
- Test: TDD, coverage 80%+; chạy `uv run pytest -q`.
- Error handling: bắt hết, thông báo thân thiện UI, log chi tiết server.
