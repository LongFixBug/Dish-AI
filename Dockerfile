FROM ghcr.io/ggml-org/llama.cpp:server AS llama_runtime

FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LD_LIBRARY_PATH=/opt/llama

WORKDIR /app

COPY --from=llama_runtime /app /opt/llama

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends wget ca-certificates libgomp1 redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.api.lock .
RUN pip install --no-cache-dir -r requirements.api.lock \
    && groupadd --system foodai \
    && useradd --system --gid foodai --home-dir /app foodai

COPY backend ./backend
COPY schemas ./schemas
COPY data/vn_nutrition_reference_targets.json ./data/vn_nutrition_reference_targets.json
COPY ml/__init__.py ml/model_registry.py ./ml/
COPY ml/inference ./ml/inference
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts/start_railway.sh ./scripts/start_railway.sh
RUN mkdir -p /app/data/uploads /app/data/feedback_objects \
    && chmod +x /app/scripts/start_railway.sh \
    && chown -R foodai:foodai /app /opt/llama

USER foodai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=2)"]

CMD ["sh", "-c", "exec /app/scripts/start_railway.sh"]
