# Rosehill Auction Manager

A personal tool for [Rosehill Auctions](https://rosehillonline.ca). In the last
hour or two before lots close, it helps you scan around 2,000 listings and spot
lots that are cheap after fees and worth flipping.

> **Status:** early development. Scraping and storage work against a built-in
> **demo source** (generated sample lots); the Rosehill adapter is pending a look
> at how the site serves its listings. The closing-soon dashboard works; the
> calculators and watchlist come next. See the [v1 design](docs/superpowers/specs/2026-11-03-rosehill-v1-design.md).

## Planned v1 features

- **Scraper**: collects every active lot into a local database, re-checks lots
  closing soon more often, rate-limited and cached. Records every closing price.
- **Closing-soon dashboard**: lots closing in the next 30, 60 or 120 minutes,
  with search, filters and sorting.
- **Fee calculator**: all-in cost (bid + buyer's premium + tax), with rates set
  in Settings.
- **Max-bid calculator**: the highest bid that still hits your profit target.
- **Watchlist**: starred lots with your resale estimate, max bid, countdown and
  an over-limit warning.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
cp .env.example .env   # optional: adjust settings
uv run rosehill db upgrade
```

## Usage

```bash
uv run rosehill serve              # dashboard at http://127.0.0.1:8000, scraping in the background
uv run rosehill serve --no-scheduler   # dashboard only
uv run rosehill scrape --dry-run   # print what the source returns, save nothing
uv run rosehill scrape             # one full sweep into the database
uv run rosehill watch              # keep scraping on the refresh schedule (Ctrl+C stops)
```

`watch` does a full sweep every hour and re-checks lots closing within two hours
every 5 minutes, and within 15 minutes every minute. `serve` runs the same
schedule alongside the dashboard.

### Dashboard

The closing-soon page lists open lots closing in the next 30, 60 or 120 minutes.
Search matches every word you type against lot titles; filter by category or by
bid count ("No bids yet", "3 or fewer", ...); click a column heading to sort, and
again to reverse. Countdowns tick every second and turn yellow inside 15 minutes
and red inside 5. The table refreshes itself every minute. When a lot closes, its final
price is saved to `lot_closings`; every bid change is saved to `lot_snapshots`.

## Configuration

All settings are environment variables prefixed with `ROSEHILL_`, read from the
environment or from `.env`. See [`.env.example`](.env.example) for the full list
and defaults. Fee rates will be editable from the app's Settings page.

## Development

```bash
uv run pytest           # all tests, including browser tests
uv run pytest -m "not e2e"   # skip the Playwright browser tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # type check (strict)
```

### Project layout

```
src/rosehill/
  domain/       Money, ScrapedLot, StoredLot (no I/O)
  scraping/     LotSource port, polite HTTP client, adapters/ (demo for now)
  storage/      SQLAlchemy tables, Alembic migrations, repositories, HTTP cache
  services/     sync (store lots, snapshots, closings), refresh policy and runner
  web/          FastAPI app, routes, Jinja templates, static assets (htmx vendored)
  events.py     in-process event bus (LotUpdated, LotClosed)
  container.py  composition root: picks implementations and wires them up
  config.py     settings
  cli.py        command-line entry point
tests/unit/         fast tests, no database or network
tests/integration/  repository, sync, refresh and page tests against SQLite
tests/e2e/          Playwright tests that drive the dashboard in Chromium
docs/               design and implementation plans
```

Dependencies point inward: services use the `LotSource` and `UnitOfWork`
protocols, never SQLAlchemy or a specific scraper. Adding a scraper means writing
an adapter and registering it in `scraping/registry.py`.

### Conventions

- One branch per milestone (`feat/scraper`, `feat/dashboard`, …), merged into
  `main` when tests pass and the code is reviewed.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `test:`, `refactor:`, `docs:`, `chore:`.
- Money is stored as integer cents and calculated with `Decimal`, never floats.

## Scraping etiquette

The scraper respects `robots.txt`, waits at least one second between requests
(two by default), caches responses, and never places bids.
