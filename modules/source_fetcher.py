"""External source retrieval with safe fallbacks."""

from __future__ import annotations

import os

import requests

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "PASTE_KEY_HERE")


def fetch_news_sources(query: str) -> list[dict]:
    try:
        if not query or not NEWS_API_KEY or NEWS_API_KEY == "PASTE_KEY_HERE":
            return []
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&pageSize=5"
        res = requests.get(url, timeout=5).json()

        articles = []
        for article in res.get("articles", []):
            articles.append(
                {
                    "title": article.get("title"),
                    "source": article.get("source", {}).get("name"),
                    "url": article.get("url"),
                    "description": article.get("description") or "",
                }
            )

        return articles
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
