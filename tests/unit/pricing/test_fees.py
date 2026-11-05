from decimal import Decimal

import pytest

from rosehill.domain.money import Money
from rosehill.pricing import BuyersPremium, FeeSchedule, FlatFee, Tax, TaxBase


def dollars(value: str) -> Money:
    return Money.from_dollars(value)


def ontario(premium: str = "15") -> FeeSchedule:
    return FeeSchedule((BuyersPremium(Decimal(premium)), Tax(Decimal("13"))))


def test_premium_then_hst_on_bid_and_premium() -> None:
    cost = ontario().cost(dollars("100"))

    assert [line.label for line in cost.lines] == ["Buyer's premium", "HST"]
    assert cost.lines[0].amount == dollars("15")
    assert cost.lines[1].amount == dollars("14.95")
    assert cost.fees == dollars("29.95")
    assert cost.total == dollars("129.95")


def test_percentages_round_half_up_to_the_cent() -> None:
    cost = FeeSchedule((BuyersPremium(Decimal("15")),)).cost(Money(333))  # 49.95 cents

    assert cost.lines[0].amount == Money(50)


def test_flat_fee_is_taxed_when_tax_base_is_subtotal() -> None:
    schedule = FeeSchedule((FlatFee(dollars("2"), "Lot fee"), Tax(Decimal("10"))))

    cost = schedule.cost(dollars("10"))

    assert cost.lines[1].amount == dollars("1.20")
    assert cost.total == dollars("13.20")


def test_tax_on_bid_only_ignores_earlier_fees() -> None:
    schedule = FeeSchedule((BuyersPremium(Decimal("20")), Tax(Decimal("10"), base=TaxBase.BID)))

    cost = schedule.cost(dollars("50"))

    assert cost.lines[1].amount == dollars("5")
    assert cost.total == dollars("65")


def test_empty_schedule_costs_the_bid() -> None:
    assert FeeSchedule(()).cost(dollars("7")).total == dollars("7")


def test_zero_bid_still_pays_flat_fees() -> None:
    assert FeeSchedule((FlatFee(dollars("1")),)).cost(Money(0)).total == dollars("1")


@pytest.mark.parametrize(
    "rule",
    [
        lambda: BuyersPremium(Decimal("-1")),
        lambda: Tax(Decimal("-0.5")),
        lambda: FlatFee(Money(-1)),
    ],
)
def test_negative_rates_are_rejected(rule: object) -> None:
    with pytest.raises(ValueError):
        rule()  # type: ignore[operator]


def test_negative_bid_is_rejected() -> None:
    with pytest.raises(ValueError):
        ontario().cost(Money(-1))
