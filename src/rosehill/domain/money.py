"""Money as whole cents. Floats are rejected so rounding errors cannot creep in."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


@dataclass(frozen=True, order=True, slots=True)
class Money:
    cents: int

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_dollars(cls, amount: Decimal | str | int) -> Money:
        if isinstance(amount, float):
            raise TypeError("use Decimal or str for money, not float")
        dollars = Decimal(amount).quantize(_CENT, rounding=ROUND_HALF_UP)
        return cls(int(dollars * 100))

    @classmethod
    def from_decimal_cents(cls, cents: Decimal) -> Money:
        """Round a fractional number of cents (e.g. a percentage result) half-up."""
        return cls(int(cents.quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    @property
    def dollars(self) -> Decimal:
        return Decimal(self.cents) / 100

    def __add__(self, other: Money) -> Money:
        return Money(self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        return Money(self.cents - other.cents)

    def __str__(self) -> str:
        sign = "-" if self.cents < 0 else ""
        return f"{sign}${abs(self.dollars):,.2f}"
