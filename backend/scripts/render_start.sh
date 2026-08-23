#!/bin/sh
# Render / Docker entrypoint — ensure data indexes exist, then start uvicorn.
set -e

cd /app

if [ ! -f /app/parcelpilot.duckdb ] || [ ! -d /app/chroma_db ] || [ -z "$(ls -A /app/chroma_db 2>/dev/null)" ]; then
  echo "[render_start] DuckDB/Chroma missing — running setup_db.py (needs GOOGLE_API_KEY)..."
  python -m app.setup_db
else
  echo "[render_start] DuckDB + Chroma present — skipping setup."
fi

PORT="${PORT:-10000}"
echo "[render_start] Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
