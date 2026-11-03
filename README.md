# Rosehill Auction Manager

A personal tool for [Rosehill Auctions](https://rosehillonline.ca). In the last
hour or two before lots close, it helps you scan around 2,000 listings and spot
lots that are cheap after fees and worth flipping.

> **Status:** early development. The project skeleton and settings are in
> place; the scraper, dashboard, calculators and watchlist are being built in
> that order. See the [v1 design](docs/superpowers/specs/2026-11-03-rosehill-v1-design.md).

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
uv run rosehill --version
```

## Configuration

All settings are environment variables prefixed with `ROSEHILL_`, read from the
environment or from `.env`. See [`.env.example`](.env.example) for the full list
and defaults. Fee rates will be editable from the app's Settings page.

## Development

```bash
uv run pytest           # tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # type check (strict)
```

### Project layout

```
src/rosehill/
  config.py     settings
  cli.py        command-line entry point
tests/unit/     fast tests with no network or database
docs/           design and implementation plans
```

The full layered layout (domain, pricing, scraping, storage, services, web) is
described in the design doc and arrives milestone by milestone.

### Conventions

- One branch per milestone (`feat/scraper`, `feat/dashboard`, …), merged into
  `main` when tests pass and the code is reviewed.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `test:`, `refactor:`, `docs:`, `chore:`.
- Money is stored as integer cents and calculated with `Decimal`, never floats.

## Scraping etiquette

The scraper respects `robots.txt`, waits at least one second between requests
(two by default), caches responses, and never places bids.
