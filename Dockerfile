# syntax=docker/dockerfile:1
# --- Web app (PWA) -----------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- API + static files ------------------------------------------------------
FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv==0.9.*
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist /app/static
ENV PATH="/app/backend/.venv/bin:$PATH" \
    RAAGA_STATIC_DIR=/app/static \
    RAAGA_STORE_DIR=/data/store \
    RAAGA_RAGA_TABLE=/app/backend/data/ragas.json \
    PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn raaga.api.app:app_from_env --factory --host 0.0.0.0 --port ${PORT:-8080}"]
