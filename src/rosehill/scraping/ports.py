"""The scraping port. Everything outside `scraping/` depends on this, never on an adapter."""

from collections.abc import Collection, Iterator
from typing import Protocol

from rosehill.domain.lot import ScrapedLot


class LotSource(Protocol):
    """Somewhere lots can be read from: a JSON API, HTML pages, a headless browser, or a fake."""

    @property
    def name(self) -> str:
        """Short identifier shown in the UI and recorded on each scrape run."""
        ...

    def fetch_active_lots(self) -> Iterator[ScrapedLot]:
        """Every lot currently open for bidding."""
        ...

    def fetch_lots(self, source_ids: Collection[str]) -> Iterator[ScrapedLot]:
        """Fresh data for specific lots, including ones that have just closed.

        Adapters without a per-lot endpoint may implement this by filtering a full fetch.
        """
        ...
