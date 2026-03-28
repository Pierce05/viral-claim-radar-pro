"""Similarity retrieval over the bundled fact-check dataset."""

from __future__ import annotations

import os
from functools import lru_cache

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    HAS_SKLEARN = True
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None
    HAS_SKLEARN = False

from modules.dataset_loader import load_claims_dataset
from modules.utils import keyword_overlap_score


def _can_use_sklearn() -> bool:
    if not HAS_SKLEARN:
        return False
    if os.environ.get("VCR_DISABLE_SKLEARN", "").lower() in {"1", "true", "yes"}:
        return False
    try:
        import pandas as pd  # type: ignore

        return hasattr(pd, "DataFrame")
    except Exception:
        return False


@lru_cache(maxsize=1)
def _build_index() -> tuple[TfidfVectorizer, object, tuple[str, ...]]:
    dataset = load_claims_dataset()
    corpus = tuple(item.get("claim", "") for item in dataset)
    if not _can_use_sklearn():
        return None, None, corpus
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform(corpus or ["placeholder"])
    return vectorizer, matrix, corpus


def retrieve_top_k(query: str, dataset: list[dict] | None = None, top_k: int = 3) -> list[dict]:
    records = dataset or load_claims_dataset()
    if not records:
        return []

    similarities: list[float]
    vectorizer, matrix, _ = _build_index()
    if _can_use_sklearn() and vectorizer is not None and matrix is not None:
        try:
            query_vector = vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, matrix).flatten().tolist()
        except Exception:
            similarities = [0.0 for _ in records]
    else:
        similarities = [0.0 for _ in records]

    ranked: list[dict] = []
    for item, score in zip(records, similarities):
        hybrid_score = max(score * 100, keyword_overlap_score(query, item.get("claim", "")))
        enriched = dict(item)
        enriched["similarity_score"] = round(hybrid_score, 1)
        ranked.append(enriched)

    ranked.sort(key=lambda row: row.get("similarity_score", 0), reverse=True)
    return ranked[: max(1, top_k)]


def find_contradicting_claims(text: str, dataset: list[dict] | None = None, top_k: int = 3) -> list[dict]:
    matches = retrieve_top_k(text, dataset=dataset, top_k=max(3, top_k))
    return [
        match
        for match in matches
        if match.get("label") == "Refuted" and float(match.get("similarity_score", 0) or 0) >= 35
    ]
