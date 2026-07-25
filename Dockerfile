FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.api.lock .
RUN pip install --no-cache-dir -r requirements.api.lock \
    && groupadd --system foodai \
    && useradd --system --gid foodai --home-dir /app foodai

COPY backend ./backend
COPY schemas ./schemas
COPY ml ./ml
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
RUN mkdir -p /app/data/uploads /app/data/feedback_objects \
    && chown -R foodai:foodai /app

USER foodai

ENV CV_ENABLED=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=2)"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
