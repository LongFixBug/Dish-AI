# RunPod GPU sidecar: Food Gate + SigLIP Food Hint

RunPod hosts only the two image models. Railway remains the public FoodAI API,
database, Qdrant, Redis, Vision, and mobile backend.

The sidecar exposes these existing contracts on HTTP port `8080`:

- `POST /predict` — Food Gate, protected by `X-Food-Gate-Token`.
- `POST /siglip/predict` — SigLIP Food Hint, protected by the same header.
- `GET /ready` and `GET /siglip/ready` — readiness probes.

## 1. Publish the GPU image

The simplest path is the manual GitHub Actions workflow **Publish RunPod GPU
image**. It builds an AMD64 image on GitHub's Linux runner and publishes:

```text
ghcr.io/longfixbug/dish-ai:runpod-v1
```

This avoids relying on a local Docker daemon. If the package is not public,
change its visibility in GitHub Packages before creating the Pod. An equivalent
manual build is:

```bash
export IMAGE=ghcr.io/longfixbug/dish-ai:runpod-v1
docker buildx build --platform linux/amd64 \
  -f Dockerfile.runpod-ml \
  -t "$IMAGE" \
  --push .
```

Make the GHCR package public, or configure its registry credentials in the
RunPod template. Do not put registry passwords, S3 credentials, or service
tokens in Git.

## 2. Create a RunPod Pod

Create a Pod from the image above with an NVIDIA GPU having at least 16 GB
VRAM (T4, L4, RTX 4090, or equivalent), then expose **HTTP port 8080**. The
Pod HTTP proxy URL is shaped like:

```text
https://POD_ID-8080.proxy.runpod.net
```

Set the following Pod environment variables in the RunPod dashboard. Use new
random values for `SIDE_CAR_TOKEN`; the example values are placeholders only.

```dotenv
PORT=8080
FOOD_GATE_DEVICE=cuda
FOOD_GATE_BLOCK_THRESHOLD=0.90
FOOD_GATE_MAX_CONCURRENCY=1
FOOD_GATE_SERVICE_TOKEN=SIDE_CAR_TOKEN

SIGLIP_FOOD_V1_DEVICE=cuda
SIGLIP_FOOD_V1_WARM_ON_STARTUP=true
SIGLIP_FOOD_V1_MAX_CONCURRENCY=1
SIGLIP_FOOD_V1_SERVICE_TOKEN=SIDE_CAR_TOKEN

FOOD_GATE_CHECKPOINT_S3_KEY=YOUR_EXISTING_FOOD_GATE_OBJECT_KEY
SIGLIP_FOOD_V1_ARTIFACT_S3_KEY=YOUR_EXISTING_SIGLIP_ARTIFACT_OBJECT_KEY
SIGLIP_FOOD_V1_ARTIFACT_SHA256=YOUR_EXISTING_SIGLIP_ARTIFACT_SHA256
S3_ENDPOINT_URL=YOUR_EXISTING_S3_ENDPOINT
S3_REGION=us-east-1
S3_BUCKET=YOUR_EXISTING_BUCKET
S3_ACCESS_KEY_ID=YOUR_EXISTING_ACCESS_KEY
S3_SECRET_ACCESS_KEY=YOUR_EXISTING_SECRET
```

`SIGLIP_FOOD_V1_WARM_ON_STARTUP=true` is mandatory for this Pod: the sidecar
does not report ready until both Food Gate and SigLIP are loaded on the GPU.

## 3. Point Railway API to the Pod

Only after `/ready` and `/siglip/ready` both respond with `ready`, replace the
following variables in Railway service **Dish-AI**:

```dotenv
FOOD_GATE_MODE=enforce
FOOD_GATE_URL=https://POD_ID-8080.proxy.runpod.net
FOOD_GATE_SERVICE_TOKEN=SIDE_CAR_TOKEN
FOOD_GATE_TIMEOUT_SECONDS=5

SIGLIP_FOOD_HINT_MODE=hint
SIGLIP_FOOD_HINT_URL=https://POD_ID-8080.proxy.runpod.net/siglip
SIGLIP_FOOD_HINT_SERVICE_TOKEN=SIDE_CAR_TOKEN
SIGLIP_FOOD_HINT_TIMEOUT_SECONDS=5
```

Never paste these values in `.env.production.example`, the README, issue
comments, or screenshots.

## 4. Validate before mobile testing

From a machine that has access to the Pod, use an actual JPEG/PNG file and the
token only from your shell environment:

```bash
curl -fsS -H "X-Food-Gate-Token: $SIDE_CAR_TOKEN" \
  -F "file=@data/eval/images/food_gate_real_eval/food/example.jpg;type=image/jpeg" \
  https://POD_ID-8080.proxy.runpod.net/predict

curl -fsS -H "X-Food-Gate-Token: $SIDE_CAR_TOKEN" \
  -F "file=@data/eval/images/food_gate_real_eval/food/example.jpg;type=image/jpeg" \
  https://POD_ID-8080.proxy.runpod.net/siglip/predict
```

Then upload one food and one non-food image through the Android app. The
non-food request must return `422 non_food_image` without a Vision call;
the food request must produce a Vision result after both sidecar calls.
