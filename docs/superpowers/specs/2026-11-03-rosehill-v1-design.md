# Rosehill Auction Manager — Version 1 Design

Status: approved 2026-11-03

## Intent

Rosehill Auctions (rosehillonline.ca) runs timed online auctions. Prices only
settle in the last 1–2 hours before lots close. This tool helps one buyer go
through roughly 2,000 active lots quickly in that window and find "steals":
lots that are cheap after fees and resell well.

## Goals (v1)

1. **Scraper**: collect every active lot (title, current bid, bid count, closing
   time, photos, link, pickup location) into a database. Re-check lots closing
   soon more often. Keep the request rate low and cache responses.
2. **Fee calculator**: all-in cost per lot (bid + buyer's premium + tax). Rates
   come from settings, never from code.
3. **Max-bid calculator**: given a resale price and a target profit, the highest
   bid that still meets the target after fees.
4. **Closing-soon dashboard**: lots closing in the next 30, 60 or 120 minutes,
   with search, a keyword/category filter, a low-bid-count filter, and sorting
   by time left, price or bid count.
5. **Watchlist**: star lots, record a resale estimate and max bid, show a
   countdown and an over-limit warning.
6. **Price history**: record the closing price of every lot the scraper sees,
   from day one.

## Non-goals (v1), designed for later

Automatic resale lookup (eBay, Marketplace, Kijiji), steal scoring, alerts,
inventory and profit tracking, pickup planning, listing generator. Each must
be addable as a new module without rewriting existing ones.

## Anti-goals

- Hammering Rosehill's servers. The scraper is rate-limited, caches responses
  and respects `robots.txt`.
- Placing bids automatically. The tool informs; the user bids.
- Fee rates or business rules buried in code.

## Constraints

- One user, running on their own computer during the closing window.
- Money is stored as integer cents and calculated with `Decimal`; never floats.
- All timestamps are stored in UTC and shown in local time (America/Toronto).
- Commits are authored by the maintainer only, using Conventional Commits, one
  branch per milestone merged into `main`.

## Approaches considered

| Approach | Trade-off | Decision |
|---|---|---|
| Python: FastAPI + Jinja2 + HTMX, SQLite | One language, best scraping tools, no frontend build | **Chosen** |
| TypeScript: Next.js + Prisma | Strong UI tooling; weaker scraping, two runtimes | Rejected |
| Python API + React SPA | Rich client, but heavy for one user and one table | Rejected |

## Stack

- Python 3.12+, managed with uv.
- httpx + selectolax for scraping; Playwright only if the site requires a
  browser. The adapter is chosen after inspecting the site.
- SQLite (WAL mode) through SQLAlchemy 2.0, migrations with Alembic.
- FastAPI, Jinja2 templates, HTMX, a little plain JavaScript for countdowns.
- APScheduler inside the web process; `rosehill scrape` also runs standalone.
- pydantic-settings for typed configuration from `.env`.
- pytest, ruff, mypy. Playwright (Python) for dashboard end-to-end tests.

## Architecture

Layers depend inward: `web` and `scraping` adapters depend on `services`,
which depend on `domain` and `pricing`. `domain` and `pricing` have no I/O.

```
src/rosehill/
  domain/       Lot, Money, LotStatus
  pricing/      FeeRule, FeeSchedule, all-in cost, max-bid solver, bid increments
  scraping/     LotSource port, rate-limited caching HTTP client, adapters/
  storage/      SQLAlchemy tables, migrations, repositories
  services/     sync (save, snapshot, detect closings), refresh policy,
                dashboard queries, watchlist
  events.py     in-process event bus (LotUpdated, LotClosed)
  web/          FastAPI routes, templates, static files
  config.py     settings
  cli.py        rosehill serve | scrape | db upgrade
```

Extension points:

- **`LotSource`** (scraping port): API, HTML and headless-browser adapters are
  interchangeable. The sync service only sees the port.
- **`FeeRule`**: a fee schedule is an ordered list of rules (percentage premium,
  flat per-lot fee, tax on a chosen base), built from settings.
- **Max bid** is solved by binary search over valid bid amounts against any fee
  schedule whose total rises with the bid, so new fee rules never break it.
- **Events**: steal scoring and alerts subscribe to `LotUpdated` / `LotClosed`.
- **`ResaleEstimator`**: v1's implementation is the user's manual watchlist
  estimate; marketplace lookups are later adapters.

## Data model

Money columns are integer cents. Times are UTC.

- `lots`: id, source_id (unique), auction_id, title, category, current_bid,
  bid_count, closes_at, status, url, pickup_location, first_seen_at,
  last_scraped_at
- `lot_photos`: lot_id, position, url
- `lot_snapshots`: lot_id, observed_at, current_bid, bid_count, closes_at.
  Written only when a value changed.
- `lot_closings`: lot_id (unique), closed_at, final_bid, bid_count, title,
  category. The price history.
- `watchlist`: lot_id, resale_estimate, max_bid, notes, added_at
- `settings`: key, JSON value (fee schedule, refresh intervals)
- `scrape_runs`: started_at, finished_at, source, lots_seen, errors
- `http_cache`: url, fetched_at, etag, body

## Refresh policy (defaults, configurable)

- Full sweep of all active lots every 60 minutes.
- Lots closing within 2 hours: every 5 minutes.
- Lots closing within 15 minutes: every minute.
- A global rate limit caps total requests regardless of tiers.
- A lot is closed once its closing time has passed and the source reports it
  closed, which handles extended (soft-close) endings. Its last observed bid
  is then written to `lot_closings`.

## Fees (defaults, configurable)

Buyer's premium as a percentage of the bid, then Ontario HST (13%) on bid plus
premium. Exact Rosehill rates are to be confirmed from the site's terms and
entered in settings.

## Build order

0. `chore/bootstrap` — project skeleton, tooling, README, `.env.example`.
1. Site investigation with Playwright → pick the `LotSource` adapter.
2. `feat/scraper` — port, adapter, rate-limited caching client.
3. `feat/database` — tables, migrations, repositories, sync, refresh scheduler.
4. `feat/dashboard` — closing-soon view with real data.
5. `feat/calculators` — fees and max bid (test-first), settings page.
6. `feat/watchlist`.

Each milestone ends with passing tests and a code review before merging.

## Open items

- How the site delivers listings (JSON API vs HTML), pagination, login,
  soft-close behaviour, fee terms, `robots.txt`. Blocked until the session's
  network policy allows rosehillonline.ca.
