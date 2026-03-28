"""Insight engine for session analysis and dashboard summaries."""

from __future__ import annotations

from collections import Counter, defaultdict

from modules.utils import normalize_text

TOPIC_TAXONOMY = {
    "Health & Medicine": ["vaccine", "virus", "health", "disease", "cancer", "dna", "autism", "exercise"],
    "Climate & Environment": ["climate", "renewable", "solar", "wind", "emission", "carbon", "environment"],
    "Technology & AI": ["ai", "deepfake", "algorithm", "cyber", "platform", "5g", "technology"],
    "Space & Astronomy": ["space", "moon", "nasa", "planet", "astronaut", "rocket"],
    "Economy & Finance": ["bitcoin", "bank", "market", "trade", "economy", "crypto"],
}

KNOWN_DISINFO_PATTERNS = [
    {"label": "Vaccine-Autism Link", "severity": "high", "keywords": ["vaccine", "autism"], "description": "A debunked vaccine-autism narrative."},
    {"label": "5G Disease Link", "severity": "high", "keywords": ["5g", "covid"], "description": "Radio network infrastructure cannot spread viruses."},
    {"label": "Miracle Cure Claim", "severity": "high", "keywords": ["miracle", "cure"], "description": "Cure-all framing without evidence is a classic misinformation pattern."},
    {"label": "Moon Hoax Narrative", "severity": "medium", "keywords": ["moon", "staged"], "description": "Moon-hoax claims conflict with extensive historical evidence."},
]


