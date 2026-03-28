"""SerpAPI-backed Google retrieval for verification articles."""

from __future__ import annotations

import os

import requests


def _get_serp_api_key() -> str:
    env_value = os.getenv("SERP_API_KEY", "").strip()
    if env_value:
        return env_value
    try:
        import streamlit as st  # type: ignore

        return str(st.secrets.get("SERP_API_KEY", "")).strip()
    except Exception:
        return ""


def has_google_source_access() -> bool:
    return bool(_get_serp_api_key())


def fetch_google_sources(query: str, mode: str = "news", max_results: int = 8) -> list[dict]:
    serp_api_key = _get_serp_api_key()
    if not serp_api_key:
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "api_key": serp_api_key,
        "num": max(1, max_results),
    }
    if mode == "news":
        params["tbm"] = "nws"

    try:
        res = requests.get(url, params=params, timeout=5).json()

        results = []
        raw_results = res.get("news_results", []) if mode == "news" else res.get("organic_results", [])
        if not raw_results and mode == "news":
            raw_results = res.get("organic_results", [])
        for result in raw_results:
            source_name = result.get("source")
            if isinstance(source_name, dict):
                source_name = source_name.get("name", "")
            snippet = result.get("snippet", "") or result.get("snippet_highlighted_words", "")
            if "2019" in str(snippet):
                continue
            results.append(
                {
                    "title": result.get("title"),
                    "source": source_name,
                    "url": result.get("link"),
                    "snippet": snippet,
                    "description": snippet,
                    "published_at": result.get("date", ""),
                }
            )

        return results
    except Exception:
        return []
