"""A polite HTTP client for scraping: rate-limited, cached, robots.txt-aware, with retries.

Adapters fetch through this client so every scraping method gets the same manners.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.robotparser import RobotFileParser

import httpx

_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRY_AFTER_SECONDS = 300.0


class DisallowedByRobotsError(Exception):
    """The site's robots.txt does not allow this path."""


@dataclass(frozen=True, slots=True)
class CachedResponse:
    body: str
    etag: str | None
    fetched_at: datetime


class ResponseCache(Protocol):
    def get(self, url: str) -> CachedResponse | None: ...

    def put(self, url: str, response: CachedResponse) -> None: ...


class InMemoryResponseCache:
    def __init__(self) -> None:
        self._entries: dict[str, CachedResponse] = {}

    def get(self, url: str) -> CachedResponse | None:
        return self._entries.get(url)

    def put(self, url: str, response: CachedResponse) -> None:
        self._entries[url] = response


class PoliteHttpClient:
    def __init__(
        self,
        http: httpx.Client,
        *,
        min_interval_seconds: float,
        cache: ResponseCache,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        respect_robots: bool = True,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if min_interval_seconds < 1.0:
            raise ValueError("min_interval_seconds must be at least 1 second")
        self._http = http
        self._min_interval = min_interval_seconds
        self._cache = cache
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._respect_robots = respect_robots
        self._clock = clock
        self._sleep = sleep
        self._now = now
        self._last_request_at: float | None = None
        self._robots: RobotFileParser | None = None

    def get_text(self, url: str, *, max_age: timedelta | None = None) -> str:
        """GET `url` (absolute or relative to the client's base URL) and return the body.

        A cached copy younger than `max_age` is returned without any request.
        """
        full_url = str(self._http.build_request("GET", url).url)
        cached = self._cache.get(full_url)
        if cached and max_age is not None and self._now() - cached.fetched_at < max_age:
            return cached.body

        self._check_robots(full_url)
        headers = {"If-None-Match": cached.etag} if cached and cached.etag else {}
        response = self._send_with_retries(full_url, headers)

        if response.status_code == 304 and cached:
            self._cache.put(full_url, CachedResponse(cached.body, cached.etag, self._now()))
            return cached.body

        response.raise_for_status()
        body = response.text
        self._cache.put(full_url, CachedResponse(body, response.headers.get("ETag"), self._now()))
        return body

    def _send_with_retries(self, url: str, headers: dict[str, str]) -> httpx.Response:
        attempt = 0
        while True:
            response = self._send(url, headers)
            if response.status_code not in _RETRYABLE or attempt >= self._max_retries:
                return response
            self._sleep(self._retry_delay(response, attempt))
            attempt += 1

    def _send(self, url: str, headers: dict[str, str]) -> httpx.Response:
        self._wait_for_rate_limit()
        try:
            return self._http.get(url, headers=headers)
        finally:
            self._last_request_at = self._clock()

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self._min_interval - (self._clock() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return min(float(retry_after), _MAX_RETRY_AFTER_SECONDS)
        return float(self._backoff * (2**attempt))

    def _check_robots(self, url: str) -> None:
        if not self._respect_robots:
            return
        if self._robots is None:
            self._robots = self._load_robots(url)
        agent = self._http.headers.get("User-Agent", "*")
        if not self._robots.can_fetch(agent, url):
            raise DisallowedByRobotsError(url)

    def _load_robots(self, url: str) -> RobotFileParser:
        parser = RobotFileParser()
        robots_url = str(httpx.URL(url).copy_with(path="/robots.txt", query=None))
        response = self._send(robots_url, {})
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        elif response.status_code in (401, 403):
            parser.parse(["User-agent: *", "Disallow: /"])  # robots.txt access denied
        else:
            parser.parse([])  # missing robots.txt: everything allowed
        return parser
