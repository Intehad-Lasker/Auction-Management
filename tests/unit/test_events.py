from dataclasses import dataclass

from rosehill.events import EventBus


@dataclass(frozen=True)
class Ping:
    value: int


@dataclass(frozen=True)
class Pong:
    value: int


def test_handlers_receive_only_their_event_type() -> None:
    bus = EventBus()
    pings: list[Ping] = []
    pongs: list[Pong] = []
    bus.subscribe(Ping, pings.append)
    bus.subscribe(Pong, pongs.append)
    bus.publish(Ping(1))
    assert pings == [Ping(1)]
    assert pongs == []


def test_a_failing_handler_does_not_stop_the_others() -> None:
    bus = EventBus()
    seen: list[Ping] = []

    def broken(_: Ping) -> None:
        raise RuntimeError("boom")

    bus.subscribe(Ping, broken)
    bus.subscribe(Ping, seen.append)
    bus.publish(Ping(2))
    assert seen == [Ping(2)]


def test_publish_without_subscribers_is_fine() -> None:
    EventBus().publish(Ping(3))
