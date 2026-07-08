#!/bin/bash
# Khởi động llama.cpp servers (LLM + Embedding) cho FoodAI
# Usage: bash scripts/start_llama.sh

MODELS_DIR="$(cd "$(dirname "$0")/../models" && pwd)"
LLM_MODEL="$MODELS_DIR/qwen2.5-7b-instruct-q4_k_m.gguf"
EMBED_MODEL="$MODELS_DIR/Qwen3-Embedding-0.6B-Q8_0.gguf"
LOG_DIR="$(cd "$(dirname "$0")/../logs" && pwd 2>/dev/null || echo "/tmp")"

mkdir -p "$LOG_DIR"

echo "🚀 Starting llama.cpp servers..."

# LLM Server (:8080)
if [ -f "$LLM_MODEL" ]; then
    llama-server \
        --model "$LLM_MODEL" \
        --host 0.0.0.0 \
        --port 8080 \
        --n-gpu-layers 99 \
        --ctx-size 4096 \
        > "$LOG_DIR/llama-llm.log" 2>&1 &
    echo "   LLM server starting on :8080"
else
    echo "   ❌ LLM model not found: $LLM_MODEL"
fi

# Embedding Server (:8081)
if [ -f "$EMBED_MODEL" ]; then
    llama-server \
        --model "$EMBED_MODEL" \
        --host 0.0.0.0 \
        --port 8081 \
        --n-gpu-layers 99 \
        --ctx-size 2048 \
        --embeddings \
        > "$LOG_DIR/llama-embed.log" 2>&1 &
    echo "   Embedding server starting on :8081"
else
    echo "   ❌ Embedding model not found: $EMBED_MODEL"
fi

echo ""
echo "⏳ Waiting for servers to be ready..."
for i in {1..30}; do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null)" = "200" ] && \
       [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/health 2>/dev/null)" = "200" ]; then
        echo "✅ Both servers are ready!"
        exit 0
    fi
    sleep 1
done
echo "⚠️  Timeout waiting for servers. Check logs: $LOG_DIR/llama-*.log"
