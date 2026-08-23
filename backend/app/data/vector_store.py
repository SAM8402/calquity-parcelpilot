import sys
import logging
import threading
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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
    """Cached Chroma handle — rebuilds embeddings+client once per process."""
    global _vectorstore, _vs_backend
    with _lock:
        emb, backend = get_embeddings(force_rebuild=force_rebuild)
        if (
            _vectorstore is not None
            and _vs_backend == backend
            and not force_rebuild
        ):
            return _vectorstore

        collection = collection_name_for(backend)
        vs = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=emb,
            collection_name=collection,
        )
        _vectorstore = vs
        _vs_backend = backend
        # Remember which backend the running process is using
        if read_active_backend() != backend:
            # Do not overwrite ingest marker if index was built with another
            # backend — only write when empty / matching rebuild paths.
            if read_active_backend() is None:
                write_active_backend(backend)
        logger.info(
            "Vectorstore ready backend=%s collection=%s", backend, collection
        )
        return _vectorstore


def reset_vectorstore_cache() -> None:
    global _vectorstore, _vs_backend
    with _lock:
        _vectorstore = None
        _vs_backend = None


def get_retriever(k: int = 4):
    return get_vectorstore().as_retriever(search_kwargs={"k": k})


def search_with_metadata(query: str, k: int = 4, filter_dict: dict = None):
    vectorstore = get_vectorstore()
    kwargs = {"k": k}
    if filter_dict:
        kwargs["filter"] = filter_dict
    return vectorstore.similarity_search_with_score(query, **kwargs)
