"""Fee schedule and bid increments, stored as settings, plus the calculators built on them.

The schedule is saved as JSON under one settings key. Until the user saves it,
the first-run defaults from configuration apply and the pages say so, because
Rosehill's real rates have not been confirmed yet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from rosehill.domain.money import Money
from rosehill.pricing import (
    BidLadder,
    BuyersPremium,
    CostBreakdown,
    FeeRule,
    FeeSchedule,
    FlatFee,
    Increment,
    MaxBid,
    Tax,
    TaxBase,
    max_bid,
)
from rosehill.services.ports import UnitOfWork

SETTINGS_KEY = "pricing"


class PricingConfigError(ValueError):
    """A fee schedule or increment table that cannot be used, with a message for the user."""


@dataclass(frozen=True, slots=True)
class PricingConfig:
    schedule: FeeSchedule
    ladder: BidLadder
    # False while the first-run defaults are in use, before anyone saved real rates.
    confirmed: bool = False

    def cost(self, bid: Money) -> CostBreakdown:
        return self.schedule.cost(bid)

    def max_bid(self, resale: Money, target_profit: Money) -> MaxBid | None:
        return max_bid(
            self.schedule, resale=resale, target_profit=target_profit, ladder=self.ladder
        )


def default_config(premium_percent: Decimal, tax_percent: Decimal) -> PricingConfig:
    return PricingConfig(
        FeeSchedule((BuyersPremium(premium_percent), Tax(tax_percent))),
        BidLadder.whole_dollars(),
        confirmed=False,
    )


# --- JSON ----------------------------------------------------------------------------


def _decimal(value: object, what: str) -> Decimal:
    try:
        number = Decimal(str(value).strip().lstrip("$").rstrip("%").replace(",", ""))
    except InvalidOperation:
        raise PricingConfigError(f"{what} must be a number, got {value!r}") from None
    if not number.is_finite():
        raise PricingConfigError(f"{what} must be a number, got {value!r}")
    return number


def _money(value: object, what: str) -> Money:
    return Money.from_dollars(_decimal(value, what))


def rule_to_json(rule: FeeRule) -> dict[str, str]:
    match rule:
        case BuyersPremium(percent=percent, label=label):
            return {"kind": "premium", "label": label, "percent": str(percent)}
        case FlatFee(amount=amount, label=label):
            return {"kind": "flat", "label": label, "amount": str(amount.dollars)}
        case Tax(percent=percent, base=base, label=label):
            return {"kind": "tax", "label": label, "percent": str(percent), "base": base.value}
    raise TypeError(f"no JSON form for fee rule {rule!r}")


def rule_from_json(data: Mapping[str, Any]) -> FeeRule:
    kind = data.get("kind")
    label = str(data.get("label") or "").strip()
    try:
        if kind == "premium":
            percent = _decimal(data.get("percent"), "Buyer's premium")
            return BuyersPremium(percent, label or "Buyer's premium")
        if kind == "flat":
            return FlatFee(_money(data.get("amount"), "Flat fee"), label or "Lot fee")
        if kind == "tax":
            base = data.get("base", TaxBase.SUBTOTAL.value)
            if base not in TaxBase._value2member_map_:
                raise PricingConfigError(f"unknown tax base {base!r}")
            return Tax(_decimal(data.get("percent"), "Tax"), TaxBase(base), label or "Tax")
    except PricingConfigError:
        raise
    except ValueError as exc:
        raise PricingConfigError(f"{label or kind}: {exc}") from None
    raise PricingConfigError(f"unknown fee rule kind {kind!r}")


def config_to_json(config: PricingConfig) -> dict[str, Any]:
    return {
        "rules": [rule_to_json(rule) for rule in config.schedule.rules],
        "increments": [
            {"from": str(t.starting_at.dollars), "step": str(t.step.dollars)}
            for t in config.ladder.tiers
        ],
    }


def config_from_json(data: Mapping[str, Any], *, confirmed: bool = True) -> PricingConfig:
    rules = tuple(rule_from_json(rule) for rule in data.get("rules", []))
    try:
        tiers = tuple(
            Increment(_money(t.get("from"), "Increment start"), _money(t.get("step"), "Step"))
            for t in data.get("increments", [])
        )
        ladder = BidLadder(tuple(sorted(tiers, key=lambda t: t.starting_at)))
    except PricingConfigError:
        raise
    except ValueError as exc:
        raise PricingConfigError(f"Bid increments: {exc}") from None
    return PricingConfig(FeeSchedule(rules), ladder, confirmed=confirmed)


# --- Service -------------------------------------------------------------------------


class PricingService:
    def __init__(
        self,
        uow: Callable[[], UnitOfWork],
        defaults: PricingConfig,
        clock: Callable[[], datetime],
    ) -> None:
        self._uow = uow
        self._defaults = defaults
        self._clock = clock

    def current(self) -> PricingConfig:
        with self._uow() as uow:
            stored = uow.settings.get(SETTINGS_KEY)
        if stored is None:
            return self._defaults
        return config_from_json(stored)

    def save(self, config: PricingConfig) -> PricingConfig:
        with self._uow() as uow:
            uow.settings.put(SETTINGS_KEY, config_to_json(config), self._clock())
            uow.commit()
        return PricingConfig(config.schedule, config.ladder, confirmed=True)
