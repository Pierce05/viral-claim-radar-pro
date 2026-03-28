"""Local-first claim classification."""

from __future__ import annotations

from collections import Counter

from modules.utils import clamp, ensure_label, keyword_overlap_score, normalize_text

HIGH_RISK_PATTERNS = [
    ("miracle", "Extraordinary cure language reduces credibility."),
    ("100%", "Absolute certainty language is a misinformation signal."),
    ("secret", "Secret-knowledge framing reduces credibility."),
    ("they don't want you to know", "Conspiracy framing reduces credibility."),
]


def _pattern_adjustment(claim: str) -> tuple[int, list[str]]:
    text = normalize_text(claim)
    delta = 0
    reasons: list[str] = []
    for token, reason in HIGH_RISK_PATTERNS:
        if token in text:
            delta -= 12
            reasons.append(reason)
    return delta, reasons


def classify_claim(
    claim: str,
    top_matches: list[dict] | None = None,
    use_llm: bool = False,
    api_key: str | None = None,
) -> dict:
    del use_llm, api_key

    matches = top_matches or []
    if not matches:
        return {
            "label": "Uncertain",
            "confidence": 28.0,
            "explanation": "No strong knowledge-base match was found, so the system returned a safe uncertain verdict.",
            "matched_claim": "",
            "source": "Fallback classifier",
            "method": "rule-based-fallback",
        }

    best = matches[0]
    best_label = ensure_label(best.get("label"))
    best_score = clamp(best.get("similarity_score", 0))
    label_counter = Counter(ensure_label(match.get("label")) for match in matches)
    overlap = keyword_overlap_score(claim, best.get("claim", ""))
    adjustment, pattern_notes = _pattern_adjustment(claim)
    second_score = clamp(matches[1].get("similarity_score", 0)) if len(matches) > 1 else 0
    best_margin = best_score - second_score

    if best_score >= 72 or overlap >= 58 or (best_score >= 40 and best_margin >= 20):
        confidence = clamp(best_score * 0.82 + 18 + adjustment, 5, 98)
        label = best_label
        explanation = (
            f"Closest match aligns with a known {best_label.lower()} claim in the local dataset. "
            f"The best evidence match is '{best.get('claim', '')}'."
        )
    elif len(label_counter) >= 2 and label_counter.most_common(1)[0][1] == 1:
        confidence = clamp(42 + adjustment, 5, 95)
        label = "Uncertain"
        explanation = "Top evidence matches disagree with each other, so the claim is marked uncertain."
    else:
        dominant_label, count = label_counter.most_common(1)[0]
        confidence = clamp((best_score * 0.55) + (count / max(1, len(matches)) * 35) + 10 + adjustment, 5, 95)
        label = dominant_label if confidence >= 45 else "Uncertain"
        explanation = (
            f"Verdict is based on similarity clustering across the top {len(matches)} local evidence matches."
        )

    if pattern_notes:
        explanation = f"{explanation} {' '.join(pattern_notes)}"

    return {
        "label": ensure_label(label),
        "confidence": round(confidence, 1),
        "explanation": explanation,
        "matched_claim": best.get("claim", ""),
        "source": best.get("source", "Local knowledge base"),
        "method": "rule-based-similarity",
    }
