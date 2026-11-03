from datetime import UTC, datetime, timedelta

import httpx
import pytest

from rosehill.scraping.http import (
    DisallowedByRobotsError,
    InMemoryResponseCache,
    PoliteHttpClient,
)

BASE = "https://auctions.example"


class FakeTime:
    """Monotonic clock, sleep and wall clock that only move when told to."""

    def __init__(self) -> None:
        self.monotonic = 1000.0
        self.wall = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.monotonic

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)

    def now(self) -> datetime:
        return self.wall

    def advance(self, seconds: float) -> None:
        self.monotonic += seconds
        self.wall += timedelta(seconds=seconds)


class Server:
    """Records requests and answers from a route table. robots.txt allows all by default."""

    def __init__(self, routes: dict[str, list[httpx.Response]] | None = None) -> None:
        self.routes = routes or {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if self.routes.get(path):
            queue = self.routes[path]
            return queue.pop(0) if len(queue) > 1 else queue[0]
        if path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=f"page {path}")

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests if r.url.path != "/robots.txt"]


def make_client(
    server: Server, time: FakeTime, *, interval: float = 2.0
) -> tuple[PoliteHttpClient, InMemoryResponseCache]:
    cache = InMemoryResponseCache()
    client = PoliteHttpClient(
        httpx.Client(base_url=BASE, transport=httpx.MockTransport(server)),
        min_interval_seconds=interval,
        cache=cache,
        clock=time.clock,
        sleep=time.sleep,
        now=time.now,
    )
    return client, cache


def test_returns_body() -> None:
    client, _ = make_client(Server(), FakeTime())
    assert client.get_text("/lots?page=1") == "page /lots"


def test_waits_between_requests_to_respect_rate_limit() -> None:
    time = FakeTime()
    client, _ = make_client(Server(), time, interval=2.0)
    client.get_text("/a")
    time.advance(0.5)
    client.get_text("/b")
    assert time.sleeps[-1] == pytest.approx(1.5)


def test_no_wait_when_interval_already_passed() -> None:
    time = FakeTime()
    client, _ = make_client(Server(), time, interval=2.0)
    client.get_text("/a")
    time.sleeps.clear()
    time.advance(5)
    client.get_text("/b")
    assert time.sleeps == []


def test_fresh_cached_response_is_served_without_a_request() -> None:
    server, time = Server(), FakeTime()
    client, _ = make_client(server, time)
    client.get_text("/a", max_age=timedelta(minutes=5))
    time.advance(60)
    assert client.get_text("/a", max_age=timedelta(minutes=5)) == "page /a"
    assert server.paths() == ["/a"]


def test_stale_cache_is_refetched() -> None:
    server, time = Server(), FakeTime()
    client, _ = make_client(server, time)
    client.get_text("/a", max_age=timedelta(minutes=5))
    time.advance(600)
    client.get_text("/a", max_age=timedelta(minutes=5))
    assert server.paths() == ["/a", "/a"]


def test_without_max_age_always_fetches() -> None:
    server = Server()
    client, _ = make_client(server, FakeTime())
    client.get_text("/a")
    client.get_text("/a")
    assert server.paths() == ["/a", "/a"]


def test_sends_etag_and_uses_cached_body_on_304() -> None:
    server = Server(
        {"/a": [httpx.Response(200, text="v1", headers={"ETag": '"abc"'}), httpx.Response(304)]}
    )
    client, _ = make_client(server, FakeTime())
    assert client.get_text("/a") == "v1"
    assert client.get_text("/a") == "v1"
    assert server.requests[-1].headers["If-None-Match"] == '"abc"'


def test_retries_server_errors_with_backoff() -> None:
    time = FakeTime()
    server = Server(
        {"/a": [httpx.Response(503), httpx.Response(502), httpx.Response(200, text="ok")]}
    )
    client, _ = make_client(server, time, interval=1.0)
    assert client.get_text("/a") == "ok"
    assert server.paths() == ["/a", "/a", "/a"]


def test_honours_retry_after_on_429() -> None:
    time = FakeTime()
    server = Server(
        {"/a": [httpx.Response(429, headers={"Retry-After": "30"}), httpx.Response(200, text="ok")]}
    )
    client, _ = make_client(server, time, interval=1.0)
    assert client.get_text("/a") == "ok"
    assert 30 in time.sleeps


def test_gives_up_after_max_retries() -> None:
    server = Server({"/a": [httpx.Response(500)]})
    client, _ = make_client(server, FakeTime(), interval=1.0)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_text("/a")
    assert len(server.paths()) == 4  # first try + 3 retries


def test_client_errors_are_not_retried() -> None:
    server = Server({"/a": [httpx.Response(404)]})
    client, _ = make_client(server, FakeTime())
    with pytest.raises(httpx.HTTPStatusError):
        client.get_text("/a")
    assert server.paths() == ["/a"]


def test_refuses_paths_disallowed_by_robots_txt() -> None:
    robots = "User-agent: *\nDisallow: /admin\n"
    server = Server({"/robots.txt": [httpx.Response(200, text=robots)]})
    client, _ = make_client(server, FakeTime())
    with pytest.raises(DisallowedByRobotsError):
        client.get_text("/admin/users")
    assert client.get_text("/lots") == "page /lots"
    assert [r.url.path for r in server.requests].count("/robots.txt") == 1


def test_minimum_interval_below_one_second_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_client(Server(), FakeTime(), interval=0.1)
