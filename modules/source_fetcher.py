"""External source retrieval with trust filtering, stance detection, and safe fallbacks."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import requests

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()

FILLER_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "just",
    "really",
    "actually",
    "that",
    "this",
    "these",
    "those",
    "my",
    "your",
    "their",
    "our",
    "of",
    "to",
    "for",
    "with",
    "about",
    "on",
    "in",
    "at",
    "from",
    "by",
}

TRUST_SCORES = {
    "bbc": 1.0,
    "reuters": 1.0,
    "who": 1.0,
    "cdc": 1.0,
    "nytimes": 1.0,
}


def rewrite_claim_as_search_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9\-\+]+", query or "")
    kept: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        lowered = token.lower()
        if lowered in FILLER_WORDS:
            continue
        if lowered not in seen:
            seen.add(lowered)
            kept.append(token)
    kept.extend(term for term in ["fact check", "study", "evidence", "research"] if term not in seen)
    return " ".join(kept).strip()


def build_query(claim: str) -> str:
    rewritten = rewrite_claim_as_search_query(claim)
    if not rewritten:
        return ""
    query = f"{rewritten} news"
    return re.sub(r"\s+", " ", query).strip()


def classify_claim_type(claim: str) -> str:
    lowered = (claim or "").lower()
    if any(word in lowered for word in ["war", "election", "president", "attack", "strike", "ceasefire", "bomb", "bombed", "missile", "airstrike"]):
        return "current_event"
    if any(word in lowered for word in ["cures", "causes", "leads to", "spreads"]):
        return "scientific_claim"
    if any(word in lowered for word in ["is", "are", "was", "were"]):
        return "fact"
    return "unknown"


def is_relevant(article: dict, query_keywords: list[str]) -> bool:
    text = (article.get("title", "") + " " + article.get("description", "")).lower()
    keyword_match = sum(1 for keyword in query_keywords if keyword and keyword in text)
    strong_signals = any(
        word in text for word in ["study", "research", "scientists", "fact check", "evidence"]
    )
    return keyword_match >= 2 or strong_signals


def relevance_score(article: dict, query: str) -> int:
    text = (article.get("title", "") + " " + article.get("description", "")).lower()
    return sum(1 for word in query.lower().split() if word and word in text)


def detect_stance(text: str) -> str:
    lowered = (text or "").lower()
    if any(word in lowered for word in ["false", "myth", "debunk", "no evidence", "fact check"]):
        return "REFUTES"
    if any(word in lowered for word in ["confirmed", "study shows", "evidence suggests", "research finds"]):
        return "SUPPORTS"
    return "NEUTRAL"


def get_source_score(url: str) -> float:
    lowered = (url or "").lower()
    for key in TRUST_SCORES:
        if key in lowered:
            return 1.0
    return 0.5


def compute_trust_score(sources: list[dict]) -> float:
    if not sources:
        return 0.0
    scores = [get_source_score(source.get("url", "")) for source in sources if source.get("url")]
    return sum(scores) / len(scores) if scores else 0.0


def filter_sources(sources: list[dict]) -> list[dict]:
    clean: list[dict] = []
    for source in sources or []:
        url = source.get("url") or ""
        if not url:
            continue
        score = get_source_score(url)
        if score >= 0.7:
            clean.append({**source, "credibility": score})
    return clean[:5]


def compute_confidence(trust_score: float, support: int, refute: int) -> float:
    base = 50
    consensus_strength = abs(support - refute) * 10
    trust_component = trust_score * 30
    return min(base + consensus_strength + trust_component, 95)


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _explain_source_match(article: dict, query_keywords: list[str]) -> str:
    text = (article.get("title", "") + " " + article.get("description", "")).lower()
    matched_keywords = [keyword for keyword in query_keywords if keyword and keyword in text][:3]
    strong_terms = [term for term in ["study", "research", "scientists", "fact check", "evidence"] if term in text][:2]
    reasons: list[str] = []
    if strong_terms:
        reasons.append("Mentions " + ", ".join(f'"{term}"' for term in strong_terms))
    if matched_keywords:
        reasons.append("matches keywords " + ", ".join(f'"{term}"' for term in matched_keywords))
    return " + ".join(reasons) if reasons else "Matches the verification search intent"


def _fetch_serpapi_news(query: str) -> list[dict]:
    if not query or not SERPAPI_KEY:
        return []
    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "tbm": "nws",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": 10,
            "hl": "en",
        },
        timeout=6,
    )
    payload = response.json()
    results = payload.get("news_results", []) if isinstance(payload, dict) else []
    articles: list[dict] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        source_name = ""
        source_data = result.get("source")
        if isinstance(source_data, dict):
            source_name = source_data.get("name", "")
        elif isinstance(source_data, str):
            source_name = source_data
        articles.append(
            {
                "title": result.get("title") or "",
                "source": source_name or _extract_domain(result.get("link", "")) or "Unknown source",
                "url": result.get("link") or "",
                "description": result.get("snippet") or "",
                "published_at": result.get("date") or "",
            }
        )
    return articles


def fetch_news_sources(query: str) -> list[dict]:
    try:
        search_query = build_query(query)
        if not search_query:
            return []

        raw_articles = _fetch_serpapi_news(search_query)
        if not raw_articles:
            return []

        query_keywords = [word for word in search_query.lower().split() if len(word) > 2]
        filtered_articles = [article for article in raw_articles if is_relevant(article, query_keywords)]
        ranked_articles = sorted(
            filtered_articles or raw_articles,
            key=lambda article: relevance_score(article, search_query),
            reverse=True,
        )
        trusted_articles = filter_sources(ranked_articles)

        enriched: list[dict] = []
        for article in trusted_articles:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            enriched.append(
                {
                    **article,
                    "search_query": search_query,
                    "relevance_score": relevance_score(article, search_query),
                    "stance": detect_stance(text),
                    "why": _explain_source_match(article, query_keywords),
                    "domain": _extract_domain(article.get("url", "")),
                }
            )
        return enriched[:5]
    except Exception:
        return []


def fetch_wikipedia_summary(query: str) -> str:
    try:
        if not query:
            return ""
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
        res = requests.get(url, timeout=5).json()
        return res.get("extract", "")
    except Exception:
        return ""
