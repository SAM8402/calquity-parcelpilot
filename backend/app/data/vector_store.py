import logging
import threading
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import Chroma

from app.config import CHROMA_DIR
from app.data.embeddings import (
    collection_name_for,
    get_embeddings,
    read_active_backend,
    write_active_backend,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_vectorstore: Optional[Chroma] = None
_vs_backend: Optional[str] = None


def get_vectorstore(force_rebuild: bool = False) -> Chroma:
    global _vectorstore, _vs_backend
    with _lock:
        emb, backend = get_embeddings(force_rebuild=force_rebuild)
        if _vectorstore is not None and _vs_backend == backend and not force_rebuild:
            return _vectorstore

        vs = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=emb,
            collection_name=collection_name_for(backend),
        )
        _vectorstore, _vs_backend = vs, backend
        if read_active_backend() is None:
            write_active_backend(backend)
        logger.info("Vectorstore ready backend=%s", backend)
        return _vectorstore


def reset_vectorstore_cache() -> None:
    global _vectorstore, _vs_backend
    with _lock:
        _vectorstore = None
        _vs_backend = None


def search_with_metadata(query: str, k: int = 4, filter_dict: dict = None):
    kwargs = {"k": k}
    if filter_dict:
        kwargs["filter"] = filter_dict
    return get_vectorstore().similarity_search_with_score(query, **kwargs)
