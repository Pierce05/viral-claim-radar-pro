"""Live update fetching with deterministic offline fallbacks."""

from __future__ import annotations

import os
from datetime import datetime

import requests

from modules.utils import clean_sentence, get_project_root, safe_load_json

CACHE_PATH = os.path.join(get_project_root(), "data", "live_updates_cache.json")

REGIONS = [
    "Global",
    "United States",
    "Europe",
    "Asia",
    "Africa",
    "Middle East",
    "Latin America",
]

TOPICS = [
    "All",
    "Public Health",
    "Misinformation",
    "Energy",
    "AI",
    "Science",
]

SIMULATED_UPDATES = [
    {
        "headline": "WHO says seasonal disease monitoring is increasing across several countries",
        "claim": "Global disease monitoring activity is increasing this season.",
        "source": "WHO; Reuters",
        "source_count": 3,
        "corroborating_sources": ["WHO", "Reuters", "AP"],
        "conflicting_reports": False,
        "region": "Global",
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
        "region": "Europe",
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
        "region": "United States",
        "category": "AI",
        "published_at": "2026-03-24T11:15:00",
        "url": "",
    },
]


def get_available_regions() -> list[str]:
    return REGIONS


def get_available_topics() -> list[str]:
    return TOPICS


def _normalize_region(value: str) -> str:
    legacy_map = {
        "health & science": "Global",
        "technology": "United States",
        "climate": "Europe",
    }
    cleaned = clean_sentence(value) or "Global"
    lowered = cleaned.lower()
    return legacy_map.get(lowered, cleaned if cleaned in REGIONS else "Global")


def _normalize_topic(value: str) -> str:
    cleaned = clean_sentence(value) or "General"
    return cleaned if cleaned in TOPICS else cleaned


def _sanitize_update(item: dict) -> dict:
    return {
        "headline": clean_sentence(item.get("headline")) or "No headline available",
        "claim": clean_sentence(item.get("claim")) or clean_sentence(item.get("headline")) or "No claim available",
        "source": clean_sentence(item.get("source")) or "Local simulated feed",
        "source_count": max(0, int(item.get("source_count", 1) or 1)),
        "corroborating_sources": item.get("corroborating_sources") if isinstance(item.get("corroborating_sources"), list) else [],
        "conflicting_reports": bool(item.get("conflicting_reports", False)),
        "contradicting_sources": item.get("contradicting_sources") if isinstance(item.get("contradicting_sources"), list) else [],
        "region": _normalize_region(item.get("region")),
        "category": _normalize_topic(item.get("category")),
        "published_at": clean_sentence(item.get("published_at")) or datetime.now().isoformat(timespec="seconds"),
        "url": clean_sentence(item.get("url")),
    }


def _cached_updates() -> list[dict]:
    raw = safe_load_json(CACHE_PATH, default=SIMULATED_UPDATES)
    if not isinstance(raw, list):
        raw = SIMULATED_UPDATES
    updates = [_sanitize_update(item) for item in raw if isinstance(item, dict)]
    return updates or [_sanitize_update(item) for item in SIMULATED_UPDATES]


def _compose_query(region: str, topic: str) -> str:
    region_terms = {
        "Global": "",
        "United States": "United States OR US OR America",
        "Europe": "Europe OR European Union OR EU",
        "Asia": "Asia",
        "Africa": "Africa",
        "Middle East": "\"Middle East\" OR Gulf OR Israel OR UAE OR Saudi",
        "Latin America": "\"Latin America\" OR Brazil OR Mexico OR Argentina OR Chile",
    }
    topic_terms = {
        "All": "misinformation OR fact check OR public health OR technology OR science OR energy",
        "Public Health": "\"public health\" OR vaccine OR outbreak OR WHO OR CDC",
        "Misinformation": "misinformation OR debunked OR false claim OR fact check OR hoax",
        "Energy": "energy OR climate OR renewables OR emissions",
        "AI": "\"artificial intelligence\" OR AI OR deepfake OR synthetic media",
        "Science": "science OR research OR study OR scientists",
    }
    region_part = region_terms.get(region, "")
    topic_part = topic_terms.get(topic, topic)
    return " AND ".join(part for part in [topic_part, region_part] if part)


def _live_news_updates(region: str, topic: str, api_key: str, max_items: int) -> list[dict]:
    query = _compose_query(region, topic)
    if not query:
        return []
    response = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max(1, max_items),
            "apiKey": api_key,
        },
        timeout=5,
    )
    payload = response.json()
    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    updates: list[dict] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        updates.append(
            _sanitize_update(
                {
                    "headline": article.get("title") or article.get("description") or "Live source update",
                    "claim": article.get("title") or article.get("description") or "Live source update",
                    "source": article.get("source", {}).get("name") or "NewsAPI source",
                    "source_count": 1,
                    "corroborating_sources": [article.get("source", {}).get("name")] if article.get("source", {}).get("name") else [],
                    "conflicting_reports": False,
                    "region": region,
                    "category": topic if topic != "All" else "General",
                    "published_at": article.get("publishedAt") or datetime.now().isoformat(timespec="seconds"),
                    "url": article.get("url") or "",
                }
            )
        )
    return updates


def fetch_updates(region: str = "Global", topic: str = "All", news_api_key: str | None = None, max_items: int = 6) -> dict:
    api_key = news_api_key or os.getenv("NEWS_API_KEY", "")

    valid_region = region if region in REGIONS else "Global"
    valid_topic = topic if topic in TOPICS else "All"

    if api_key:
        try:
            live_updates = _live_news_updates(valid_region, valid_topic, api_key, max_items)
            if live_updates:
                return {
                    "updates": live_updates[: max(1, max_items)],
                    "source": "live",
                    "region": valid_region,
                    "topic": valid_topic,
                }
        except Exception:
            pass

    cached = _cached_updates()
    if valid_region != "Global":
        filtered = [item for item in cached if item.get("region") in {valid_region, "Global"}]
    else:
        filtered = list(cached)
    if valid_topic != "All":
        filtered = [item for item in filtered if item.get("category") == valid_topic]

    if not filtered:
        filtered = [_sanitize_update(item) for item in SIMULATED_UPDATES]
        if valid_topic != "All":
            filtered = [item for item in filtered if item.get("category") == valid_topic] or filtered
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
        "topic": valid_topic,
    }
