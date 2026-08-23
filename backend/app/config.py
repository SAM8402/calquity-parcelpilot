import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Prefer project-root .env (where user pastes Gemini keys)
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ROOT_ENV)
load_dotenv(_BACKEND_ENV, override=False)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
EXCEL_DIR = DATA_DIR / "excel"
CHROMA_DIR = BASE_DIR / "chroma_db"
DB_PATH = BASE_DIR / "parcelpilot.duckdb"


def _parse_cors(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return ["http://localhost:3000"]
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [o.strip() for o in raw.split(",") if o.strip()]


def _parse_api_keys(raw: str) -> list[str]:
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
API_KEYS = _parse_api_keys(GOOGLE_API_KEY)
# Prefer a standard Google AI Studio key if a comma-separated list was pasted
if API_KEYS:
    preferred = next((k for k in API_KEYS if k.startswith("AIza")), API_KEYS[0])
    GOOGLE_API_KEY = preferred

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LLM_FALLBACK_CHAIN = os.getenv("LLM_FALLBACK_CHAIN", "")
# Google embeddings (API) — tried first unless EMBEDDING_PREFER_LOCAL=true
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
# Local ONNX FastEmbed model (no torch). Used when Google fails / prefer local.
# FastEmbed ids: BAAI/bge-small-en-v1.5, sentence-transformers/all-MiniLM-L6-v2
LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
)
# auto | google | local | hash
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "auto")
# Prefer local for faster doc search (skips Google embed API round-trip)
EMBEDDING_PREFER_LOCAL = os.getenv("EMBEDDING_PREFER_LOCAL", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

CORS_ORIGINS = _parse_cors(
    os.getenv("CORS_ORIGINS", '["http://localhost:3000","http://localhost:8080","*"]')
)

# Empty REDIS_URL → fakeredis in-process (Render / free deploy, Gyansetu-style).
# Set REDIS_URL=redis://... only when a real Redis is available (local Docker).
_raw_redis = os.getenv("REDIS_URL", "")
REDIS_URL = (_raw_redis or "").strip()
CACHE_TTL_CHAT = int(os.getenv("CACHE_TTL_CHAT", "600"))  # 10 min
CACHE_TTL_DOCS = int(os.getenv("CACHE_TTL_DOCS", "3600"))  # 1 hour
CACHE_TTL_DATA = int(os.getenv("CACHE_TTL_DATA", "300"))  # 5 min


def fallback_models() -> list[str]:
    if not LLM_FALLBACK_CHAIN:
        return []
    return [m.strip() for m in LLM_FALLBACK_CHAIN.split(",") if m.strip()]
