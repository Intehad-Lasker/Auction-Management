"""Command-line entry point for the Rosehill auction manager."""

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from rosehill import __version__
from rosehill.config import Settings
from rosehill.scraping.registry import build_lot_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rosehill", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")

    scrape = commands.add_parser("scrape", help="fetch active lots from the configured source")
    scrape.add_argument("--dry-run", action="store_true", help="print lots instead of saving them")
    scrape.add_argument("--limit", type=int, default=20, help="lots to print (default 20)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scrape":
        if not args.dry_run:
            parser.error("saving lots arrives with the database; use --dry-run for now")
        return _scrape_dry_run(Settings(), args.limit)
    parser.print_help()
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
            f"{lot.source_id:<12} {closes} ({minutes:>3} min)  {lot.current_bid!s:>10}"
            f"  {lot.bid_count:>3} bids  {lot.title[:48]}"
        )
    return 0
