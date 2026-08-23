"""LLM factory with Gemini model/API-key fallbacks (ported from HR RAG project)."""
from __future__ import annotations

import logging
import time

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import (
    API_KEYS,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    fallback_models,
)

logger = logging.getLogger(__name__)

_combo_cache: dict[tuple[str, str], tuple[str, float]] = {}
CACHE_TTL = 300


def _check_combination(model: str, key: str, timeout: float = 8.0) -> bool:
    """Test whether a model+api-key combination works; cache for 5 minutes."""
    now = time.time()
    cache_key = (model, key[-8:] if key else "")
    if cache_key in _combo_cache:
        status, expiry = _combo_cache[cache_key]
        if now < expiry:
            return status == "working"

    test_llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=0.0,
        google_api_key=key,
        timeout=timeout,
        max_retries=0,
    )
    try:
        test_llm.invoke([HumanMessage(content="ok")])
        _combo_cache[cache_key] = ("working", now + CACHE_TTL)
        logger.info("Gemini combo OK: model=%s", model)
        return True
    except Exception as exc:
        _combo_cache[cache_key] = ("exhausted", now + CACHE_TTL)
        logger.warning("Gemini combo failed: model=%s err=%s", model, exc)
        return False


def get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """
    Return ChatGoogleGenerativeAI with fallbacks across API keys and models.
    Tries primary GEMINI_MODEL first, then LLM_FALLBACK_CHAIN.
    """
    api_keys = API_KEYS or ([GOOGLE_API_KEY] if GOOGLE_API_KEY else [])
    if not api_keys:
        raise RuntimeError("GOOGLE_API_KEY is not set in .env")

    models = [GEMINI_MODEL] + [m for m in fallback_models() if m != GEMINI_MODEL]
    candidates: list[tuple[str, str]] = []
    for model_name in models:
        for key in api_keys:
            candidates.append((model_name, key))

    working: list[tuple[str, str]] = []
    for model_name, key in candidates:
        if _check_combination(model_name, key):
            working.append((model_name, key))
            # First working combo is enough to start; keep remaining as runtime fallbacks
            # still probe a few more cheaply from cache
            break

    if not working:
        # Fall back to primary without probe so the agent can still start
        logger.error("No Gemini combo passed probe; using primary model anyway")
        working = [(GEMINI_MODEL, api_keys[0])]

    # Build chain: working primary + remaining unevaluated candidates as fallbacks
    seen = set(working)
    for pair in candidates:
        if pair not in seen:
            working.append(pair)
            seen.add(pair)

    runnables = [
        ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=key,
        )
        for model_name, key in working[:8]  # cap chain length
    ]

    primary = runnables[0]
    logger.info("Using Gemini model=%s", working[0][0])
    if len(runnables) > 1:
        return primary.with_fallbacks(runnables[1:])
    return primary
