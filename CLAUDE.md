# FoodAI — Hướng dẫn cho Claude Code khi vào project

## Tóm tắt project

Nhận diện món ăn Việt từ ảnh + phân tích dinh dưỡng. Stack: FastAPI + PostgreSQL + Qdrant + llama.cpp (embedding + LLM) + Qwen3.7 Plus Vision (cloud API).

 người dùng là fresher AI Engineer, đang học bằng cách tự viết code (Claude chỉ hướng dẫn/giải thích, KHÔNG viết code thay — ngoại trừ khi yêu cầu rõ ràng). Giải thích: dịch từng dòng sang tiếng Việt tự nhiên + ẩn dụ đời thường.

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

- `backend/main.py` — FastAPI app + `include_router`. Router: chat, analyze, **dishes**.
- `backend/api/` — endpoint (analyzer pattern). `dishes.py` có 4 endpoint 2-tier, dùng `Depends(get_session)`.
- `backend/services/` — business logic: `embeddings`, `vector_catalog` (Qdrant), `conversions`, `dishes`, `dish_candidates`.
- `backend/db/models.py` — ORM cho catalog dinh dưỡng, món đã duyệt, candidate chờ duyệt và conversion rate; không lưu vector trong PostgreSQL.
- `backend/db/postgres.py` — `get_session()` async, `async_session`.
- `schemas/` — Pydantic ở ROOT (không trong backend/). `nutrition.py` có `calculate_*()` (toán, tái dùng), `dish.py` cho 2-tier.
- `ml/inference/` — `cv.py` (ResNet50 local, output dish_name), `vision.py` (Qwen3.7 cloud, output dish_name + ingredients + gram).
- `alembic/` — migration schema chính thức. `scripts/legacy/` chỉ lưu migration lịch sử, không chạy trên schema hiện tại.
- `data/` — `usda_ingredients.json` (8060), `vn_foods.json` (2088: 838 `vnfood` + 1250 `vnmeal`).
  - `vnfood` là per-gram; `vnmeal` là **tổng dinh dưỡng cho một khẩu phần**. Không đổi tổng `vnmeal` thành per-100g khi chưa có khối lượng đo thực tế.

## 2-tier dish lookup (kiến trúc chính)

- Tier 1 `GET /dishes/lookup`: institute (`source=vnmeal`) ưu tiên → fallback user-recipe (`dishes` JOIN `dish_ingredients`). `exists=false` → Tier 2.
- Tier 2 `POST /dishes` (contribute) + `POST /dishes/compute` (preview không lưu).
- `GET /ingredients/search`: exact/ILIKE PostgreSQL trước, Qdrant semantic fallback sau; kết quả Qdrant luôn được resolve lại qua UUID PostgreSQL.
- Tái dùng `calculate_ingredient_nutrition()` + `calculate_totals()` từ `schemas/nutrition.py`, KHÔNG viết lại toán.

## Lưu ý quan trọng

- `dish_name` UNIQUE → contribute trùng → HTTP 409.
- ILIKE phân biệt dấu tiếng Việt: user gõ "suon" KHÔNG móc "sườn" (chỉ vector giúp). Pha 2 cần normalize dấu.
- `conversion_assumed` flag gần như không bao giờ báo vì có fallback nước (rate NULL=1.0).
- `typical_grams` của `vnmeal` là ước lượng có provenance (`source`, `confidence`, `rule`), không phải số đo từ Viện Dinh dưỡng. Chạy `scripts/rebuild_dish_servings.py` chỉ khi chủ động muốn tái tạo toàn bộ các ước lượng này.
- Pha 2 chưa làm: trust-score + versioning (`dish_recipes`), tăng `usage_count` khi lookup, admin verify recipe.
- Plan đầy đủ 2-tier: `/Users/nguyenhailong/.claude/plans/frolicking-waddling-journal.md`.

## Conventions

- Commit: `<type>: <description>` (feat/fix/refactor/docs/test/chore/perf/ci). Không ghi Co-Authored-By.
- Code: immutable, KISS/DRY/YAGNI, file 200-400 dòng, hàm <50 dòng.
- Test: TDD, coverage 80%+; chạy `uv run pytest -q`.
- Error handling: bắt hết, thông báo thân thiện UI, log chi tiết server.
