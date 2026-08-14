#!/bin/sh
set -eu

checkpoint_path="${FOOD_GATE_CHECKPOINT_PATH:-/app/checkpoints/food_gate/siglip2_food_gate_best.pt}"

if [ ! -s "$checkpoint_path" ]; then
    : "${FOOD_GATE_CHECKPOINT_S3_KEY:?FOOD_GATE_CHECKPOINT_S3_KEY is required}"
    : "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL is required}"
    : "${S3_BUCKET:?S3_BUCKET is required}"
    : "${S3_ACCESS_KEY_ID:?S3_ACCESS_KEY_ID is required}"
    : "${S3_SECRET_ACCESS_KEY:?S3_SECRET_ACCESS_KEY is required}"
    mkdir -p "$(dirname "$checkpoint_path")"
    echo "Downloading Food Gate checkpoint..."
    python - "$checkpoint_path" <<'PY'
import os
import sys

import boto3

destination = sys.argv[1]
client = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT_URL"],
    region_name=os.environ.get("S3_REGION") or "us-east-1",
    aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
)
temporary = f"{destination}.part"
client.download_file(
    os.environ["S3_BUCKET"],
    os.environ["FOOD_GATE_CHECKPOINT_S3_KEY"],
    temporary,
)
os.replace(temporary, destination)
PY
fi

exec uvicorn ml.serving.ml_sidecar:app --host 0.0.0.0 --port "${PORT:-8084}"
