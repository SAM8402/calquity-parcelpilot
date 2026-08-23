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


def test_hash_embeddings_deterministic():
    from app.data.embeddings import HashEmbeddings

    emb = HashEmbeddings(dim=64)
    a = emb.embed_query("cancellation fee ORD-1001")
    b = emb.embed_query("cancellation fee ORD-1001")
    c = emb.embed_documents(["a", "b"])
    assert a == b
    assert len(a) == 64
    assert len(c) == 2
    assert abs(sum(x * x for x in a) - 1.0) < 1e-5


def test_collection_name_for_backend():
    from app.data.embeddings import collection_name_for

    assert collection_name_for("google") == "parcelpilot_docs_google"
    assert collection_name_for("local") == "parcelpilot_docs_local"
