"""Fee rules and schedules: what a lot really costs on top of the hammer price.

A schedule is an ordered list of rules. Each rule sees the bid and the fee lines
already added before it, so a tax can apply to the bid alone or to the bid plus
earlier fees. Every rule must cost the same or more as the bid rises; the
max-bid solver depends on that.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from rosehill.domain.money import Money


@dataclass(frozen=True, slots=True)
class FeeLine:
    label: str
    amount: Money


class FeeRule(Protocol):
    @property
    def label(self) -> str: ...

    def charge(self, bid: Money, earlier: Sequence[FeeLine]) -> Money: ...


def _percent_of(amount: Money, percent: Decimal) -> Money:
    return Money.from_decimal_cents(Decimal(amount.cents) * percent / 100)


def _check_percent(percent: Decimal) -> None:
    if not percent.is_finite() or percent < 0:
        raise ValueError(f"percentage must be zero or more, got {percent}")


@dataclass(frozen=True, slots=True)
class BuyersPremium:
    """A percentage of the bid."""

    percent: Decimal
    label: str = "Buyer's premium"

    def __post_init__(self) -> None:
        _check_percent(self.percent)

    def charge(self, bid: Money, earlier: Sequence[FeeLine]) -> Money:
        return _percent_of(bid, self.percent)


@dataclass(frozen=True, slots=True)
class FlatFee:
    """A fixed amount per lot, such as a handling or lot fee."""

    amount: Money
    label: str = "Lot fee"

    def __post_init__(self) -> None:
        if self.amount.cents < 0:
            raise ValueError("a flat fee cannot be negative")

    def charge(self, bid: Money, earlier: Sequence[FeeLine]) -> Money:
        return self.amount


class TaxBase(StrEnum):
    BID = "bid"
    SUBTOTAL = "subtotal"  # bid plus every fee before this rule


@dataclass(frozen=True, slots=True)
class Tax:
    percent: Decimal
    base: TaxBase = TaxBase.SUBTOTAL
    label: str = "HST"

    def __post_init__(self) -> None:
        _check_percent(self.percent)

    def charge(self, bid: Money, earlier: Sequence[FeeLine]) -> Money:
        base = bid
        if self.base is TaxBase.SUBTOTAL:
            for line in earlier:
                base = base + line.amount
        return _percent_of(base, self.percent)


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    bid: Money
    lines: tuple[FeeLine, ...]

    @property
    def fees(self) -> Money:
        return sum((line.amount for line in self.lines), Money.zero())

    @property
    def total(self) -> Money:
        return self.bid + self.fees


@dataclass(frozen=True, slots=True)
class FeeSchedule:
    rules: tuple[FeeRule, ...]

    def cost(self, bid: Money) -> CostBreakdown:
        if bid.cents < 0:
            raise ValueError("a bid cannot be negative")
        lines: list[FeeLine] = []
        for rule in self.rules:
            lines.append(FeeLine(rule.label, rule.charge(bid, lines)))
        return CostBreakdown(bid, tuple(lines))
