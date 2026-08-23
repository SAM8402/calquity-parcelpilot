"""Embedding backends: Google Gemini first, local FastEmbed fallback."""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import List, Optional

from langchain_core.embeddings import Embeddings

from app.config import (
    CHROMA_DIR,
    EMBEDDING_BACKEND,
    EMBEDDING_MODEL,
    EMBEDDING_PREFER_LOCAL,
    GOOGLE_API_KEY,
    LOCAL_EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_embeddings: Optional[Embeddings] = None
_backend: Optional[str] = None


class HashEmbeddings(Embeddings):
    """Deterministic no-dependency last resort (dim=384)."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        raw = (text or "").encode("utf-8")
        for i in range(0, max(len(raw), 1), 16):
            digest = hashlib.sha256(raw[i : i + 32] or b"\0").digest()
            for j, b in enumerate(digest):
                vec[(i + j) % self.dim] += (b / 255.0) - 0.5
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._one(text)


class FastEmbedLocalEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [list(v) for v in self._model.embed(texts or [""])]

    def embed_query(self, text: str) -> List[float]:
        if hasattr(self._model, "query_embed"):
            return list(next(self._model.query_embed(text or "")))
        return list(next(self._model.embed([text or ""])))


def _marker():
    return CHROMA_DIR / ".embedding_backend"


def read_active_backend() -> Optional[str]:
    p = _marker()
    if p.is_file():
        val = p.read_text(encoding="utf-8").strip().lower()
        if val in {"google", "local", "hash"}:
            return val
    return None


def write_active_backend(name: str) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _marker().write_text(name, encoding="utf-8")


def collection_name_for(backend: str) -> str:
    return f"parcelpilot_docs_{backend}"


def _make(name: str) -> Embeddings:
    if name == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY not set")
        emb = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL, google_api_key=GOOGLE_API_KEY
        )
        emb.embed_query("ping")
        return emb
    if name == "local":
        emb = FastEmbedLocalEmbeddings(LOCAL_EMBEDDING_MODEL)
        emb.embed_query("ping")
        return emb
    return HashEmbeddings()


def _order(prefer_local: bool) -> list[str]:
    forced = (EMBEDDING_BACKEND or "auto").strip().lower()
    if forced in {"google", "local", "hash"}:
        return [forced]
    if prefer_local:
        return ["local", "google", "hash"]
    return ["google", "local", "hash"]


def get_embeddings(force_rebuild: bool = False) -> tuple[Embeddings, str]:
    global _embeddings, _backend
    with _lock:
        if _embeddings is not None and _backend and not force_rebuild:
            return _embeddings, _backend

        stored = read_active_backend()
        if stored in {"google", "local", "hash"} and (EMBEDDING_BACKEND or "auto") == "auto":
            try:
                emb, backend = _make(stored), stored
            except Exception as e:
                logger.warning("Stored backend %s failed (%s); falling back", stored, e)
                emb, backend = None, None  # type: ignore
                for name in _order(prefer_local=(stored == "local") or EMBEDDING_PREFER_LOCAL):
                    try:
                        emb, backend = _make(name), name
                        break
                    except Exception as err:
                        logger.warning("Embedding %s failed: %s", name, err)
                if emb is None:
                    raise RuntimeError("All embedding backends failed")
        else:
            emb, backend = None, None  # type: ignore
            for name in _order(prefer_local=EMBEDDING_PREFER_LOCAL):
                try:
                    emb, backend = _make(name), name
                    break
                except Exception as err:
                    logger.warning("Embedding %s failed: %s", name, err)
            if emb is None:
                raise RuntimeError("All embedding backends failed")

        _embeddings, _backend = emb, backend
        logger.info("Active embedding backend: %s", backend)
        return _embeddings, _backend


def reset_embeddings_cache() -> None:
    global _embeddings, _backend
    with _lock:
        _embeddings = None
        _backend = None
