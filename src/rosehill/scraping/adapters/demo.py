"""A fake lot source for developing and testing without touching the real site.

Lots are generated from a seed, so the same seed always gives the same catalogue.
Bids and bid counts climb as each lot's closing time approaches. Every URL uses the
reserved `.invalid` domain so demo data can never be mistaken for a real listing.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rosehill.domain.lot import ScrapedLot
from rosehill.domain.money import Money

_ITEMS: dict[str, list[tuple[str, int]]] = {
    "Tools": [
        ("DeWalt 20V drill/driver kit", 160),
        ("Milwaukee M18 impact driver", 190),
        ("Ryobi 18V string trimmer", 120),
        ("Makita circular saw", 140),
        ("Craftsman 230-piece mechanics tool set", 150),
        ("Bosch laser level", 110),
    ],
    "Appliances": [
        ("Ninja Foodi air fryer", 130),
        ("KitchenAid stand mixer", 380),
        ("Instant Pot Duo 8 qt", 110),
        ("Breville espresso machine", 520),
        ("Frigidaire induction cooktop", 600),
        ("Dyson V8 cordless vacuum", 290),
    ],
    "Electronics": [
        ('Samsung 55" 4K TV', 480),
        ("Sony WH-1000XM5 headphones", 330),
        ("Apple iPad 10th gen 64GB", 410),
        ("Nintendo Switch OLED", 360),
        ("Bose SoundLink speaker", 150),
        ("Logitech MX Master 3S mouse", 95),
    ],
    "Furniture": [
        ("Solid oak dining table", 450),
        ("Ergonomic mesh office chair", 220),
        ("Three-seat fabric sofa", 650),
        ("IKEA Kallax shelf unit", 90),
        ("Queen bed frame with headboard", 320),
    ],
    "Outdoor": [
        ("Weber Spirit gas BBQ", 520),
        ("Patio set with four chairs", 380),
        ("Greenworks electric lawn mower", 340),
        ("Coleman 6-person tent", 160),
    ],
    "Sports": [
        ("Trek hybrid bike", 520),
        ("Bowflex adjustable dumbbells", 380),
        ("CCM hockey skates", 140),
        ("Yeti Tundra 45 cooler", 300),
    ],
}
_CONDITIONS = ["New in box", "Open box", "Like new", "Used", "Untested", "Customer return"]
_PICKUP = ["Burlington warehouse", "Hamilton warehouse", "Oakville depot"]


@dataclass(frozen=True, slots=True)
class _Template:
    source_id: str
    title: str
    category: str
    pickup: str
    opens_at: datetime
    closes_at: datetime
    start_bid_cents: int
    final_bid_cents: int
    final_bid_count: int
    photo_count: int


class DemoLotSource:
    def __init__(
        self,
        *,
        count: int = 2000,
        seed: int = 7,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._now = now
        anchor = now().replace(second=0, microsecond=0)
        rng = random.Random(seed)
        self._lots = {
            t.source_id: t for t in (self._template(i, anchor, rng) for i in range(count))
        }

    @property
    def name(self) -> str:
        return "demo"

    def fetch_active_lots(self) -> Iterator[ScrapedLot]:
        now = self._now()
        for template in self._lots.values():
            if template.closes_at > now:
                yield self._snapshot(template, now)

    def fetch_lots(self, source_ids: Collection[str]) -> Iterator[ScrapedLot]:
        now = self._now()
        for source_id in source_ids:
            template = self._lots.get(source_id)
            if template is not None:
                yield self._snapshot(template, now)

    @staticmethod
    def _template(index: int, anchor: datetime, rng: random.Random) -> _Template:
        category = rng.choice(list(_ITEMS))
        name, value = rng.choice(_ITEMS[category])
        condition = rng.choice(_CONDITIONS)
        value_cents = int(value * 100 * rng.uniform(0.7, 1.3))
        # Weighted so plenty of lots fall inside the 30/60/120-minute dashboard windows.
        minutes_to_close = rng.choice(
            [rng.uniform(2, 30), rng.uniform(30, 120), rng.uniform(120, 480)]
        )
        closes_at = anchor + timedelta(minutes=minutes_to_close)
        hot = rng.random() < 0.7
        return _Template(
            source_id=f"DEMO-{index + 1:05d}",
            title=f"{name} - {condition}",
            category=category,
            pickup=rng.choice(_PICKUP),
            opens_at=closes_at - timedelta(days=5),
            closes_at=closes_at,
            start_bid_cents=100,
            final_bid_cents=int(value_cents * (rng.uniform(0.35, 0.85) if hot else 0.15)),
            final_bid_count=rng.randint(12, 45) if hot else rng.randint(0, 3),
            photo_count=rng.randint(1, 4),
        )

    @staticmethod
    def _snapshot(t: _Template, now: datetime) -> ScrapedLot:
        duration = (t.closes_at - t.opens_at).total_seconds()
        elapsed = (min(now, t.closes_at) - t.opens_at).total_seconds()
        progress = max(0.0, min(1.0, elapsed / duration))
        # Most bidding happens near the end, so both curves are steep late on.
        bid = t.start_bid_cents + (t.final_bid_cents - t.start_bid_cents) * progress**6
        bids = round(t.final_bid_count * progress**4)
        whole_dollars = max(t.start_bid_cents, int(bid) // 100 * 100) if bids else 0
        return ScrapedLot(
            source_id=t.source_id,
            title=t.title,
            current_bid=Money(whole_dollars),
            bid_count=bids,
            closes_at=t.closes_at,
            url=f"https://demo.invalid/lots/{t.source_id}",
            photos=tuple(
                f"https://demo.invalid/photos/{t.source_id}-{n}.jpg" for n in range(t.photo_count)
            ),
            pickup_location=t.pickup,
            category=t.category,
            auction_id="DEMO",
            is_closed=now >= t.closes_at,
        )
