from sqlalchemy.orm import Session, sessionmaker

from rosehill.scraping.http import CachedResponse
from rosehill.storage.http_cache import SqlResponseCache

from .conftest import NOW


def test_put_then_get(session_factory: sessionmaker[Session]) -> None:
    cache = SqlResponseCache(session_factory)
    assert cache.get("https://x.invalid/a") is None
    cache.put("https://x.invalid/a", CachedResponse("body", '"e1"', NOW))
    assert cache.get("https://x.invalid/a") == CachedResponse("body", '"e1"', NOW)


def test_put_replaces_existing_entry(session_factory: sessionmaker[Session]) -> None:
    cache = SqlResponseCache(session_factory)
    cache.put("u", CachedResponse("old", None, NOW))
    cache.put("u", CachedResponse("new", '"e2"', NOW))
    assert cache.get("u") == CachedResponse("new", '"e2"', NOW)


def test_entries_survive_a_new_cache_instance(session_factory: sessionmaker[Session]) -> None:
    SqlResponseCache(session_factory).put("u", CachedResponse("kept", None, NOW))
    assert SqlResponseCache(session_factory).get("u") is not None
