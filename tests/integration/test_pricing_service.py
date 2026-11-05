from collections.abc import Callable
from decimal import Decimal

import pytest

from rosehill.domain.money import Money
from rosehill.pricing import BidLadder, FeeSchedule, FlatFee, Increment, Tax, TaxBase
from rosehill.services.pricing import (
    PricingConfig,
    PricingConfigError,
    PricingService,
    config_from_json,
    config_to_json,
    default_config,
)
from rosehill.storage.repositories import SqlUnitOfWork
from tests.integration.conftest import NOW


@pytest.fixture
def service(uow: Callable[[], SqlUnitOfWork]) -> PricingService:
    return PricingService(uow, default_config(Decimal("15"), Decimal("13")), lambda: NOW)


def test_defaults_apply_until_saved(service: PricingService) -> None:
    config = service.current()

    assert not config.confirmed
    assert config.cost(Money.from_dollars("100")).total == Money.from_dollars("129.95")


def test_saved_schedule_is_used_and_confirmed(service: PricingService) -> None:
    custom = PricingConfig(
        FeeSchedule((FlatFee(Money(250), "Handling"), Tax(Decimal("13"), TaxBase.BID))),
        BidLadder((Increment(Money(0), Money(100)), Increment(Money(10000), Money(500)))),
    )

    service.save(custom)
    service.save(custom)  # overwriting works too
    current = service.current()

    assert current.confirmed
    assert current.schedule == custom.schedule
    assert current.ladder == custom.ladder


def test_json_round_trip() -> None:
    config = default_config(Decimal("17.5"), Decimal("13"))

    assert config_from_json(config_to_json(config)).schedule == config.schedule


DOLLAR_STEPS = [{"from": "0", "step": "1"}]


@pytest.mark.parametrize(
    "data",
    [
        {"rules": [{"kind": "bribe", "percent": "5"}], "increments": DOLLAR_STEPS},
        {"rules": [{"kind": "premium", "percent": "lots"}], "increments": DOLLAR_STEPS},
        {"rules": [{"kind": "premium", "percent": "-3"}], "increments": DOLLAR_STEPS},
        {"rules": [{"kind": "tax", "percent": "13", "base": "x"}], "increments": DOLLAR_STEPS},
        {"rules": [], "increments": [{"from": "5", "step": "1"}]},
        {"rules": [], "increments": []},
        {"rules": [], "increments": [{"from": "0", "step": "0"}]},
    ],
)
def test_invalid_json_raises_a_readable_error(data: dict[str, object]) -> None:
    with pytest.raises(PricingConfigError):
        config_from_json(data)
