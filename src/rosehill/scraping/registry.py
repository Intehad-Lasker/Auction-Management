"""Maps the `ROSEHILL_SOURCE` setting to a `LotSource`. New adapters register here."""

from collections.abc import Callable

from rosehill.config import Settings
from rosehill.scraping.adapters.demo import DemoLotSource
from rosehill.scraping.http import InMemoryResponseCache, ResponseCache
from rosehill.scraping.ports import LotSource

# A factory gets the settings and the shared response cache, which HTTP-based
# adapters pass to PoliteHttpClient.
SourceFactory = Callable[[Settings, ResponseCache], LotSource]

_FACTORIES: dict[str, SourceFactory] = {
    "demo": lambda settings, cache: DemoLotSource(),
}


def available_sources() -> list[str]:
    return sorted(_FACTORIES)


def build_lot_source(settings: Settings, cache: ResponseCache | None = None) -> LotSource:
    try:
        factory = _FACTORIES[settings.source]
    except KeyError:
        options = ", ".join(available_sources())
        raise ValueError(f"unknown source {settings.source!r}; choose one of: {options}") from None
    return factory(settings, cache or InMemoryResponseCache())
