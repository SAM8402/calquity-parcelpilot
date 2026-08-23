"""Cache service for ParcelPilot.

Uses real Redis when REDIS_URL is set and reachable.
Otherwise uses fakeredis (in-process) — Gyansetu-style free deploy, no Redis service.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import redis

from app.config import CACHE_TTL_CHAT, CACHE_TTL_DOCS, CACHE_TTL_DATA, REDIS_URL

logger = logging.getLogger(__name__)


class CacheService:
    """Sync Redis-compatible cache (real Redis or fakeredis)."""

    def __init__(self) -> None:
        self._redis: Optional[Any] = None
        self.available = False
        self.backend: str = "none"

    def _fake_client(self) -> Any:
        """In-memory Redis via fakeredis (sync API matches redis-py)."""
        from fakeredis import FakeRedis

        return FakeRedis(decode_responses=True)

    def connect(self) -> bool:
        """Connect to Redis, or fall back to fakeredis when URL empty / unreachable."""
        url = (REDIS_URL or "").strip()

        if not url:
            self._redis = self._fake_client()
            self.available = True
            self.backend = "fakeredis"
            logger.info("Cache backend: fakeredis (REDIS_URL empty — deploy/default)")
            return True

        try:
            client = redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._redis = client
            self.available = True
            self.backend = "redis"
            logger.info("Cache backend: redis (%s)", url)
            return True
        except Exception as e:
            self._redis = self._fake_client()
            self.available = True
            self.backend = "fakeredis"
            logger.warning(
                "Redis unreachable (%s) — using fakeredis in-process cache", e
            )
            return True

    def disconnect(self) -> None:
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                pass
        self._redis = None
        self.available = False
        self.backend = "none"

    def get(self, key: str) -> Any | None:
        if not self._redis:
            return None
        try:
            val = self._redis.get(key)
            if val is None:
                return None
            logger.info("Cache hit: %s", key[:80])
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        except Exception as e:
            logger.error("Cache get error: %s", e)
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self._redis:
            return
        try:
            serialized = (
                json.dumps(value, default=str) if not isinstance(value, str) else value
            )
            self._redis.set(key, serialized, ex=ttl)
            logger.info("Cache set: %s ttl=%ds", key[:80], ttl)
        except Exception as e:
            logger.error("Cache set error: %s", e)

    def delete(self, key: str) -> None:
        if not self._redis:
            return
        try:
            self._redis.delete(key)
        except Exception:
            pass

    def delete_pattern(self, pattern: str) -> int:
        if not self._redis:
            return 0
        try:
            keys = list(self._redis.scan_iter(match=pattern, count=200))
            if keys:
                self._redis.delete(*keys)
                logger.info("Cache cleared pattern %s (%d keys)", pattern, len(keys))
                return len(keys)
        except Exception as e:
            logger.error("Cache delete_pattern error: %s", e)
        return 0

    @staticmethod
    def hash_key(*parts: str) -> str:
        raw = "|".join(p.strip().lower() for p in parts if p is not None)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    # ── Chat (empty-history FAQ only) ────────────────────────────────────

    def chat_cache_key(self, user_id: str, role: str, account_id: str | None, message: str) -> str:
        return "chat:" + self.hash_key(user_id, role, account_id or "", message)

    def get_chat(self, user_id: str, role: str, account_id: str | None, message: str) -> Any | None:
        return self.get(self.chat_cache_key(user_id, role, account_id, message))

    def set_chat(
        self,
        user_id: str,
        role: str,
        account_id: str | None,
        message: str,
        payload: dict,
    ) -> None:
        if payload.get("requires_confirmation"):
            return
        self.set(
            self.chat_cache_key(user_id, role, account_id, message),
            payload,
            ttl=CACHE_TTL_CHAT,
        )

    # ── Document search ──────────────────────────────────────────────────

    def get_docs(self, query: str, account_scope: str | None) -> Any | None:
        key = "docs:" + self.hash_key(query, account_scope or "all")
        return self.get(key)

    def set_docs(self, query: str, account_scope: str | None, value: str) -> None:
        key = "docs:" + self.hash_key(query, account_scope or "all")
        self.set(key, value, ttl=CACHE_TTL_DOCS)

    # ── Structured data ──────────────────────────────────────────────────

    def get_data(self, query_type: str, params: dict, account_scope: str | None) -> Any | None:
        key = "data:" + self.hash_key(
            query_type,
            json.dumps(params or {}, sort_keys=True, default=str),
            account_scope or "all",
        )
        return self.get(key)

    def set_data(
        self, query_type: str, params: dict, account_scope: str | None, value: str
    ) -> None:
        key = "data:" + self.hash_key(
            query_type,
            json.dumps(params or {}, sort_keys=True, default=str),
            account_scope or "all",
        )
        self.set(key, value, ttl=CACHE_TTL_DATA)


cache_service = CacheService()
