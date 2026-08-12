#!/usr/bin/env bash
# Khởi động toàn bộ FoodAI cho môi trường dev, bỏ qua thứ đã chạy sẵn.
#
#   bash scripts/dev_up.sh            # bật hết
#   bash scripts/dev_up.sh --no-llm   # bỏ llama.cpp (đủ để test API + catalog)
#
# Dừng lại: bash scripts/dev_down.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
RUN_DIR="$ROOT/logs/run"
mkdir -p "$LOG_DIR" "$RUN_DIR"

WITH_LLM=1
[ "${1:-}" = "--no-llm" ] && WITH_LLM=0

port_open() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }

wait_for_port() {
  local port=$1 name=$2 tries=${3:-60}
  for _ in $(seq "$tries"); do
    if port_open "$port"; then
      echo "   ✅ $name (:$port)"
      return 0
    fi
    sleep 1
  done
  echo "   ❌ $name (:$port) chưa lên sau ${tries}s"
  return 1
}

echo "▶ 1/5  Data stores (postgres :5432, qdrant :6333)"
if port_open 5432 && port_open 6333; then
  echo "   ⏭  đã chạy sẵn"
else
  docker compose up -d postgres qdrant
  wait_for_port 5432 postgres
  wait_for_port 6333 qdrant
fi

echo "▶ 2/5  Migrations"
DEBUG=false uv run python -m alembic upgrade head

echo "▶ 3/5  Sticker segmentation (:8083)"
if port_open 8083; then
  echo "   ⏭  đã chạy sẵn"
else
  bash scripts/start_segment.sh
  wait_for_port 8083 segment
fi

echo "▶ 4/5  llama.cpp (LLM :8080, embedding :8081)"
if [ "$WITH_LLM" = "0" ]; then
  echo "   ⏭  bỏ qua theo --no-llm"
elif port_open 8080 && port_open 8081; then
  echo "   ⏭  đã chạy sẵn"
elif ! command -v llama-server >/dev/null 2>&1; then
  echo "   ⚠️  không thấy llama-server trong PATH — bỏ qua."
  echo "      Semantic search sẽ hụt, tra cứu chính xác vẫn chạy."
else
  bash scripts/start_llama.sh
fi

echo "▶ 5/5  API (:8000)"
if port_open 8000; then
  echo "   ⏭  đã chạy sẵn"
else
  # Pydantic ưu tiên biến đã export trong terminal hơn file .env. Xóa riêng
  # các biến SigLIP local đã cũ để API dev luôn đọc mode hiện tại từ .env.
  # Không thay đổi quy tắc này cho production/deploy environment.
  unset "SIGLIP_FOOD_HINT_MODE"
  unset "SIGLIP_FOOD_HINT_URL"
  unset "SIGLIP_FOOD_HINT_TIMEOUT_SECONDS"
  unset "SIGLIP_FOOD_HINT_TOP_K"
  unset "SIGLIP_FOOD_HINT_MIN_SCORE"

  # --timeout-graceful-shutdown: request treo (vd Vision cloud chậm) không được
  # phép kẹt vòng reload/shutdown vô hạn như từng gặp 26/7.
  DEBUG=false nohup "$ROOT/.venv/bin/python" -m uvicorn backend.main:app --reload --port 8000 \
    --timeout-graceful-shutdown 5 \
    > "$LOG_DIR/api.log" 2>&1 &
  echo $! > "$RUN_DIR/api.pid"
  wait_for_port 8000 api
fi

echo
echo "▶ Readiness"
curl -s http://127.0.0.1:8000/ready | python3 -m json.tool 2>/dev/null \
  || echo "   ❌ /ready không trả JSON — xem $LOG_DIR/api.log"

cat <<EOF

──────────────────────────────────────────────
  API      http://127.0.0.1:8000
  Docs     http://127.0.0.1:8000/docs
  Sticker  http://127.0.0.1:8083
  Log      $LOG_DIR/api.log
  Smoke    bash scripts/smoke_test.sh
  Dừng     bash scripts/dev_down.sh
──────────────────────────────────────────────
EOF
