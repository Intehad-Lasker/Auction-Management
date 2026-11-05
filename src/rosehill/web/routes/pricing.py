"""Fee calculator, max-bid calculator and the Settings page that holds the fee schedule."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from rosehill.container import Container
from rosehill.domain.money import Money
from rosehill.pricing import CostBreakdown, MaxBid
from rosehill.services.pricing import PricingConfig, PricingConfigError
from rosehill.web.forms import SettingsForm, parse_dollars

router = APIRouter()


@dataclass(frozen=True, slots=True)
class CalculatorView:
    bid_text: str
    resale_text: str
    profit_text: str
    errors: dict[str, str]
    cost: CostBreakdown | None
    resale: Money | None
    target_profit: Money | None
    best: MaxBid | None

    @property
    def profit_at_bid(self) -> Money | None:
        if self.cost is None or self.resale is None:
            return None
        return self.resale - self.cost.total

    @property
    def over_max(self) -> bool:
        return self.cost is not None and self.best is not None and self.cost.bid > self.best.bid


def _calculate(params: dict[str, str], config: PricingConfig) -> CalculatorView:
    texts = {name: params.get(name, "").strip() for name in ("bid", "resale", "profit")}
    errors: dict[str, str] = {}
    values: dict[str, Money | None] = {}
    for name, text in texts.items():
        values[name], error = parse_dollars(text)
        if error:
            errors[name] = error
    bid, resale, profit = values["bid"], values["resale"], values["profit"]
    cost = config.cost(bid) if bid is not None else None
    best = None
    if resale is not None:
        best = config.max_bid(resale, profit or Money.zero())
    return CalculatorView(
        texts["bid"], texts["resale"], texts["profit"], errors, cost, resale, profit, best
    )


def _container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


def _calculator(request: Request, template: str) -> HTMLResponse:
    config = _container(request).pricing.current()
    view = _calculate(dict(request.query_params), config)
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request, template, {"calc": view, "pricing": config}
    )


@router.get("/calculator", response_class=HTMLResponse)
def calculator(request: Request) -> HTMLResponse:
    return _calculator(request, "calculator.html")


@router.get("/calculator/result", response_class=HTMLResponse)
def calculator_result(request: Request) -> HTMLResponse:
    return _calculator(request, "_calculator_result.html")


def _settings_page(
    request: Request, form: SettingsForm, config: PricingConfig, status_code: int = 200
) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "settings.html",
        {"form": form, "pricing": config, "saved": request.query_params.get("saved") == "1"},
        status_code=status_code,
    )


@router.get("/settings", response_class=HTMLResponse)
def settings(request: Request) -> HTMLResponse:
    config = _container(request).pricing.current()
    return _settings_page(request, SettingsForm.from_config(config), config)


@router.post("/settings", response_class=HTMLResponse)
async def save_settings(request: Request) -> Response:
    service = _container(request).pricing
    form = SettingsForm.from_fields(await request.form())
    try:
        service.save(form.to_config())
    except PricingConfigError as exc:
        form.error = str(exc)
        return _settings_page(request, form.with_blank_rows(), service.current(), 400)
    return RedirectResponse("/settings?saved=1", status_code=303)
