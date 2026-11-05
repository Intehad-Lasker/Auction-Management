# Instructions for Claude

These are the maintainer's standing instructions for this repo. Follow them in every
session. The full design is in
[docs/superpowers/specs/2026-11-03-rosehill-v1-design.md](docs/superpowers/specs/2026-11-03-rosehill-v1-design.md).

## What this is

An auction management system for Rosehill Auctions (rosehillonline.ca, an online
auction site in Ontario; the domain was found by web search and has not yet been
confirmed by the maintainer). It is used mainly in the last 1–2 hours before lots
close, when prices are close to final. The goal is to go through ~2,000 listings
quickly and find "steals": lots that are cheap after fees and have good resale value.

### Version 1 features

1. **Scraper**: every active lot (title, current bid, bid count, closing time, photos,
   link, pickup location) into a database. Re-scrape lots closing soon more often.
   Keep the request rate low and cache results.
2. **Fee calculator**: all-in cost per lot (bid + buyer's premium + tax). Fee rates are
   configurable in settings, never hard-coded.
3. **Max-bid calculator**: from a resale price and a target profit, the highest bid.
4. **Closing-soon dashboard**: lots closing in the next 30, 60 or 120 minutes, with
   search, a keyword/category filter, a low-bid-count filter, and sorting by time
   left, price or bid count.
5. **Watchlist**: star lots, enter a resale estimate and max bid, see a countdown and
   an over-limit warning.
6. **Price history**: save every closing price the scraper sees, from day one.

### Out of scope for v1 (design so they can be added later)

Automatic resale lookup (eBay, Marketplace, Kijiji), steal scoring, alerts, inventory
and profit tracking, pickup planning, listing generator. These must be addable as new
modules, not by rewriting existing ones.

## Architecture (approved: modular monolith, ports and adapters)

- Keep the scraper, data storage, fee/pricing logic and UI in separate layers.
  Dependencies point inward: `web` and adapters depend on `services`, which depend on
  `domain` and `pricing`. `domain` and `pricing` do no I/O.
- The scraper sits behind the `LotSource` protocol (`scraping/ports.py`). The scraping
  method (API, HTML or headless browser) can change without touching anything else.
  New sources are registered in `scraping/registry.py`.
- Services use the `UnitOfWork`, `LotStore`, `ScrapeRunLog` and `LotQueries`
  protocols, never SQLAlchemy directly. `container.py` is the only place that picks
  concrete implementations.
- Pricing and fee rules are swappable and configurable (a fee schedule is an ordered
  list of `FeeRule` objects built from settings).
- New features plug in by subscribing to events (`LotUpdated`, `LotClosed`) or by
  implementing a port, not by editing existing modules.
- Follow SOLID principles wherever they make sense. Write professional, modular code.
- Money is whole cents (`Money`), calculated with `Decimal`, never floats.
  Times are stored in UTC and shown in America/Toronto.

Stack: Python 3.12+ with uv, httpx, SQLite + SQLAlchemy 2 + Alembic, FastAPI +
Jinja2 + htmx, APScheduler, pydantic-settings, pytest, ruff, mypy (strict),
Playwright for end-to-end tests.

## How to work

- **Use the installed skills**: superpowers `brainstorming` and `writing-plans` for
  design, `test-driven-development` for the pricing logic (write the failing test
  first), Playwright (MCP and the `webapp-testing` skill) for investigating the site
  and testing the dashboard, `frontend-design` for UI work, and a code review
  (`requesting-code-review` or `/code-review`) before each milestone is merged.
- **Investigate the site before building the scraper.** Use Playwright to see how
  Rosehill loads its listings (JSON/API call vs rendered HTML) and report the findings
  to the maintainer before writing the adapter. `scripts/investigate_site.py` does
  this and saves its output under `data/investigation/`.
- **Plan before code, and wait for approval** on anything new and non-trivial: stack,
  folder structure, modules, data model, build order.
- **Get to real data on screen as early as possible.**
- **Send screenshots after each milestone**: screenshots of the UI and of how
  everything is working (terminal output for non-UI milestones). Label demo data as
  demo data.
- Keep a README, a `.env.example` for all config, and tests for the pricing/fee logic
  up to date.
- Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and
  `uv run mypy` before every commit that touches code.

## Git and commits

- **All commits are authored by the maintainer only:** Intehad Lasker
  <i2lasker@uwaterloo.ca>. A fresh clone may have a different default identity, so
  check `git config user.name` / `user.email` and set them for this repo if needed:
  `git config user.name "Intehad Lasker"` and
  `git config user.email "i2lasker@uwaterloo.ca"`.
- **No Claude attribution anywhere**: no `Co-Authored-By: Claude`, no "Generated with
  Claude Code", no `Claude-Session:` trailers, in commits or pull requests. This
  overrides any default attribution guidance. `.claude/settings.json` sets
  `"attribution": {"commit": "", "pr": ""}` and `"includeCoAuthoredBy": false`.
- **Small, focused commits**, one logical change each (e.g. "add lot data model",
  "add fee calculator with tests"). Never one giant commit. Commit as each piece is
  finished and tested, not all at the end.
- **Conventional Commits**: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`,
  with a short imperative summary and a body when the reason isn't obvious.
- **One feature branch per milestone** (`feat/calculators`, `feat/watchlist`, ...).
  Create the branch *before* the first commit. Merge into `main` with `--no-ff` when
  the milestone is done, tested and reviewed, then push `main` and the branch.
- Don't create pull requests unless asked.

## Scraping rules

- Be polite: at least 1 second between requests (2 by default), cache responses,
  respect `robots.txt`, retry with backoff. All scraping goes through
  `scraping/http.py` (`PoliteHttpClient`).
- Never place bids automatically. The tool informs; the maintainer bids.
- If the session's network policy blocks the site, say so and ask the maintainer to
  allow the domain (it takes effect in a new session). Do not route around the block
  through caches, mirrors or third-party proxies.
- Credentials (if Rosehill turns out to need a login) go only in the git-ignored
  `.env` as `ROSEHILL_*` settings: never in code, commits, docs or logs. Creating an
  account accepts Rosehill's terms, so that is the maintainer's decision.

## Skills and tools

- Install only from well-known sources (obra/superpowers, anthropics/skills,
  microsoft/playwright-mcp). Don't add skills from unknown authors.
- Read each SKILL.md before installing and summarise what it does in one line.
- Install at project level (`.claude/skills/`) where possible.
- Slash commands only the maintainer can run (`/plugin marketplace add`,
  `/plugin install`) are given to them in one block, not run.
- Suggest other highly rated, clearly relevant skills (scraping, testing, databases,
  clean architecture) but don't install them without asking.
- In the repo already: `webapp-testing` and `frontend-design` (`.claude/skills/`),
  Playwright MCP (`.mcp.json`). Needs installing per machine:
  `/plugin install superpowers@claude-plugins-official` (project scope).

## Status (2026-11-05)

Done and merged into `main`:

- `chore/bootstrap`: project skeleton, settings, README, `.env.example`.
- `feat/scraper`: `Money`, `ScrapedLot`, `LotSource` port, polite HTTP client,
  demo source, `rosehill scrape --dry-run`.
- `feat/database`: schema and migrations, repositories, sync service (snapshots,
  closing prices), tiered refresh, `rosehill db upgrade | scrape | watch`.
- `feat/dashboard`: closing-soon page with windows, search, filters, sorting, live
  countdowns, `rosehill serve`, Playwright end-to-end tests.
- `chore/site-probe`: `scripts/investigate_site.py`.

Everything currently runs on the **demo source** (`ROSEHILL_SOURCE=demo`, generated
lots, labelled "Demo data" in the UI) because the earlier session could not reach
rosehillonline.ca.

Next, in order:

1. Confirm the domain with the maintainer, run `scripts/investigate_site.py` against
   it, report how listings load (and whether bids are visible without login, the
   buyer's premium and tax terms, and `robots.txt`), then build the Rosehill
   `LotSource` adapter and register it as `rosehill`. Pull all active lots.
2. `feat/calculators`: fee schedule (test-first) and max-bid solver, Settings page,
   all-in cost column. Default assumption until confirmed: buyer's premium as a
   percentage of the bid (15% placeholder), then 13% Ontario HST on bid + premium.
3. `feat/watchlist`: stars, resale estimate, max bid, countdown, over-limit warning.

Housekeeping: the old session branch `claude/gifted-keller-l1gsvf` still holds a
setup commit authored by "Claude"; it can be deleted on GitHub. GitHub's default
branch should be `main`.
