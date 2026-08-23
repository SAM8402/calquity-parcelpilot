"""Embedding backends: Google Gemini first, local FastEmbed fallback.

Collections are backend-specific so Google (API) and local (ONNX) vectors
never mix. Active backend is persisted under chroma_db/.embedding_backend.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, List, Optional

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
_backend: Optional[str] = None  # "google" | "local" | "hash"


class HashEmbeddings(Embeddings):
    """Deterministic no-dependency fallback (last resort). Dim=384."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        raw = (text or "").encode("utf-8")
        for i in range(0, max(len(raw), 1), 16):
            digest = hashlib.sha256(raw[i : i + 32] or b"\0").digest()
            for j, b in enumerate(digest):
                vec[(i + j) % self.dim] += (b / 255.0) - 0.5
        # L2 normalize
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)


def _backend_marker_path():
    return CHROMA_DIR / ".embedding_backend"


def read_active_backend() -> Optional[str]:
    path = _backend_marker_path()
    if path.is_file():
        val = path.read_text(encoding="utf-8").strip().lower()
        if val in {"google", "local", "hash"}:
            return val
    return None


def write_active_backend(name: str) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _backend_marker_path().write_text(name, encoding="utf-8")


def collection_name_for(backend: str) -> str:
    return f"parcelpilot_docs_{backend}"


def _google_embeddings() -> Embeddings:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")
    emb = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )
    # Probe once — fails fast on quota/network
    emb.embed_query("ping")
    return emb


class FastEmbedLocalEmbeddings(Embeddings):
    """Thin wrapper around fastembed.TextEmbedding (avoids broken LangChain probe)."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [list(v) for v in self._model.embed(texts or [""])]

    def embed_query(self, text: str) -> List[float]:
        # Prefer query_embed when available (retrieval-optimized)
        if hasattr(self._model, "query_embed"):
            return list(next(self._model.query_embed(text or "")))
        return list(next(self._model.embed([text or ""])))


def _local_embeddings() -> Embeddings:
    """Prefer FastEmbed (ONNX, no torch). Fall back to HashEmbeddings."""
    model = LOCAL_EMBEDDING_MODEL
    try:
        emb = FastEmbedLocalEmbeddings(model_name=model)
        emb.embed_query("ping")
        logger.info("Local embeddings via FastEmbed: %s", model)
        return emb
    except Exception as e_fast:
        logger.warning(
            "FastEmbed unavailable (%s); using HashEmbeddings last-resort", e_fast
        )
        return HashEmbeddings()


def _build_embeddings(prefer_local: bool = False) -> tuple[Embeddings, str]:
    """Return (embeddings, backend_name)."""
    forced = (EMBEDDING_BACKEND or "auto").strip().lower()

    order: list[str]
    if forced in {"google", "local", "hash"}:
        order = [forced]
    elif prefer_local or EMBEDDING_PREFER_LOCAL:
        order = ["local", "google", "hash"]
    else:
        order = ["google", "local", "hash"]

    errors: list[str] = []
    for name in order:
        try:
            if name == "google":
                return _google_embeddings(), "google"
            if name == "local":
                return _local_embeddings(), "local"
            if name == "hash":
                logger.warning("Using HashEmbeddings last-resort backend")
                return HashEmbeddings(), "hash"
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.warning("Embedding backend %s failed: %s", name, e)

    raise RuntimeError("All embedding backends failed: " + " | ".join(errors))


def get_embeddings(force_rebuild: bool = False) -> tuple[Embeddings, str]:
    """Process-wide singleton embeddings + backend name."""
    global _embeddings, _backend
    with _lock:
        if _embeddings is not None and _backend and not force_rebuild:
            return _embeddings, _backend

        # Always honor the backend the on-disk index was built with.
        # EMBEDDING_PREFER_LOCAL only applies when choosing a backend for a new index.
        stored = read_active_backend()
        if stored == "google":
            prefer_local = False
            order_forced = "google"
        elif stored == "local":
            prefer_local = True
            order_forced = "local"
        elif stored == "hash":
            prefer_local = False
            order_forced = "hash"
        else:
            prefer_local = EMBEDDING_PREFER_LOCAL
            order_forced = None

        if order_forced and (EMBEDDING_BACKEND or "auto").strip().lower() == "auto":
            try:
                if order_forced == "google":
                    emb, backend = _google_embeddings(), "google"
                elif order_forced == "local":
                    emb, backend = _local_embeddings(), "local"
                else:
                    emb, backend = HashEmbeddings(), "hash"
            except Exception as e:
                logger.warning(
                    "Stored embedding backend %s failed (%s); falling back",
                    order_forced,
                    e,
                )
                emb, backend = _build_embeddings(prefer_local=prefer_local)
        else:
            emb, backend = _build_embeddings(prefer_local=prefer_local)

        _embeddings = emb
        _backend = backend
        logger.info("Active embedding backend: %s", backend)
        return _embeddings, _backend


def reset_embeddings_cache() -> None:
    global _embeddings, _backend
    with _lock:
        _embeddings = None
        _backend = None
