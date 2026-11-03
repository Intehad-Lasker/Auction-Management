from decimal import Decimal

import pytest

from rosehill.domain.money import Money


def test_from_dollars_parses_strings_and_decimals() -> None:
    assert Money.from_dollars("12.34").cents == 1234
    assert Money.from_dollars(Decimal("0.5")).cents == 50
    assert Money.from_dollars(7).cents == 700


def test_from_dollars_rounds_half_up_to_the_cent() -> None:
    assert Money.from_dollars("1.005").cents == 101
    assert Money.from_dollars("1.004").cents == 100


def test_from_dollars_rejects_floats() -> None:
    with pytest.raises(TypeError):
        Money.from_dollars(1.1)  # type: ignore[arg-type]


def test_dollars_round_trips() -> None:
    assert Money(1999).dollars == Decimal("19.99")


def test_addition_and_subtraction() -> None:
    assert Money(150) + Money(250) == Money(400)
    assert Money(500) - Money(125) == Money(375)


def test_ordering() -> None:
    assert Money(100) < Money(101)
    assert max(Money(5), Money(3)) == Money(5)


def test_str_formats_as_canadian_dollars() -> None:
    assert str(Money(123456)) == "$1,234.56"
    assert str(Money(-250)) == "-$2.50"


def test_zero() -> None:
    assert Money.zero() == Money(0)
