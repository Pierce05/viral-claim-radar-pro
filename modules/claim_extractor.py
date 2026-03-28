"""Claim extraction with a deterministic rule-based fallback."""

from __future__ import annotations

import re

from modules.utils import clean_sentence, dedupe_keep_order


def extract_claims(text: str, use_llm: bool = False, api_key: str | None = None) -> dict:
    del use_llm, api_key

    cleaned = clean_sentence(text)
    if not cleaned:
        return {"claims": [], "method": "empty"}

    parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", cleaned)
    claims: list[str] = []
    for part in parts:
        candidate = clean_sentence(part)
        if len(candidate) < 8:
            continue
        if candidate[-1] not in ".!?":
            candidate = f"{candidate}."
        claims.append(candidate)

    claims = dedupe_keep_order(claims)
    if not claims:
        claims = [cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."]

    return {"claims": claims[:6], "method": "rule-based"}
