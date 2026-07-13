# FoodAI — Hướng dẫn cho Claude Code khi vào project

## Tóm tắt project

Nhận diện món ăn Việt từ ảnh + phân tích dinh dưỡng. Stack: FastAPI + PostgreSQL/pgvector + llama.cpp (embedding + LLM) + Qwen3.7 Plus Vision (cloud API).

 người dùng là fresher AI Engineer, đang học bằng cách tự viết code (Claude chỉ hướng dẫn/giải thích, KHÔNG viết code thay — ngoại trừ khi yêu cầu rõ ràng). Giải thích: dịch từng dòng sang tiếng Việt tự nhiên + ẩn dụ đời thường.

## Chạy project (kiểm tra trước khi làm)

- **DB**: `docker compose up -d postgres qdrant` (pgvector/pgvector:pg16). Lưu ý: docker-compose map port **5432**, nhưng `backend/config.py` mặc định `database_url` trỏ **5433** — kiểm tra `.env`.
- **Embedding server** (llama.cpp, port 8081): KHÔNG nằm trong docker-compose, phải start thủ công:
  `llama-server --model models/Qwen3-Embedding-0.6B-Q8_0.gguf --embedding --port 8081 --host 0.0.0.0`
  File model thật: `models/Qwen3-Embedding-0.6B-Q8_0.gguf` (tên viết HOA, khác `.env`).
- **LLM server** (port 8080): `scripts/start_llama.sh`.
- **API**: `uvicorn backend.main:app --reload` (port 8000).
- **Env**: dùng `DEBUG=false python ...` để tắt SQLAlchemy echo (config `debug=true` bật echo gây nhiễu output).

Quy trình seed: `parse_*.py` → `data/*.json` → `seed_nutrition.py` → `create_tables.py` → `migrate_dishes_v2.py` → `seed_conversion_rates.py` → `generate_embeddings.py`.

## Cấu trúc code

- `backend/main.py` — FastAPI app + `include_router`. Router: chat, analyze, **dishes**.
- `backend/api/` — endpoint (analyzer pattern). `dishes.py` có 4 endpoint 2-tier, dùng `Depends(get_session)`.
- `backend/services/` — business logic: `embeddings`, `ingredients` (2-tier search), `conversions` (mL→g), `dishes` (lookup/compute/contribute).
- `backend/db/models.py` — ORM: `NutritionIngredient` (per-gram, có `embedding Vector(1024)`), `Dish` (status/contributor_id/usage_count), `DishIngredient`, `ConversionRate`.
- `backend/db/postgres.py` — `get_session()` async, `async_session`.
- `schemas/` — Pydantic ở ROOT (không trong backend/). `nutrition.py` có `calculate_*()` (toán, tái dùng), `dish.py` cho 2-tier.
- `ml/inference/` — `cv.py` (ResNet50 local, output dish_name), `vision.py` (Qwen3.7 cloud, output dish_name + ingredients + gram).
- `scripts/` — migrate/seed. **KHÔNG có Alembic** — schema đổi bằng `Base.metadata.create_all` (chỉ tạo mới) + `migrate_dishes_v2.py` (ALTER idempotent cho bảng cũ).
- `data/` — `usda_ingredients.json` (8060), `vn_foods.json` (2088: 838 `vnfood` + 1250 `vnmeal`).

## 2-tier dish lookup (kiến trúc chính)

- Tier 1 `GET /dishes/lookup`: institute (`source=vnmeal`) ưu tiên → fallback user-recipe (`dishes` JOIN `dish_ingredients`). `exists=false` → Tier 2.
- Tier 2 `POST /dishes` (contribute) + `POST /dishes/compute` (preview không lưu).
- `GET /ingredients/search`: ILIKE trước, vector fallback (`cosine_distance` — lần đầu codebase dùng pgvector).
- Tái dùng `calculate_ingredient_nutrition()` + `calculate_totals()` từ `schemas/nutrition.py`, KHÔNG viết lại toán.

## Lưu ý quan trọng

- `dish_name` UNIQUE → contribute trùng → HTTP 409.
- ILIKE phân biệt dấu tiếng Việt: user gõ "suon" KHÔNG móc "sườn" (chỉ vector giúp). Pha 2 cần normalize dấu.
- `conversion_assumed` flag gần như không bao giờ báo vì có fallback nước (rate NULL=1.0).
- Pha 2 chưa làm: trust-score + versioning (`dish_recipes`), tăng `usage_count` khi lookup, admin verify recipe.
- Plan đầy đủ 2-tier: `/Users/nguyenhailong/.claude/plans/frolicking-waddling-journal.md`.

## Conventions

- Commit: `<type>: <description>` (feat/fix/refactor/docs/test/chore/perf/ci). Không ghi Co-Authored-By.
- Code: immutable, KISS/DRY/YAGNI, file 200-400 dòng, hàm <50 dòng.
- Test: TDD, coverage 80%+. (FoodAI chưa có test — chưa setup pytest.)
- Error handling: bắt hết, thông báo thân thiện UI, log chi tiết server.