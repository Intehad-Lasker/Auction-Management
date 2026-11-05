"""Bid increments: which amounts the auction accepts as a bid."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from rosehill.domain.money import Money


@dataclass(frozen=True, slots=True)
class Increment:
    """From `starting_at` upward, bids go up in steps of `step`."""

    starting_at: Money
    step: Money

    def __post_init__(self) -> None:
        if self.step.cents <= 0:
            raise ValueError("a bid increment must be more than zero")


@dataclass(frozen=True, slots=True)
class BidLadder:
    """Tiers of increments. Valid bids in a tier are its start plus whole steps."""

    tiers: tuple[Increment, ...]

    def __post_init__(self) -> None:
        if not self.tiers or self.tiers[0].starting_at.cents != 0:
            raise ValueError("the first bid increment tier must start at $0")
        starts = [tier.starting_at.cents for tier in self.tiers]
        if any(b <= a for a, b in pairwise(starts)):
            raise ValueError("bid increment tiers must start at rising amounts")

    @classmethod
    def whole_dollars(cls) -> BidLadder:
        return cls((Increment(Money(0), Money(100)),))

    def floor(self, amount: Money) -> Money:
        """The highest valid bid at or below `amount`."""
        if amount.cents < 0:
            raise ValueError("no valid bid below $0")
        tier = next(t for t in reversed(self.tiers) if t.starting_at <= amount)
        steps = (amount.cents - tier.starting_at.cents) // tier.step.cents
        return Money(tier.starting_at.cents + steps * tier.step.cents)
