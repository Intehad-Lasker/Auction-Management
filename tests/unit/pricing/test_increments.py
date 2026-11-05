import pytest

from rosehill.domain.money import Money
from rosehill.pricing import BidLadder, Increment


def d(value: str) -> Money:
    return Money.from_dollars(value)


LADDER = BidLadder(
    (Increment(d("0"), d("1")), Increment(d("50"), d("5")), Increment(d("200"), d("10")))
)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("0", "0"),
        ("0.99", "0"),
        ("49.99", "49"),
        ("50", "50"),
        ("54.99", "50"),
        ("55", "55"),
        ("199", "195"),
        ("209.99", "200"),
        ("1234", "1230"),
    ],
)
def test_floor_snaps_down_to_a_valid_bid(amount: str, expected: str) -> None:
    assert LADDER.floor(d(amount)) == d(expected)


def test_default_ladder_is_whole_dollars() -> None:
    assert BidLadder.whole_dollars().floor(d("12.75")) == d("12")


def test_tiers_must_start_at_zero_and_ascend() -> None:
    with pytest.raises(ValueError):
        BidLadder((Increment(d("1"), d("1")),))
    with pytest.raises(ValueError):
        BidLadder((Increment(d("0"), d("1")), Increment(d("0"), d("5"))))
    with pytest.raises(ValueError):
        BidLadder(())


def test_step_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Increment(d("0"), d("0"))


def test_negative_amount_has_no_valid_bid() -> None:
    with pytest.raises(ValueError):
        LADDER.floor(Money(-1))
