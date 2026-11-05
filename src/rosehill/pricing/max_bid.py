"""The highest bid that still leaves the target profit after fees."""

from __future__ import annotations

from dataclasses import dataclass

from rosehill.domain.money import Money
from rosehill.pricing.fees import CostBreakdown, FeeSchedule
from rosehill.pricing.increments import BidLadder


@dataclass(frozen=True, slots=True)
class MaxBid:
    bid: Money
    cost: CostBreakdown
    resale: Money

    @property
    def profit(self) -> Money:
        return self.resale - self.cost.total


def max_bid(
    schedule: FeeSchedule, *, resale: Money, target_profit: Money, ladder: BidLadder
) -> MaxBid | None:
    """Binary search for the highest bid whose all-in cost fits the budget.

    Works for any schedule whose total never falls as the bid rises. Returns
    None when not even a $0 bid leaves the target profit.
    """
    budget = resale - target_profit
    if schedule.cost(Money(0)).total > budget:
        return None
    # Fees are never negative, so the answer is at most the budget itself.
    low, high = 0, budget.cents  # invariant: cost(low) fits
    while low < high:
        mid = (low + high + 1) // 2
        if schedule.cost(Money(mid)).total <= budget:
            low = mid
        else:
            high = mid - 1
    bid = ladder.floor(Money(low))
    return MaxBid(bid, schedule.cost(bid), resale)
