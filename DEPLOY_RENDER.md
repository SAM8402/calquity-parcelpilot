# Deploy ParcelPilot on Render.com

Reference pattern: [Gyansetu](https://github.com/SAM8402/Gyansetu) — one Docker web
service, frontend baked into FastAPI, `$PORT` from Render, Redis optional.

Live Gyansetu example: https://gyansetu-626t.onrender.com

---

## What you get

| Piece | How it maps (Gyansetu → ParcelPilot) |
|-------|--------------------------------------|
| Single Docker Web Service | Root `Dockerfile` (Next static export + FastAPI) |
| Frontend inside backend | Next `out/` → `/app/static`, mounted at `/` |
| `PORT` | `uvicorn ... --port ${PORT:-10000}` via `scripts/render_start.sh` |
| Slim deps | `backend/requirements.txt` (Gemini + FastEmbed ONNX, no torch) |
| Redis optional | Empty `REDIS_URL` → **fakeredis** in-process (no Redis service) |
| First-boot data | `setup_db.py` if DuckDB/Chroma missing |

---

## Prerequisites

1. Code pushed to GitHub (public or private).
2. Google AI Studio key (`GOOGLE_API_KEY`) with Gemini access.
3. Free [Render](https://render.com) account.

---

## Option A — Blueprint (recommended)

1. Push this repo (includes `render.yaml` + `Dockerfile`).
2. Render Dashboard → **New** → **Blueprint**.
3. Connect the GitHub repo → apply `render.yaml`.
4. When prompted, set **GOOGLE_API_KEY** (secret).
5. Wait for first build. First boot runs `setup_db.py` (PDF/Excel → DuckDB + Chroma) — can take several minutes.
6. Open `https://<your-service>.onrender.com` — UI + `/api/health` on the same origin.

---

## Option B — Manual Web Service

1. **New** → **Web Service** → connect repo.
2. Settings:
   - **Runtime:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Docker context:** `.`
   - **Plan:** Free
   - **Health check path:** `/api/health`
3. Environment variables:

```
GOOGLE_API_KEY=<your key>
GEMINI_MODEL=gemini-2.5-flash
LLM_FALLBACK_CHAIN=gemini-2.5-flash,gemini-2.5-flash-lite,gemini-2.0-flash,gemini-2.0-flash-lite,gemini-2.5-pro
EMBEDDING_MODEL=models/gemini-embedding-001
CORS_ORIGINS=["*"]
REDIS_URL=
```

Leave `REDIS_URL` empty so the app uses **fakeredis** (in-memory). Do not add a Render Redis addon for the free demo.

4. Deploy. After green, test:
   - `GET https://<service>.onrender.com/api/health` — expect `"cache_backend": "fakeredis"`
   - Open the root URL and run an ORD-1001 demo question.

---

## Local check of the same image

```bash
# From repo root (WSL)
docker build -t parcelpilot .
docker run --rm -p 10000:10000 \
  -e PORT=10000 \
  -e GOOGLE_API_KEY="$GOOGLE_API_KEY" \
  -e CORS_ORIGINS='["*"]' \
  -e REDIS_URL= \
  parcelpilot
```

Then open http://127.0.0.1:10000

---

## Free-tier notes (same constraints Gyansetu documents)

- **512 MB RAM** — keep one worker; do not add torch/local embedding models.
- **Cold starts** — free instances sleep; first request after idle can take ~30–60s.
- **Ephemeral disk** — DuckDB/Chroma live on the instance filesystem; a new deploy may rebuild indexes on boot (needs `GOOGLE_API_KEY`).
- **Redis** — not required. Empty `REDIS_URL` uses **fakeredis**. Only set a real URL if you add Render Redis later.
- **Build time** — Node build + pip + first-boot ingest can approach Render’s build/start limits; if start times out, raise the start command timeout or pre-bake chroma in the image (advanced).

---

## After deploy (submission)

Add the URL to your CalQuity form and README, e.g.:

```
Live demo: https://parcelpilot-xxxx.onrender.com
```

Optional: put the same link at the top of `README.md` under a “Live Prototype” heading (Gyansetu style).
