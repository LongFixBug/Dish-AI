#!/bin/sh
set -eu

MODEL_DIR=/app/models
MODEL_FILE="$MODEL_DIR/Qwen3-Embedding-0.6B.Q4_K_M.gguf"
EMBED_PORT=8081

mkdir -p "$MODEL_DIR"

# Rate-limit counters are ephemeral. Keep this bounded Redis process beside
# the single API replica; image recognition is handled by the Vision API.
echo "Starting bounded local Redis rate limiter..."
redis-server \
  --bind 127.0.0.1 \
  --port 6379 \
  --save "" \
  --appendonly no \
  --maxmemory 16mb \
  --maxmemory-policy allkeys-lru \
  > /proc/1/fd/1 2>&1 &

if [ ! -s "$MODEL_FILE" ]; then
  echo "Downloading embedding model..."
  wget -q \
    -O "$MODEL_FILE" \
    "https://huggingface.co/mradermacher/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B.Q4_K_M.gguf"
fi

echo "Starting llama.cpp embedding server..."
/opt/llama/llama-server \
  --model "$MODEL_FILE" \
  --embedding \
  --host 127.0.0.1 \
  --port "$EMBED_PORT" \
  --ctx-size 256 \
  --parallel 1 \
  --batch-size 256 \
  --ubatch-size 256 \
  > /proc/1/fd/1 2>&1 &

echo "FastAPI starting while embedding model loads in background."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
