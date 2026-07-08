#!/bin/bash
# Tải GGUF models cho FoodAI
# Yêu cầu: brew install huggingface-cli (hoặc dùng wget/curl fallback)

set -e

MODELS_DIR="$(cd "$(dirname "$0")/../models" && pwd)"

echo "📁 Models directory: $MODELS_DIR"
echo ""

# ─── Qwen2.5 7B Instruct (LLM) ───────────────────────────────────────
# Q4_K_M — cân bằng tốt giữa chất lượng và tốc độ trên Mac Metal
LLM_MODEL="Qwen/Qwen2.5-7B-Instruct-GGUF"
LLM_FILE="qwen2.5-7b-instruct-q4_k_m.gguf"
LLM_URL="https://huggingface.co/${LLM_MODEL}/resolve/main/${LLM_FILE}"

echo "📥 Downloading Qwen2.5 7B Instruct (Q4_K_M)..."
echo "   Size: ~4.7 GB — có thể mất 5-15 phút tùy mạng"
echo ""

if [ -f "$MODELS_DIR/$LLM_FILE" ]; then
    echo "   ✅ Đã có sẵn, bỏ qua."
else
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download "$LLM_MODEL" "$LLM_FILE" --local-dir "$MODELS_DIR"
    else
        # Fallback: dùng wget hoặc curl
        if command -v wget &> /dev/null; then
            wget -O "$MODELS_DIR/$LLM_FILE" "$LLM_URL"
        else
            curl -L -o "$MODELS_DIR/$LLM_FILE" "$LLM_URL"
        fi
    fi
    echo "   ✅ Đã tải xong!"
fi

echo ""

# ─── Qwen3-Embedding 0.6B (Embedding) ────────────────────────────────
EMBED_MODEL="Qwen/Qwen3-Embedding-0.6B-GGUF"
EMBED_FILE="qwen3-embedding-0.6b-q4_k_m.gguf"
EMBED_URL="https://huggingface.co/${EMBED_MODEL}/resolve/main/${EMBED_FILE}"

echo "📥 Downloading Qwen3-Embedding 0.6B (Q4_K_M)..."
echo "   Size: ~400 MB"
echo ""

if [ -f "$MODELS_DIR/$EMBED_FILE" ]; then
    echo "   ✅ Đã có sẵn, bỏ qua."
else
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download "$EMBED_MODEL" "$EMBED_FILE" --local-dir "$MODELS_DIR"
    else
        if command -v wget &> /dev/null; then
            wget -O "$MODELS_DIR/$EMBED_FILE" "$EMBED_URL"
        else
            curl -L -o "$MODELS_DIR/$EMBED_FILE" "$EMBED_URL"
        fi
    fi
    echo "   ✅ Đã tải xong!"
fi

echo ""
echo "🎉 Hoàn tất! Models đã sẵn sàng trong $MODELS_DIR"
ls -lh "$MODELS_DIR"/*.gguf
