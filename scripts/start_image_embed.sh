#!/bin/bash
# Khởi động SigLIP 2 image embedding sidecar (:8082) cho FoodAI
# Usage: bash scripts/start_image_embed.sh

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$LOG_DIR"

echo "🚀 Starting image embedding server..."

cd "$PROJECT_ROOT" || exit 1
uv run uvicorn ml.serving.image_embed_server:app \
    --host 0.0.0.0 \
    --port 8082 \
    > "$LOG_DIR/image-embed.log" 2>&1 &
echo "   Image embedding server starting on :8082"

echo ""
echo "⏳ Waiting for server to be ready..."
for i in {1..30}; do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8082/health 2>/dev/null)" = "200" ]; then
        echo "✅ Image embedding server is ready!"
        exit 0
    fi
    sleep 1
done
echo "⚠️  Timeout waiting for server. Check log: $LOG_DIR/image-embed.log"
