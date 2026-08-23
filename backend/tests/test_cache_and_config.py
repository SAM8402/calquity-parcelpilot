"""Lightweight CI tests — no live Gemini / Redis required."""
from app.config import CORS_ORIGINS, _parse_cors
from app.services.cache_service import CacheService


def test_parse_cors_json_array():
    assert _parse_cors('["http://localhost:3000","https://example.com"]') == [
        "http://localhost:3000",
        "https://example.com",
    ]


def test_parse_cors_comma_separated():
    assert _parse_cors("http://a.com, http://b.com") == [
        "http://a.com",
        "http://b.com",
    ]


def test_fakeredis_cache_roundtrip(monkeypatch):
    monkeypatch.setattr("app.services.cache_service.REDIS_URL", "")
    cache = CacheService()
    assert cache.connect() is True
    assert cache.backend == "fakeredis"
    assert cache.available is True

    cache.set("ci:key", {"ok": True}, ttl=60)
    assert cache.get("ci:key") == {"ok": True}
    assert cache.delete_pattern("ci:*") >= 1
    cache.disconnect()


def test_cors_origins_loaded():
    assert isinstance(CORS_ORIGINS, list)
    assert len(CORS_ORIGINS) >= 1
