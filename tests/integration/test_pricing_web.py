from fastapi.testclient import TestClient


def test_dashboard_shows_all_in_cost_and_placeholder_notice(client: TestClient) -> None:
    page = client.get("/").text
    # Dyson at $90: 15% premium 13.50, HST 13% of 103.50 = 13.46 -> 116.96
    assert "$116.96" in page
    assert 'href="/calculator?bid=90"' in page
    assert "placeholder rates" in page
    assert "$1.00" not in page and "$0.00" not in page  # no all-in shown for unbid lots


def test_fee_breakdown_for_a_bid(client: TestClient) -> None:
    page = client.get("/calculator", params={"bid": "100"}).text
    assert "Buyer&#39;s premium" in page
    assert "$15.00" in page
    assert "$14.95" in page
    assert "$129.95" in page


def test_max_bid_for_resale_and_target(client: TestClient) -> None:
    page = client.get("/calculator/result", params={"resale": "200", "profit": "50"}).text
    assert "<html" not in page
    assert "Bid up to <strong>$115.00</strong>" in page
    assert "leaving $50.56" in page


def test_bid_over_max_is_flagged(client: TestClient) -> None:
    page = client.get("/calculator", params={"bid": "130", "resale": "200", "profit": "50"}).text
    assert "Over your max bid of $115.00" in page
    assert "that leaves $31.06" in page


def test_unreachable_target_says_pass(client: TestClient) -> None:
    page = client.get("/calculator", params={"resale": "10", "profit": "20"}).text
    assert "Pass" in page


def test_bad_input_is_explained_not_crashed(client: TestClient) -> None:
    page = client.get("/calculator", params={"bid": "abc", "resale": "-5"}).text
    assert "Bid: Enter an amount in dollars" in page
    assert "Resale price: Enter an amount of $0 or more" in page


def test_saving_settings_changes_every_calculation(client: TestClient) -> None:
    rows = [
        ("premium", "Premium", "18"),
        ("flat", "Lot fee", "2"),
        ("tax", "HST", "13"),
        ("premium", "", ""),
    ]
    form: dict[str, str] = {}
    for i, (kind, label, value) in enumerate(rows):
        form |= {f"rule-{i}-kind": kind, f"rule-{i}-label": label, f"rule-{i}-value": value}
        form[f"rule-{i}-base"] = "subtotal"
    form |= {"inc-0-start": "0", "inc-0-step": "1", "inc-1-start": "100", "inc-1-step": "5"}
    form |= {"inc-2-start": "", "inc-2-step": ""}
    response = client.post("/settings", data=form, follow_redirects=False)
    assert response.status_code == 303

    settings_page = client.get("/settings?saved=1").text
    assert "Saved." in settings_page
    assert 'value="18"' in settings_page
    assert "placeholder rates" not in settings_page

    # 100 + 18 + 2 = 120, HST 15.60 -> 135.60
    calc = client.get("/calculator", params={"bid": "100"}).text
    assert "$135.60" in calc
    assert "placeholder rates" not in calc


def test_invalid_settings_are_rejected_and_kept(client: TestClient) -> None:
    form = {
        "rule-0-kind": "premium", "rule-0-label": "Premium", "rule-0-value": "lots",
        "inc-0-start": "0", "inc-0-step": "1",
    }  # fmt: skip
    response = client.post("/settings", data=form)
    assert response.status_code == 400
    assert "must be a number" in response.text
    assert 'value="lots"' in response.text
    # Nothing was saved.
    assert "$129.95" in client.get("/calculator", params={"bid": "100"}).text


def test_increments_must_start_at_zero(client: TestClient) -> None:
    form = {"rule-0-kind": "tax", "rule-0-value": "13", "inc-0-start": "5", "inc-0-step": "1"}
    response = client.post("/settings", data=form)
    assert response.status_code == 400
    assert "start at $0" in response.text
