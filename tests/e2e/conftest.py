"""Runs the real app in a background thread on a free port, against seeded lots."""

import socket
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import uvicorn

from rosehill.config import Settings
from rosehill.container import build_container
from rosehill.domain.lot import ScrapedLot
from rosehill.domain.money import Money
from rosehill.web.app import create_app


class SeededSource:
    name = "demo"

    def __init__(self, now: datetime) -> None:
        def lot(
            sid: str, title: str, category: str, bid: int, bids: int, minutes: int
        ) -> ScrapedLot:
            return ScrapedLot(
                source_id=sid,
                title=title,
                current_bid=Money(bid),
                bid_count=bids,
                closes_at=now + timedelta(minutes=minutes),
                url=f"https://demo.invalid/{sid}",
                category=category,
                pickup_location="Burlington warehouse",
            )

        self.lots = [
            lot("1", "Dyson V8 cordless vacuum", "Appliances", 9000, 12, 4),
            lot("2", "DeWalt 20V drill kit", "Tools", 0, 0, 12),
            lot("3", "KitchenAid stand mixer", "Appliances", 21000, 30, 25),
            lot("4", "Makita circular saw", "Tools", 3500, 2, 50),
            lot("5", "Oak dining table", "Furniture", 15000, 20, 100),
        ]

    def fetch_active_lots(self):  # type: ignore[no-untyped-def]
        return iter(self.lots)

    def fetch_lots(self, ids):  # type: ignore[no-untyped-def]
        return iter(x for x in self.lots if x.source_id in ids)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    db: Path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    now = datetime.now(UTC)
    container = build_container(
        Settings(_env_file=None, database_url=f"sqlite:///{db}"),
        source=SeededSource(now),  # type: ignore[arg-type]
    )
    container.upgrade_database()
    container.refresh.full_sweep()

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(container, run_scheduler=False), port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
