"""`ResponseCache` stored in the database, so cached pages survive restarts."""

from sqlalchemy.orm import Session, sessionmaker

from rosehill.scraping.http import CachedResponse
from rosehill.storage.tables import HttpCacheRow


class SqlResponseCache:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, url: str) -> CachedResponse | None:
        with self._session_factory() as session:
            row = session.get(HttpCacheRow, url)
            return None if row is None else CachedResponse(row.body, row.etag, row.fetched_at)

    def put(self, url: str, response: CachedResponse) -> None:
        with self._session_factory() as session:
            session.merge(
                HttpCacheRow(
                    url=url,
                    body=response.body,
                    etag=response.etag,
                    fetched_at=response.fetched_at,
                )
            )
            session.commit()
