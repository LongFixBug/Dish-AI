#!/bin/bash
# Khởi động sidecar tách chủ thể (:8083) cho FoodAI
# Usage: bash scripts/start_segment.sh
#
# Lần chạy đầu tiên sẽ tải model u2net (~176MB) về ~/.u2net, nên request đầu
# chậm hơn hẳn các request sau.

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
RUN_DIR="$LOG_DIR/run"

mkdir -p "$LOG_DIR" "$RUN_DIR"

if nc -z 127.0.0.1 8083 >/dev/null 2>&1; then
    echo "✅ Segmentation server đã chạy sẵn trên :8083"
    exit 0
fi

echo "🚀 Starting subject segmentation server..."

cd "$PROJECT_ROOT" || exit 1
nohup "$PROJECT_ROOT/.venv/bin/python" -m uvicorn ml.serving.segment_server:app \
    --host 0.0.0.0 \
    --port 8083 \
    > "$LOG_DIR/segment.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/segment.pid"
echo "   Segmentation server starting on :8083"

echo ""
echo "⏳ Waiting for server to be ready..."
for i in {1..30}; do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8083/health 2>/dev/null)" = "200" ]; then
        echo "✅ Segmentation server is ready!"
        exit 0
    fi
    sleep 1
done
echo "⚠️  Timeout waiting for server. Check log: $LOG_DIR/segment.log"
