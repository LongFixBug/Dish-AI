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

echo "▶ 1/7  Data stores (postgres :5432, qdrant :6333)"
if port_open 5432 && port_open 6333; then
  echo "   ⏭  đã chạy sẵn"
else
  docker compose up -d postgres qdrant
  wait_for_port 5432 postgres
  wait_for_port 6333 qdrant
fi

echo "▶ 2/7  Migrations"
DEBUG=false uv run python -m alembic upgrade head

echo "▶ 3/7  Sticker segmentation (:8083)"
if port_open 8083; then
  echo "   ⏭  đã chạy sẵn"
else
  bash scripts/start_segment.sh
  wait_for_port 8083 segment
fi

echo "▶ 4/7  llama.cpp (LLM :8080, embedding :8081)"
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

echo "▶ 5/7  Food Gate (:8084)"
if port_open 8084; then
  echo "   ⏭  đã chạy sẵn"
else
  DEBUG=false FOOD_GATE_CHECKPOINT_PATH="$ROOT/checkpoints/food_gate/siglip2_food_gate_best.pt" \
    nohup "$ROOT/.venv/bin/python" -m uvicorn ml.inference.food_gate:app \
      --host 127.0.0.1 --port 8084 > "$LOG_DIR/food_gate.log" 2>&1 &
  echo $! > "$RUN_DIR/food_gate.pid"
  wait_for_port 8084 food-gate 90
fi

echo "▶ 6/7  SigLIP food hint (:8085)"
if port_open 8085; then
  echo "   ⏭  đã chạy sẵn"
else
  DEBUG=false \
    SIGLIP_FOOD_V1_ENCODER_DIR="$ROOT/checkpoints/siglip_food_v1/encoder" \
    SIGLIP_FOOD_V1_CLASSIFIER_HEAD_PATH="$ROOT/checkpoints/siglip_food_v1/classifier_head.pt" \
    nohup "$ROOT/.venv/bin/python" -m uvicorn ml.inference.siglip_food_v1:app \
      --host 127.0.0.1 --port 8085 > "$LOG_DIR/food_hint.log" 2>&1 &
  echo $! > "$RUN_DIR/food_hint.pid"
  wait_for_port 8085 food-hint 90
fi

echo "▶ 7/7  API (:8000)"
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
  Food Gate http://127.0.0.1:8084
  Hint     http://127.0.0.1:8085
  Log      $LOG_DIR/api.log
  Smoke    bash scripts/smoke_test.sh
  Dừng     bash scripts/dev_down.sh
──────────────────────────────────────────────
EOF
