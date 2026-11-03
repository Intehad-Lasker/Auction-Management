from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rosehill.config import Settings
from rosehill.container import build_container
from rosehill.domain.money import Money
from rosehill.web.app import create_app

from .conftest import NOW, scraped


class FixedSource:
    """Serves a fixed set of lots so page assertions are exact."""

    name = "demo"

    def __init__(self) -> None:
        self.lots = [
            scraped(
                "a",
                title="Dyson V8 vacuum",
                category="Appliances",
                current_bid=Money(9000),
                bid_count=12,
                closes_at=NOW + timedelta(minutes=4),
            ),
            scraped(
                "b",
                title="DeWalt drill kit",
                category="Tools",
                current_bid=Money(0),
                bid_count=0,
                closes_at=NOW + timedelta(minutes=40),
            ),
            scraped(
                "c",
                title="Oak dining table",
                category="Furniture",
                current_bid=Money(15000),
                bid_count=20,
                closes_at=NOW + timedelta(minutes=100),
            ),
        ]

    def fetch_active_lots(self):  # type: ignore[no-untyped-def]
        return iter(self.lots)

    def fetch_lots(self, source_ids):  # type: ignore[no-untyped-def]
        return iter(lot for lot in self.lots if lot.source_id in source_ids)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'web.db'}")
    container = build_container(settings, clock=lambda: NOW, source=FixedSource())  # type: ignore[arg-type]
    container.upgrade_database()
    container.refresh.full_sweep()
    with TestClient(create_app(container, run_scheduler=False)) as test_client:
        yield test_client


def test_dashboard_lists_lots_in_the_default_hour(client: TestClient) -> None:
    page = client.get("/").text
    assert "Dyson V8 vacuum" in page
    assert "DeWalt drill kit" in page
    assert "Oak dining table" not in page  # closes in 100 minutes
    assert "2 lots" in page
    assert "Demo data" in page


def test_window_and_filters_apply(client: TestClient) -> None:
    page = client.get("/lots", params={"window": "120", "max_bids": "0"}).text
    assert "DeWalt drill kit" in page
    assert "Dyson" not in page
    assert "<html" not in page  # partial for htmx


def test_rows_carry_urgency_and_countdown_data(client: TestClient) -> None:
    page = client.get("/").text
    assert "urgency-now" in page  # Dyson, 4 minutes left
    assert "4:00" in page
    assert "No bids" in page


def test_sort_link_flips_direction_on_the_active_column(client: TestClient) -> None:
    page = client.get("/", params={"sort": "price"}).text
    assert 'aria-sort="ascending"' in page
    assert "sort=price&amp;dir=desc" in page


def test_empty_state_offers_a_way_forward(client: TestClient) -> None:
    page = client.get("/", params={"q": "nothing-matches"}).text
    assert "match these filters" in page
    assert "Clear filters" in page


def test_static_assets_and_health(client: TestClient) -> None:
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/vendor/htmx-2.0.4.min.js").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