def detect_topics(text: str) -> list[str]:
    normalized = normalize_text(text)
    scored: list[tuple[str, int]] = []
    for topic, keywords in TOPIC_TAXONOMY.items():
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score:
            scored.append((topic, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [topic for topic, _ in scored[:2]] or ["General"]


def compute_label_distribution(items: list[dict], label_key: str = "label") -> dict:
    labels = [item.get(label_key, "Uncertain") for item in items if isinstance(item, dict)]
    total = len(labels)
    if total == 0:
        return {"Supported": 0.0, "Refuted": 0.0, "Uncertain": 0.0, "total": 0, "counts": {}}
    counter = Counter(labels)
    return {
        "Supported": round(counter.get("Supported", 0) / total * 100, 1),
        "Refuted": round(counter.get("Refuted", 0) / total * 100, 1),
        "Uncertain": round(counter.get("Uncertain", 0) / total * 100, 1),
        "total": total,
        "counts": dict(counter),
    }


def compute_topic_distribution(items: list[dict], text_keys: list[str] | None = None) -> dict:
    keys = text_keys or ["claim", "headline", "explanation"]
    counts = Counter()
    labels_by_topic: dict[str, list[str]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        combined = " ".join(str(item.get(key, "")) for key in keys if item.get(key))
        for topic in detect_topics(combined):
            counts[topic] += 1
            labels_by_topic[topic].append(item.get("label", "Uncertain"))
    enriched = {}
    for topic, count in counts.most_common():
        label_counter = Counter(labels_by_topic[topic])
        total = max(1, len(labels_by_topic[topic]))
        enriched[topic] = {
            "count": count,
            "refuted_pct": round(label_counter.get("Refuted", 0) / total * 100, 1),
            "supported_pct": round(label_counter.get("Supported", 0) / total * 100, 1),
            "uncertain_pct": round(label_counter.get("Uncertain", 0) / total * 100, 1),
        }
    return enriched


def detect_recurring_disinfo(items: list[dict], text_keys: list[str] | None = None) -> list[dict]:
    keys = text_keys or ["claim", "headline", "explanation"]
    findings: list[dict] = []
    seen: set[str] = set()
    for item in items:
        combined = " ".join(str(item.get(key, "")) for key in keys if isinstance(item, dict))
        normalized = normalize_text(combined)
        for pattern in KNOWN_DISINFO_PATTERNS:
            if pattern["label"] in seen:
                continue
            hits = sum(1 for keyword in pattern["keywords"] if keyword in normalized)
            if hits >= max(1, len(pattern["keywords"]) - 1):
                seen.add(pattern["label"])
                findings.append(
                    {
                        "pattern": pattern["label"],
                        "severity": pattern["severity"],
                        "description": pattern["description"],
                        "match_strength": round((hits / len(pattern["keywords"])) * 100, 1),
                        "example_claim": item.get("claim") or item.get("headline") or "",
                    }
                )
    return findings


def compute_confidence_trend(items: list[dict]) -> dict:
    scores = [float(item.get("confidence", 0)) for item in items if isinstance(item, dict) and item.get("confidence") is not None]
    if not scores:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "trend": "stable", "scores": []}
    avg = round(sum(scores) / len(scores), 1)
    trend = "stable"
    if len(scores) >= 4:
        midpoint = len(scores) // 2
        first = sum(scores[:midpoint]) / max(1, midpoint)
        second = sum(scores[midpoint:]) / max(1, len(scores) - midpoint)
        if second >= first + 5:
            trend = "rising"
        elif second <= first - 5:
            trend = "falling"
    return {"avg": avg, "min": round(min(scores), 1), "max": round(max(scores), 1), "trend": trend, "scores": scores}


def compute_source_diversity(items: list[dict]) -> dict:
    if not items:
        return {"avg_sources": 0.0, "high_authority_pct": 0.0, "authority_distribution": {}, "diversity_score": 0.0}
    sources = [max(0, int(item.get("source_count", 0) or 0)) for item in items if isinstance(item, dict)]
    authorities = [item.get("authority_label", "") for item in items if isinstance(item, dict)]
    high = sum(1 for label in authorities if "High" in label)
    avg_sources = round(sum(sources) / max(1, len(sources)), 1) if sources else 0.0
    return {
        "avg_sources": avg_sources,
        "high_authority_pct": round((high / max(1, len(authorities))) * 100, 1) if authorities else 0.0,
        "authority_distribution": dict(Counter(authorities)),
        "diversity_score": round(min(100.0, avg_sources * 22), 1),
    }


def compute_region_breakdown(items: list[dict]) -> dict:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in items:
        region = item.get("region", "Global") if isinstance(item, dict) else "Global"
        grouped[region].append(item.get("label", "Uncertain"))
    output = {}
    for region, labels in grouped.items():
        total = max(1, len(labels))
        counter = Counter(labels)
        output[region] = {
            "total": len(labels),
            "supported_pct": round(counter.get("Supported", 0) / total * 100, 1),
            "refuted_pct": round(counter.get("Refuted", 0) / total * 100, 1),
            "uncertain_pct": round(counter.get("Uncertain", 0) / total * 100, 1),
        }
    return output


def generate_insights(fact_check_results: list[dict] | None = None, live_update_results: list[dict] | None = None, dataset: list[dict] | None = None) -> dict:
    fact_items = fact_check_results or []
    live_items = live_update_results or []
    session_items = [item for item in fact_items + live_items if isinstance(item, dict)]
    base_items = session_items if session_items else (dataset or [])

    label_distribution = compute_label_distribution(base_items)
    topic_distribution = compute_topic_distribution(base_items)
    recurring_disinfo = detect_recurring_disinfo(base_items)
    confidence_trend = compute_confidence_trend(base_items)
    source_diversity = compute_source_diversity(live_items)
    region_breakdown = compute_region_breakdown(live_items)
    dataset_items = dataset or []
    dataset_insights = {
        "label_distribution": compute_label_distribution(dataset_items),
        "topic_distribution": compute_topic_distribution(dataset_items),
        "total_claims": len(dataset_items),
    }

    bullets: list[str] = []
    if label_distribution["total"] == 0:
        bullets.append("No analysis history yet. The dashboard is showing the bundled local knowledge base.")
    else:
        dominant = max(["Supported", "Refuted", "Uncertain"], key=lambda key: label_distribution[key])
        bullets.append(f"{label_distribution[dominant]:.0f}% of analyzed items currently lean {dominant.lower()}.")
    if topic_distribution:
        topic, data = next(iter(topic_distribution.items()))
        bullets.append(f"Most active topic is {topic} with {data['count']} tracked item(s).")
    if recurring_disinfo:
        bullets.append(f"{len(recurring_disinfo)} recurring misinformation pattern(s) were detected in the current data.")
    if source_diversity.get("avg_sources", 0) > 0:
        bullets.append(f"Live radar items average {source_diversity['avg_sources']:.1f} corroborating source signal(s).")

    return {
        "label_distribution": label_distribution,
        "topic_distribution": topic_distribution,
        "recurring_disinfo": recurring_disinfo,
        "confidence_trend": confidence_trend,
        "source_diversity": source_diversity,
        "region_breakdown": region_breakdown,
        "dataset_insights": dataset_insights,
        "summary_bullets": bullets,
        "total_analyzed": len(base_items),
        "has_session_data": bool(session_items),
    }
