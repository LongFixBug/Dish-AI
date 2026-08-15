#!/bin/sh
set -eu

checkpoint_path="${FOOD_GATE_CHECKPOINT_PATH:-/app/checkpoints/food_gate/siglip2_food_gate_best.pt}"

download_s3_object() {
    destination="$1"
    object_key="$2"
    mkdir -p "$(dirname "$destination")"
    python - "$destination" "$object_key" <<'PY'
import os
import sys

import boto3

destination = sys.argv[1]
object_key = sys.argv[2]
client = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT_URL"],
    region_name=os.environ.get("S3_REGION") or "us-east-1",
    aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
)
temporary = f"{destination}.part"
client.download_file(os.environ["S3_BUCKET"], object_key, temporary)
os.replace(temporary, destination)
PY
}

if [ ! -s "$checkpoint_path" ]; then
    : "${FOOD_GATE_CHECKPOINT_S3_KEY:?FOOD_GATE_CHECKPOINT_S3_KEY is required}"
    : "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL is required}"
    : "${S3_BUCKET:?S3_BUCKET is required}"
    : "${S3_ACCESS_KEY_ID:?S3_ACCESS_KEY_ID is required}"
    : "${S3_SECRET_ACCESS_KEY:?S3_SECRET_ACCESS_KEY is required}"
    echo "Downloading Food Gate checkpoint..."
    download_s3_object "$checkpoint_path" "$FOOD_GATE_CHECKPOINT_S3_KEY"
fi

siglip_encoder="${SIGLIP_FOOD_V1_ENCODER_DIR:-/app/checkpoints/siglip_food_v1/encoder}"
siglip_head="${SIGLIP_FOOD_V1_CLASSIFIER_HEAD_PATH:-/app/checkpoints/siglip_food_v1/classifier_head.pt}"
siglip_artifact="${SIGLIP_FOOD_V1_ARTIFACT_PATH:-/app/checkpoints/siglip_food_v1/siglip_food_v1.tar.gz}"
siglip_key="${SIGLIP_FOOD_V1_ARTIFACT_S3_KEY:-}"

if [ -n "$siglip_key" ] && [ ! -s "$siglip_encoder/model.safetensors" ]; then
    : "${SIGLIP_FOOD_V1_ARTIFACT_SHA256:?SIGLIP_FOOD_V1_ARTIFACT_SHA256 is required}"
    echo "Downloading SigLIP food-hint artifact..."
    download_s3_object "$siglip_artifact" "$siglip_key"
    SIGLIP_ARTIFACT="$siglip_artifact" SIGLIP_SHA256="$SIGLIP_FOOD_V1_ARTIFACT_SHA256" \
        SIGLIP_ROOT="$(dirname "$siglip_encoder")" python - <<'PY'
import hashlib
import os
import tarfile
from pathlib import Path

archive = Path(os.environ["SIGLIP_ARTIFACT"])
expected = os.environ["SIGLIP_SHA256"].strip().lower()
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("SigLIP artifact checksum mismatch")

root = Path(os.environ["SIGLIP_ROOT"]).resolve()
root.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    for member in members:
        target = (root / member.name).resolve()
        if target != root and root not in target.parents:
            raise SystemExit("Unsafe SigLIP artifact path")
    bundle.extractall(root)
PY
fi

exec uvicorn ml.serving.ml_sidecar:app --host 0.0.0.0 --port "${PORT:-8084}"
