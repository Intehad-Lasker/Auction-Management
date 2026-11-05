"""Turn form fields into prices and fee settings, with messages a person can act on."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from rosehill.domain.money import Money
from rosehill.pricing import BuyersPremium, FlatFee, Tax
from rosehill.services.pricing import PricingConfig, config_from_json

BLANK_ROWS = 2
_MAX_DOLLARS = Decimal("10000000")


def parse_dollars(raw: str | None) -> tuple[Money | None, str | None]:
    """(amount, error). Blank input is (None, None)."""
    text = (raw or "").strip().lstrip("$").replace(",", "")
    if not text:
        return None, None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None, "Enter an amount in dollars, like 45 or 45.50"
    if not value.is_finite() or value < 0:
        return None, "Enter an amount of $0 or more"
    if value > _MAX_DOLLARS:
        return None, "That amount is too large"
    return Money.from_dollars(value), None


@dataclass
class RuleRow:
    kind: str = "premium"
    label: str = ""
    value: str = ""
    base: str = "subtotal"


@dataclass
class IncrementRow:
    start: str = ""
    step: str = ""


@dataclass
class SettingsForm:
    rules: list[RuleRow] = field(default_factory=list)
    increments: list[IncrementRow] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def from_config(cls, config: PricingConfig) -> SettingsForm:
        rules: list[RuleRow] = []
        for rule in config.schedule.rules:
            match rule:
                case BuyersPremium():
                    rules.append(RuleRow("premium", rule.label, _plain(rule.percent)))
                case FlatFee():
                    rules.append(RuleRow("flat", rule.label, _plain(rule.amount.dollars)))
                case Tax():
                    rules.append(RuleRow("tax", rule.label, _plain(rule.percent), rule.base.value))
        increments = [
            IncrementRow(_plain(t.starting_at.dollars), _plain(t.step.dollars))
            for t in config.ladder.tiers
        ]
        return cls(rules, increments).with_blank_rows()

    @classmethod
    def from_fields(cls, fields: Mapping[str, Any]) -> SettingsForm:
        def get(name: str) -> str:
            return str(fields.get(name, "")).strip()

        rules = []
        for i in range(_count(fields, "rule-", "-kind")):
            rules.append(
                RuleRow(
                    get(f"rule-{i}-kind"),
                    get(f"rule-{i}-label"),
                    get(f"rule-{i}-value"),
                    get(f"rule-{i}-base") or "subtotal",
                )
            )
        increments = [
            IncrementRow(get(f"inc-{i}-start"), get(f"inc-{i}-step"))
            for i in range(_count(fields, "inc-", "-step"))
        ]
        return cls(rules, increments)

    def with_blank_rows(self) -> SettingsForm:
        self.rules = [r for r in self.rules if r.value] + [RuleRow() for _ in range(BLANK_ROWS)]
        self.increments = [r for r in self.increments if r.start or r.step] + [
            IncrementRow() for _ in range(BLANK_ROWS)
        ]
        return self

    def to_json(self) -> dict[str, Any]:
        rules: list[dict[str, str]] = []
        for row in self.rules:
            if not row.value:
                continue
            if row.kind == "flat":
                rules.append({"kind": "flat", "label": row.label, "amount": row.value})
            elif row.kind == "tax":
                rules.append(
                    {"kind": "tax", "label": row.label, "percent": row.value, "base": row.base}
                )
            else:
                rules.append({"kind": row.kind, "label": row.label, "percent": row.value})
        increments = [
            {"from": row.start or "0", "step": row.step}
            for row in self.increments
            if row.start or row.step
        ]
        return {"rules": rules, "increments": increments}

    def to_config(self) -> PricingConfig:
        """Raises PricingConfigError with a readable message when a row is wrong."""
        return config_from_json(self.to_json())


def _count(fields: Mapping[str, Any], prefix: str, suffix: str) -> int:
    middles = [
        key[len(prefix) : -len(suffix)]
        for key in fields
        if key.startswith(prefix) and key.endswith(suffix)
    ]
    indexes = [int(middle) for middle in middles if middle.isdigit()]
    return min(max(indexes, default=-1) + 1, 50)


def _plain(value: Decimal) -> str:
    """15.00 -> 15, 2.50 -> 2.50."""
    if value == value.to_integral_value():
        return str(value.to_integral_value())
    return f"{value:.2f}" if value.as_tuple().exponent == -2 else str(value.normalize())
