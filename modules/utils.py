"""Utility helpers shared across the local-first claim intelligence app."""

from __future__ import annotations

import json
import os
import re
from typing import Any

LABEL_EMOJIS = {
    "Supported": "OK",
    "Refuted": "NO",
    "Uncertain": "??",
}

LABEL_COLORS = {
    "Supported": "#22c55e",
    "Refuted": "#ef4444",
    "Uncertain": "#f59e0b",
}

VALID_LABELS = {"Supported", "Refuted", "Uncertain"}


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def safe_load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return [] if default is None else default


def normalize_text(text: Any) -> str:
    value = "" if text is None else str(text)
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def clean_sentence(text: Any) -> str:
    value = "" if text is None else str(text)
    value = re.sub(r"\s+", " ", value).strip(" \n\t-")
    return value


def validate_claim_input(text: Any) -> tuple[bool, str]:
    cleaned = clean_sentence(text)
    if not cleaned:
        return False, "Input is empty. Try the sample claim or paste a statement to analyze."
    if len(cleaned) < 8:
        return False, "Input is too short to analyze reliably."
    return True, ""


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def ensure_label(label: Any) -> str:
    return label if label in VALID_LABELS else "Uncertain"


def confidence_to_label(confidence: Any) -> str:
    value = clamp(confidence)
    if value >= 75:
        return "High"
    if value >= 45:
        return "Medium"
    return "Low"


def format_confidence_bar(confidence: Any, width: int = 20) -> str:
    value = clamp(confidence)
    filled = round((value / 100) * width)
    return "[" + ("#" * filled).ljust(width, "-") + f"] {value:.0f}%"


def format_result_summary(result: dict[str, Any]) -> str:
    label = ensure_label(result.get("label"))
    confidence = clamp(result.get("confidence", 0))
    claim = clean_sentence(result.get("claim", ""))[:90]
    return f"{LABEL_EMOJIS[label]} {label} | {confidence:.0f}% | {claim}"


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def tokenize(text: Any) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", normalize_text(text))


def keyword_overlap_score(a: Any, b: Any) -> float:
    a_tokens = set(tokenize(a))
    b_tokens = set(tokenize(b))
    if not a_tokens or not b_tokens:
        return 0.0
    return round((len(a_tokens & b_tokens) / len(a_tokens | b_tokens)) * 100, 2)
