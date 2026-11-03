"""In-process publish/subscribe. Later features (alerts, steal scoring) subscribe here
instead of being wired into the code that produces the events."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from rosehill.domain.lot import StoredLot

log = logging.getLogger(__name__)
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class LotUpdated:
    """A lot was seen for the first time, or its bid, bid count or closing time changed."""

    lot: StoredLot
    is_new: bool


@dataclass(frozen=True, slots=True)
class LotClosed:
    lot: StoredLot
    closed_at: datetime


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Any], list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: object) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception:
                log.exception("event handler %r failed for %r", handler, event)
