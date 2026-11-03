"""Command-line entry point for the Rosehill auction manager."""

from __future__ import annotations

import argparse
import contextlib
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from rosehill import __version__
from rosehill.config import Settings
from rosehill.container import Container, build_container
from rosehill.scraping.registry import build_lot_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rosehill", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")

    db = commands.add_parser("db", help="database maintenance")
    db_commands = db.add_subparsers(dest="db_command", required=True)
    db_commands.add_parser("upgrade", help="apply database migrations")

    scrape = commands.add_parser("scrape", help="run one full sweep of active lots")
    scrape.add_argument("--dry-run", action="store_true", help="print lots instead of saving")
    scrape.add_argument("--limit", type=int, default=20, help="lots to print with --dry-run")

    commands.add_parser("watch", help="keep scraping on the refresh schedule until stopped")

    serve = commands.add_parser("serve", help="run the dashboard (and the scraper schedule)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--no-scheduler", action="store_true", help="serve the dashboard without scraping"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    if args.command == "scrape" and args.dry_run:
        return _scrape_dry_run(settings, args.limit)

    container = build_container(settings)
    container.upgrade_database()
    if args.command == "db":
        print(f"database is up to date: {settings.database_url}")
        return 0
    if args.command == "scrape":
        return _scrape(container)
    if args.command == "watch":
        return _watch(container)
    if args.command == "serve":
        return _serve(container, args.host, args.port, scheduler=not args.no_scheduler)
    parser.error(f"unknown command {args.command}")
    return 2  # pragma: no cover - parser.error exits


def _scrape(container: Container) -> int:
    result = container.refresh.full_sweep()
    print(
        f"source: {container.source.name}  seen: {result.seen}  new: {result.new}"
        f"  changed: {result.changed}  closed: {result.closed}"
    )
    return 0


def _watch(container: Container) -> int:
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone=UTC)
    scheduler.add_job(
        container.refresh.tick,
        "interval",
        seconds=container.settings.scheduler_tick_seconds,
        next_run_time=datetime.now(UTC),
        max_instances=1,
        coalesce=True,
    )
    print(f"watching source {container.source.name}; press Ctrl+C to stop")
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        scheduler.start()
    return 0


def _serve(container: Container, host: str, port: int, *, scheduler: bool) -> int:
    import uvicorn

    from rosehill.web.app import create_app

    print(f"dashboard at http://{host}:{port}  (source: {container.source.name})")
    uvicorn.run(create_app(container, run_scheduler=scheduler), host=host, port=port)
    return 0


def _scrape_dry_run(settings: Settings, limit: int) -> int:
    source = build_lot_source(settings)
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(UTC)
    lots = sorted(source.fetch_active_lots(), key=lambda lot: lot.closes_at)
    print(f"source: {source.name}  active lots: {len(lots)}")
    for lot in lots[:limit]:
        minutes = int(lot.time_left(now).total_seconds() // 60)
        closes = lot.closes_at.astimezone(tz).strftime("%H:%M")
        print(
            f"{lot.source_id:<14} {closes} ({minutes:>3} min)  {lot.current_bid!s:>10}"
            f"  {lot.bid_count:>3} bids  {lot.title[:48]}"
        )
    return 0
