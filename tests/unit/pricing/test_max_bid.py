from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from rosehill.domain.money import Money
from rosehill.pricing import BidLadder, BuyersPremium, FeeSchedule, FlatFee, Increment, Tax, max_bid


def d(value: str) -> Money:
    return Money.from_dollars(value)


ONTARIO = FeeSchedule((BuyersPremium(Decimal("15")), Tax(Decimal("13"))))
DOLLARS = BidLadder.whole_dollars()


def test_highest_whole_dollar_bid_within_budget() -> None:
    # Resale 200, want 50 profit -> all-in must stay <= 150. 150 / 1.2995 = 115.43
    result = max_bid(ONTARIO, resale=d("200"), target_profit=d("50"), ladder=DOLLARS)

    assert result is not None
    assert result.bid == d("115")
    assert result.cost.total == d("149.44")
    assert result.profit == d("50.56")
    assert ONTARIO.cost(d("116")).total > d("150")


def test_none_when_even_a_zero_bid_misses_the_target() -> None:
    schedule = FeeSchedule((FlatFee(d("5")),))

    assert max_bid(schedule, resale=d("10"), target_profit=d("6"), ladder=DOLLARS) is None


def test_none_when_target_exceeds_resale() -> None:
    assert max_bid(ONTARIO, resale=d("10"), target_profit=d("20"), ladder=DOLLARS) is None


def test_respects_bid_ladder() -> None:
    ladder = BidLadder((Increment(d("0"), d("1")), Increment(d("100"), d("25"))))

    result = max_bid(ONTARIO, resale=d("200"), target_profit=d("0"), ladder=ladder)

    # 200 / 1.2995 = 153.9 -> ladder floor 150
    assert result is not None
    assert result.bid == d("150")


def test_no_fees_means_bid_equals_budget() -> None:
    result = max_bid(FeeSchedule(()), resale=d("80"), target_profit=d("30"), ladder=DOLLARS)

    assert result is not None
    assert result.bid == d("50")


@given(
    premium=st.decimals(min_value=0, max_value=40, places=2),
    tax=st.decimals(min_value=0, max_value=20, places=2),
    flat=st.integers(min_value=0, max_value=1000),
    resale=st.integers(min_value=0, max_value=1_000_000),
    profit=st.integers(min_value=0, max_value=100_000),
)
def test_result_is_the_best_valid_bid(
    premium: Decimal, tax: Decimal, flat: int, resale: int, profit: int
) -> None:
    schedule = FeeSchedule((BuyersPremium(premium), FlatFee(Money(flat)), Tax(tax)))
    budget = Money(resale - profit)

    result = max_bid(schedule, resale=Money(resale), target_profit=Money(profit), ladder=DOLLARS)

    if result is None:
        assert schedule.cost(Money(0)).total > budget
    else:
        assert result.cost.total <= budget
        assert result.bid.cents % 100 == 0
        assert schedule.cost(result.bid + Money(100)).total > budget
