"""FastAPI application factory. Routes get their services from `app.state.container`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from rosehill.container import Container
from rosehill.web import formatting

_HERE = Path(__file__).parent


def build_templates(container: Container) -> Jinja2Templates:
    templates = Jinja2Templates(directory=_HERE / "templates")
    tz = ZoneInfo(container.settings.timezone)
    env = templates.env
    env.filters["local_time"] = lambda value: value.astimezone(tz).strftime("%H:%M")
    env.filters["time_left"] = formatting.time_left_text
    env.globals["urgency"] = formatting.urgency
    env.globals["fuse_percent"] = formatting.fuse_percent
    env.globals["is_demo"] = container.source.name == "demo"
    return templates


def create_app(container: Container, *, run_scheduler: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        scheduler = None
        if run_scheduler:
            from apscheduler.schedulers.background import BackgroundScheduler

            scheduler = BackgroundScheduler(timezone=UTC)
            scheduler.add_job(
                container.refresh.tick,
                "interval",
                seconds=container.settings.scheduler_tick_seconds,
                next_run_time=datetime.now(UTC),
                max_instances=1,
                coalesce=True,
            )
            scheduler.start()
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    app = FastAPI(title="Rosehill auction manager", lifespan=lifespan, docs_url=None)
    app.state.container = container
    app.state.templates = build_templates(container)
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

    from rosehill.web.routes import dashboard, pricing

    app.include_router(dashboard.router)
    app.include_router(pricing.router)
    return app
