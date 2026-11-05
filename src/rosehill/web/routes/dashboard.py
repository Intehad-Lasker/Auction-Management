"""Closing-soon dashboard. `/` renders the page; `/lots` renders just the results for htmx."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from rosehill.container import Container
from rosehill.services.dashboard import DashboardFilters, DashboardService, SortKey
from rosehill.storage.queries import SqlLotQueries

router = APIRouter()


def _service(container: Container) -> DashboardService:
    return DashboardService(
        SqlLotQueries(container.session_factory), container.uow, source=container.source.name
    )


def _render(request: Request, template: str) -> HTMLResponse:
    container: Container = request.app.state.container
    filters = DashboardFilters.from_params(request.query_params)
    view = _service(container).closing_soon(filters, container.clock())
    pricing = container.pricing.current()

    def sort_params(key: str) -> dict[str, str]:
        """Clicking the active column flips direction; a new column starts ascending."""
        params = filters.to_params()
        flip = filters.sort == SortKey(key) and not filters.descending
        params.update(sort=key, dir="desc" if flip else "asc")
        return params

    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request, template, {"view": view, "sort_params": sort_params, "pricing": pricing}
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return _render(request, "dashboard.html")


@router.get("/lots", response_class=HTMLResponse)
def lots(request: Request) -> HTMLResponse:
    return _render(request, "_results.html")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
