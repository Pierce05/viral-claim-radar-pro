"""Live update fetching with deterministic offline fallbacks."""

from __future__ import annotations

import os
from datetime import datetime

from modules.utils import clean_sentence, get_project_root, safe_load_json

CACHE_PATH = os.path.join(get_project_root(), "data", "live_updates_cache.json")

REGIONS = [
    "Global",
    "United States",
    "Europe",
    "Asia",
    "Health & Science",
    "Technology",
    "Climate",
]

SIMULATED_UPDATES = [
    {
        "headline": "WHO says seasonal disease monitoring is increasing across several countries",
        "claim": "Global disease monitoring activity is increasing this season.",
        "source": "WHO; Reuters",
        "source_count": 3,
        "corroborating_sources": ["WHO", "Reuters", "AP"],
        "conflicting_reports": False,
        "region": "Health & Science",
        "category": "Public Health",
        "published_at": "2026-03-24T09:00:00",
        "url": "",
    },
    {
        "headline": "Researchers warn viral posts are again claiming vaccines alter DNA",
        "claim": "Vaccines alter human DNA.",
        "source": "BBC Verify; CDC",
        "source_count": 2,
        "corroborating_sources": ["BBC Verify", "CDC"],
        "conflicting_reports": True,
        "contradicting_sources": ["CDC"],
        "region": "Global",
        "category": "Misinformation",
        "published_at": "2026-03-24T10:00:00",
        "url": "",
    },
    {
        "headline": "Satellite agencies report another year of strong renewable deployment",
        "claim": "Renewable energy deployment remains strong.",
        "source": "IEA; Financial Times",
        "source_count": 2,
        "corroborating_sources": ["IEA", "Financial Times"],
        "conflicting_reports": False,
        "region": "Climate",
        "category": "Energy",
        "published_at": "2026-03-24T08:30:00",
        "url": "",
    },
    {
        "headline": "AI-generated deepfakes are being used in new election misinformation campaigns",
        "claim": "AI deepfakes are being used in misinformation campaigns.",
        "source": "AP; Stanford Internet Observatory",
        "source_count": 2,
        "corroborating_sources": ["AP", "Stanford Internet Observatory"],
        "conflicting_reports": False,
        "region": "Technology",
        "category": "AI",
        "published_at": "2026-03-24T11:15:00",
        "url": "",
    },
]


def get_available_regions() -> list[str]:
    return REGIONS


def _sanitize_update(item: dict) -> dict:
    return {
        "headline": clean_sentence(item.get("headline")) or "No headline available",
        "claim": clean_sentence(item.get("claim")) or clean_sentence(item.get("headline")) or "No claim available",
        "source": clean_sentence(item.get("source")) or "Local simulated feed",
        "source_count": max(0, int(item.get("source_count", 1) or 1)),
        "corroborating_sources": item.get("corroborating_sources") if isinstance(item.get("corroborating_sources"), list) else [],
        "conflicting_reports": bool(item.get("conflicting_reports", False)),
        "contradicting_sources": item.get("contradicting_sources") if isinstance(item.get("contradicting_sources"), list) else [],
        "region": clean_sentence(item.get("region")) or "Global",
        "category": clean_sentence(item.get("category")) or "General",
        "published_at": clean_sentence(item.get("published_at")) or datetime.now().isoformat(timespec="seconds"),
        "url": clean_sentence(item.get("url")),
    }


def _cached_updates() -> list[dict]:
    raw = safe_load_json(CACHE_PATH, default=SIMULATED_UPDATES)
    if not isinstance(raw, list):
        raw = SIMULATED_UPDATES
    updates = [_sanitize_update(item) for item in raw if isinstance(item, dict)]
    return updates or [_sanitize_update(item) for item in SIMULATED_UPDATES]


def fetch_updates(region: str = "Global", news_api_key: str | None = None, max_items: int = 6) -> dict:
    del news_api_key

    valid_region = region if region in REGIONS else "Global"
    cached = _cached_updates()
    if valid_region != "Global":
        filtered = [item for item in cached if item.get("region") in {valid_region, "Global"}]
    else:
        filtered = list(cached)

    if not filtered:
        filtered = [_sanitize_update(item) for item in SIMULATED_UPDATES]
        source = "simulated"
    else:
        source = "cached"

    if not filtered:
        filtered = [
            _sanitize_update(
                {
                    "headline": "Local fallback feed remains active for demo resilience",
                    "claim": "Fallback live update feed is active.",
                    "source": "Local fallback",
                    "source_count": 1,
                    "region": valid_region,
                }
            )
        ]
        source = "simulated"

    return {
        "updates": filtered[: max(1, max_items)],
        "source": source,
        "region": valid_region,
    }
