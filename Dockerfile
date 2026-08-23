# Multi-stage production image for Render (Gyansetu-style).
# Builds Next.js static export, then serves API + UI from one FastAPI process.

# ---------------------------------------------------------------------------
# Stage 1: Frontend (Next.js → static `out/`)
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
# Same-origin /api on Render — no rewrite target needed at build time
ENV NEXT_OUTPUT=export
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Backend + static UI
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Slim Render deps (Gemini + FastEmbed ONNX — no torch)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Baked Next.js static export (served by FastAPI when present)
COPY --from=frontend-builder /app/frontend/out /app/static

RUN mkdir -p /app/data/pdfs /app/data/excel /app/chroma_db \
    && chmod +x /app/scripts/render_start.sh

EXPOSE 10000

# Render injects $PORT; default 10000 matches Gyansetu convention
CMD ["sh", "/app/scripts/render_start.sh"]
