#!/bin/sh
# Render / Docker entrypoint — ensure data indexes exist, then start uvicorn.
set -e

cd /app

NEED_SETUP=0
if [ ! -f /app/parcelpilot.duckdb ]; then
  NEED_SETUP=1
fi
if [ ! -d /app/chroma_db ] || [ -z "$(ls -A /app/chroma_db 2>/dev/null)" ]; then
  NEED_SETUP=1
fi
# New embedding backend marker (google/local collections) — re-ingest if missing
if [ ! -f /app/chroma_db/.embedding_backend ]; then
  NEED_SETUP=1
fi

if [ "$NEED_SETUP" = "1" ]; then
  echo "[render_start] Data/index missing — running setup_db.py (Google embed → local fallback)..."
  python -m app.setup_db
else
  echo "[render_start] DuckDB + Chroma present (backend=$(cat /app/chroma_db/.embedding_backend)) — skipping setup."
fi

PORT="${PORT:-10000}"
echo "[render_start] Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
