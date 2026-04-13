FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY ai_editor ./ai_editor
COPY pipeline ./pipeline
COPY docker/start.sh ./docker/start.sh
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/tmp/jobs && \
    chown -R app:app /app && \
    chmod +x /app/docker/start.sh

USER app

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:10000/healthz', timeout=3)"

CMD ["/app/docker/start.sh"]
