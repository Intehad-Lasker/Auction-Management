from fastapi.testclient import TestClient


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
