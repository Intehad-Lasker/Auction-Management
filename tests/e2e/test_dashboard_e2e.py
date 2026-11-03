import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def titles(page: Page) -> list[str]:
    return page.locator(".lot-title").all_inner_texts()


def test_default_view_shows_the_next_hour_soonest_first(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.locator(".count")).to_contain_text("4 lots closing in the next 60 minutes")
    assert titles(page) == [
        "Dyson V8 cordless vacuum",
        "DeWalt 20V drill kit",
        "KitchenAid stand mixer",
        "Makita circular saw",
    ]


def test_switching_window_updates_results_and_url(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_role("radio", name="120").check()
    expect(page.locator(".count")).to_contain_text("5 lots closing in the next 120 minutes")
    expect(page).to_have_url(re.compile(r"window=120"))


def test_typing_a_search_filters_live(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_label("Search titles").fill("drill")
    expect(page.locator(".lot-title")).to_have_count(1)
    expect(page.locator(".lot-title")).to_have_text("DeWalt 20V drill kit")


def test_category_and_low_bid_filters(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_label("Category").select_option("Tools")
    expect(page.locator(".lot-title")).to_have_count(2)
    page.get_by_label("Bids").select_option(label="No bids yet")
    expect(page.locator(".lot-title")).to_have_text(["DeWalt 20V drill kit"])


def test_sorting_by_price_toggles_direction(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_role("link", name="Current bid").click()
    expect(page.locator(".lot-title").first).to_have_text("DeWalt 20V drill kit")
    page.get_by_role("link", name="Current bid").click()
    expect(page.locator(".lot-title").first).to_have_text("KitchenAid stand mixer")


def test_countdown_ticks_and_marks_urgent_lots(page: Page, base_url: str) -> None:
    page.goto(base_url)
    first = page.locator("tr.lot").first
    expect(first).to_have_class(re.compile("urgency-now"))
    before = first.locator(".time-text").inner_text()
    page.wait_for_timeout(1500)
    assert first.locator(".time-text").inner_text() != before


def test_no_matches_shows_how_to_recover(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_label("Search titles").fill("zzz-nothing")
    expect(page.get_by_text("match these filters")).to_be_visible()
    page.get_by_role("link", name="Clear filters").click()
    expect(page.locator(".lot-title")).to_have_count(4)


def test_sort_survives_a_later_filter_change(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_role("link", name="Current bid").click()
    page.get_by_role("link", name="Current bid").click()  # most expensive first
    page.get_by_label("Category").select_option("Tools")
    expect(page.locator(".lot-title")).to_have_text(["Makita circular saw", "DeWalt 20V drill kit"])
