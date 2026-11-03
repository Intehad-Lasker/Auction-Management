import pytest

from rosehill.services.dashboard import DashboardFilters, SortKey


def test_defaults() -> None:
    f = DashboardFilters.from_params({})
    assert f == DashboardFilters(
        window_minutes=60,
        search="",
        category=None,
        max_bids=None,
        sort=SortKey.TIME_LEFT,
        descending=False,
    )


def test_parses_valid_params() -> None:
    f = DashboardFilters.from_params(
        {
            "window": "30",
            "q": "  dyson   vacuum ",
            "category": "Appliances",
            "max_bids": "3",
            "sort": "price",
            "dir": "desc",
        }
    )
    assert f.window_minutes == 30
    assert f.search_terms == ("dyson", "vacuum")
    assert f.category == "Appliances"
    assert f.max_bids == 3
    assert f.sort is SortKey.PRICE
    assert f.descending is True


@pytest.mark.parametrize(
    "params",
    [
        {"window": "45"},
        {"window": "abc"},
        {"sort": "title"},
        {"max_bids": "-1"},
        {"max_bids": "x"},
        {"dir": "sideways"},
    ],
)
def test_invalid_values_fall_back_to_defaults(params: dict[str, str]) -> None:
    assert DashboardFilters.from_params(params) == DashboardFilters()


def test_blank_category_and_bids_mean_any() -> None:
    f = DashboardFilters.from_params({"category": "", "max_bids": ""})
    assert f.category is None and f.max_bids is None


def test_to_params_round_trips() -> None:
    f = DashboardFilters(
        window_minutes=120,
        search="kitchen aid",
        category="Tools",
        max_bids=0,
        sort=SortKey.BIDS,
        descending=True,
    )
    assert DashboardFilters.from_params(f.to_params()) == f
