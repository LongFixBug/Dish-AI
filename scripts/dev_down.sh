#!/usr/bin/env bash
# Dừng những gì dev_up.sh đã bật. Data trong docker volume vẫn giữ nguyên.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/logs/run"

if [ -f "$RUN_DIR/api.pid" ]; then
  kill "$(cat "$RUN_DIR/api.pid")" 2>/dev/null && echo "🛑 api"
  rm -f "$RUN_DIR/api.pid"
fi

if [ -f "$RUN_DIR/segment.pid" ]; then
  kill "$(cat "$RUN_DIR/segment.pid")" 2>/dev/null && echo "🛑 segment"
  rm -f "$RUN_DIR/segment.pid"
fi

if [ -f "$RUN_DIR/food_gate.pid" ]; then
  kill "$(cat "$RUN_DIR/food_gate.pid")" 2>/dev/null && echo "🛑 food-gate"
  rm -f "$RUN_DIR/food_gate.pid"
fi

if [ -f "$RUN_DIR/food_hint.pid" ]; then
  kill "$(cat "$RUN_DIR/food_hint.pid")" 2>/dev/null && echo "🛑 food-hint"
  rm -f "$RUN_DIR/food_hint.pid"
fi

pkill -f "llama-server --model" 2>/dev/null && echo "🛑 llama.cpp"

docker compose stop postgres qdrant >/dev/null 2>&1 && echo "🛑 postgres + qdrant"

echo "✅ Đã dừng. Dữ liệu trong docker volume không bị xoá."
