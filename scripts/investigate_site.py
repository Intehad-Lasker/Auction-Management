"""Record how an auction site loads its listings, so a scraper adapter can be written.

Opens each page in headless Chromium, waits for it to settle, scrolls once to trigger
lazy loading, and saves:

  summary.md        what was requested, which responses were JSON, robots.txt verdicts
  requests.json     every request: method, URL, status, content type, size
  json/NNN.json     the body of each JSON response (first --max-json of them)
  pages/NN.html     the rendered HTML of each page
  pages/NN.png      a full-page screenshot of each page
  robots.txt        the site's robots.txt, if it has one

It only reads public pages: no login, no clicking, no form submission. Pages that
robots.txt disallows are skipped.

Usage:
  uv run python scripts/investigate_site.py https://rosehillonline.ca
  uv run python scripts/investigate_site.py https://rosehillonline.ca https://rosehillonline.ca/auctions
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Response, sync_playwright

USER_AGENT = "rosehill-auction-manager/0.1 (personal use; site investigation)"


@dataclass
class Captured:
    page: int
    method: str
    url: str
    resource_type: str
    status: int
    content_type: str
    size: int
    json_file: str | None = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("urls", nargs="+", help="pages to open, e.g. the home and auction list")
    parser.add_argument("--out", type=Path, default=None, help="output folder")
    parser.add_argument("--max-json", type=int, default=40, help="JSON bodies to keep")
    parser.add_argument("--pause", type=float, default=3.0, help="seconds between pages")
    args = parser.parse_args(argv)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out: Path = args.out or Path("data") / "investigation" / stamp
    (out / "json").mkdir(parents=True, exist_ok=True)
    (out / "pages").mkdir(parents=True, exist_ok=True)

    robots = _load_robots(args.urls[0], out)
    captured: list[Captured] = []
    skipped: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            user_agent=USER_AGENT, viewport={"width": 1366, "height": 900}
        )
        page = context.new_page()
        page_number = 0

        def on_response(response: Response) -> None:
            request = response.request
            content_type = response.headers.get("content-type", "")
            try:
                body = response.body()
            except Exception:  # redirects and aborted requests have no body
                body = b""
            item = Captured(
                page=page_number,
                method=request.method,
                url=response.url,
                resource_type=request.resource_type,
                status=response.status,
                content_type=content_type,
                size=len(body),
            )
            json_count = sum(1 for c in captured if c.json_file)
            if "json" in content_type and body and json_count < args.max_json:
                name = f"json/{json_count + 1:03d}.json"
                try:
                    parsed = json.loads(body)
                    (out / name).write_text(json.dumps(parsed, indent=2)[:2_000_000])
                except ValueError:
                    (out / name).write_bytes(body[:2_000_000])
                item.json_file = name
            captured.append(item)

        page.on("response", on_response)

        for page_number, url in enumerate(args.urls, start=1):
            if robots and not robots.can_fetch(USER_AGENT, url):
                skipped.append(url)
                continue
            print(f"opening {url}")
            page.goto(url, wait_until="networkidle", timeout=60_000)
            page.mouse.wheel(0, 4000)  # trigger lazy-loaded listings, if any
            page.wait_for_timeout(2500)
            (out / "pages" / f"{page_number:02d}.html").write_text(page.content())
            page.screenshot(path=out / "pages" / f"{page_number:02d}.png", full_page=True)
            time.sleep(args.pause)

        browser.close()

    (out / "requests.json").write_text(json.dumps([asdict(c) for c in captured], indent=2))
    (out / "summary.md").write_text(_summary(args.urls, captured, skipped, robots is not None))
    print(f"saved to {out}")
    return 0


def _load_robots(url: str, out: Path) -> urllib.robotparser.RobotFileParser | None:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser(robots_url)
    try:
        parser.read()
    except Exception as exc:
        print(f"could not read {robots_url}: {exc}", file=sys.stderr)
        return None
    try:
        with urllib.request.urlopen(robots_url, timeout=20) as response:
            (out / "robots.txt").write_bytes(response.read())
    except Exception:
        pass
    return parser


def _summary(
    urls: list[str], captured: list[Captured], skipped: list[str], has_robots: bool
) -> str:
    lines = ["# Site investigation", "", f"Run at {datetime.now(UTC).isoformat()}", ""]
    lines += ["## Pages", ""] + [f"- {u}" for u in urls] + [""]
    if skipped:
        lines += ["## Skipped (disallowed by robots.txt)", ""] + [f"- {u}" for u in skipped] + [""]
    if not has_robots:
        lines += ["robots.txt could not be read.", ""]
    api_calls = [c for c in captured if c.resource_type in ("xhr", "fetch")]
    lines += [f"## XHR/fetch requests ({len(api_calls)})", ""]
    for c in api_calls:
        saved = f" -> {c.json_file}" if c.json_file else ""
        lines.append(f"- {c.method} {c.status} {c.content_type or '?'} {c.size}B {c.url}{saved}")
    hosts = sorted({urlsplit(c.url).netloc for c in captured})
    lines += ["", "## Hosts contacted", ""] + [f"- {h}" for h in hosts] + [""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
