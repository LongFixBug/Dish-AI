#!/usr/bin/env bash
# Khởi động SigLIP 2 image embedding sidecar (:8082) cho FoodAI
# Usage: bash scripts/start_image_embed.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
RUN_DIR="$LOG_DIR/run"

mkdir -p "$LOG_DIR" "$RUN_DIR"

if nc -z 127.0.0.1 8082 >/dev/null 2>&1; then
    echo "✅ Image embedding server đã chạy sẵn trên :8082"
    exit 0
fi

echo "🚀 Starting image embedding server..."

cd "$PROJECT_ROOT" || exit 1
if [ ! -x "$PROJECT_ROOT/.venv/bin/uvicorn" ]; then
    echo "❌ Chưa có .venv/bin/uvicorn — chạy 'uv sync' trước."
    exit 1
fi

# Chạy binary trong venv trực tiếp để PID ghi lại chính là server. Nếu dùng
# `uv run`, PID thuộc tiến trình bọc và có thể chết khi shell gọi script kết thúc,
# trong khi tiến trình con không còn được dev_down.sh quản lý chính xác.
nohup "$PROJECT_ROOT/.venv/bin/uvicorn" ml.serving.image_embed_server:app \
    --host 0.0.0.0 \
    --port 8082 \
    > "$LOG_DIR/image-embed.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/image_embed.pid"
echo "   Image embedding server starting on :8082"

echo ""
echo "⏳ Waiting for server to be ready..."
for _ in $(seq 1 180); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8082/health 2>/dev/null)" = "200" ]; then
        echo "✅ Image embedding server is ready!"
        exit 0
    fi
    sleep 1
done
echo "⚠️  Timeout waiting for server. Check log: $LOG_DIR/image-embed.log"
exit 1
