"""Credibility scoring engine for live updates."""

from __future__ import annotations

import re

from modules.retriever import find_contradicting_claims
from modules.utils import clamp, ensure_label, normalize_text

HIGH_AUTHORITY_SOURCES = {
    "reuters", "ap", "associated press", "bbc", "who", "cdc", "nasa",
    "nature", "science", "lancet", "nejm", "new york times", "wsj",
    "nih", "fda", "ipcc", "un", "financial times", "stanford",
}

LOW_AUTHORITY_SIGNALS = {
    "anonymous", "viral", "unverified", "rumor", "conspiracy", "telegram",
    "whatsapp", "4chan", "single source", "unknown",
}


def score_source_authority(source_str: str, corroborating: list[str]) -> dict:
    text = normalize_text(source_str) + " " + " ".join(normalize_text(item) for item in corroborating)
    hits = [item for item in HIGH_AUTHORITY_SOURCES if item in text]
    low_hits = [item for item in LOW_AUTHORITY_SIGNALS if item in text]
    score = clamp(50 + len(hits) * 12 - len(low_hits) * 15, 10, 95)
    if score >= 75:
        label = "High Authority"
    elif score >= 50:
        label = "Moderate Authority"
    elif score >= 30:
        label = "Low Authority"
    else:
        label = "Unreliable Source"
    return {
        "authority_score": score,
        "authority_label": label,
        "detected_authority_sources": hits,
        "low_authority_signals": low_hits,
    }


def score_source_count(source_count: int, corroborating: list[str]) -> dict:
    count = max(int(source_count or 0), len(corroborating or []))
    if count >= 4:
        score, label = 90, "Widely Corroborated"
    elif count == 3:
        score, label = 75, "Well Corroborated"
    elif count == 2:
        score, label = 60, "Partially Corroborated"
    elif count == 1:
        score, label = 35, "Single Source"
    else:
        score, label = 20, "No Clear Source"
    return {"count_score": score, "count_label": label, "effective_source_count": count}


def score_conflict(conflicting_reports: bool, contradicting_sources: list[str], update_text: str, dataset: list[dict]) -> dict:
    conflict_score = 0
    reasons: list[str] = []

    if conflicting_reports:
        conflict_score += 30
        reasons.append("Feed metadata shows conflicting reporting.")

    if contradicting_sources:
        reasons.append(f"Contradicting sources noted: {', '.join(contradicting_sources[:3])}.")

    contradicting = find_contradicting_claims(update_text, dataset=dataset, top_k=2) if dataset else []
    if contradicting:
        top = contradicting[0]
        conflict_score += min(35, int(top.get("similarity_score", 0) * 0.45))
        reasons.append(f"Closest local contradiction: '{top.get('claim', '')}'.")

    if re.search(r"\bmiracle\b|\bsecretly\b|\b100%\b|\bthey don't want you to know\b", normalize_text(update_text)):
        conflict_score += 18
        reasons.append("Headline contains alarmist language.")

    return {
        "conflict_score": clamp(conflict_score, 0, 100),
        "conflict_reasons": reasons,
        "has_conflicts": conflict_score > 0,
    }


def compute_verdict(authority: dict, count: dict, conflict: dict) -> dict:
    final_score = (authority.get("authority_score", 50) * 0.4) + (count.get("count_score", 35) * 0.35) - (conflict.get("conflict_score", 0) * 0.3)
    final_score = round(clamp(final_score, 5, 97), 1)
    if conflict.get("conflict_score", 0) >= 45 and final_score < 45:
        label = "Refuted"
    elif final_score >= 74:
        label = "Supported"
    elif final_score >= 45:
        label = "Uncertain"
    else:
        label = "Refuted"
    return {
        "label": ensure_label(label),
        "confidence": final_score,
    }


def assess_credibility(update: dict, dataset: list[dict] | None = None) -> dict:
    item = update or {}
    headline = item.get("headline") or "No headline available"
    claim = item.get("claim") or headline
    source = item.get("source") or "Unknown source"
    corroborating = item.get("corroborating_sources") if isinstance(item.get("corroborating_sources"), list) else []
    contradicting_sources = item.get("contradicting_sources") if isinstance(item.get("contradicting_sources"), list) else []

    authority = score_source_authority(source, corroborating)
    count = score_source_count(item.get("source_count", 1), corroborating)
    conflict = score_conflict(bool(item.get("conflicting_reports")), contradicting_sources, claim, dataset or [])
    verdict = compute_verdict(authority, count, conflict)

    reasoning_parts = []
    if authority.get("detected_authority_sources"):
        reasoning_parts.append("Authoritative sources detected in the source mix.")
    reasoning_parts.append(f"{count.get('count_label', 'No Clear Source')} with {count.get('effective_source_count', 0)} source signal(s).")
    reasoning_parts.extend(conflict.get("conflict_reasons", []))
    reasoning = " ".join(reasoning_parts).strip() or "Assessment completed with limited signals."

    return {
        "headline": headline,
        "claim": claim,
        "label": verdict["label"],
        "confidence": verdict["confidence"],
        "reasoning": reasoning,
        "source": source,
        "source_count": count.get("effective_source_count", 0),
        "authority_label": authority.get("authority_label", "Moderate Authority"),
        "count_label": count.get("count_label", "No Clear Source"),
        "has_conflicts": conflict.get("has_conflicts", False),
        "conflict_reasons": conflict.get("conflict_reasons", []),
        "region": item.get("region", "Global") or "Global",
        "category": item.get("category", "General") or "General",
        "published_at": item.get("published_at", ""),
        "url": item.get("url", ""),
        "assessment_note": "Credibility score is a signal, not a guarantee of truth.",
    }


def assess_batch(updates: list[dict], dataset: list[dict] | None = None) -> list[dict]:
    safe_updates = updates or []
    return [assess_credibility(update, dataset=dataset) for update in safe_updates]


def compute_source_consensus(sources: list[dict]) -> dict:
    support = 0
    refute = 0

    for source in sources or []:
        stance = str(source.get("stance", "")).upper()
        text = f"{source.get('title', '')} {source.get('description', '')}".lower()
        if stance == "REFUTES" or any(keyword in text for keyword in ["no evidence", "false", "myth", "debunked"]):
            refute += 1
        elif stance == "SUPPORTS" or any(keyword in text for keyword in ["study shows", "confirmed", "research finds"]):
            support += 1

    return {
        "support": support,
        "refute": refute,
    }
