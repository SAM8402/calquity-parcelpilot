"""LLM factory — primary Gemini model with optional env fallback chain."""
from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import API_KEYS, GEMINI_MODEL, GOOGLE_API_KEY, fallback_models

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    api_keys = API_KEYS or ([GOOGLE_API_KEY] if GOOGLE_API_KEY else [])
    if not api_keys:
        raise RuntimeError("GOOGLE_API_KEY is not set in .env")

    models = [GEMINI_MODEL] + [m for m in fallback_models() if m != GEMINI_MODEL]
    runnables = [
        ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=key,
        )
        for model_name in models[:4]
        for key in api_keys[:2]
    ]

    primary = runnables[0]
    logger.info("Using Gemini model=%s", models[0])
    if len(runnables) > 1:
        return primary.with_fallbacks(runnables[1:])
    return primary
