"""CLI and programmatic entrypoints for Viral Claim Radar PRO++."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.claim_extractor import extract_claims
from modules.classifier import classify_claim
from modules.consensus_engine import assess_batch, compute_source_consensus
from modules.dataset_loader import get_dataset_stats, load_claims_dataset
from modules.google_fetcher import fetch_google_sources, has_google_source_access
from modules.retriever import retrieve_top_k
from modules.source_fetcher import (
    classify_claim_type,
    compute_confidence as compute_source_confidence,
    filter_sources,
    get_source_score,
    detect_stance,
    relevance_score,
    fetch_wikipedia_summary,
)
from modules.update_fetcher import fetch_updates, get_available_regions, get_available_topics
from modules.utils import LABEL_EMOJIS, compute_source_trust, format_confidence_bar, generate_explanation, validate_claim_input


def _current_event_queries(claim: str) -> list[str]:
    cleaned = claim.strip()
    return [
        f'"{cleaned}" latest breaking news',
        f"{cleaned} latest breaking news Reuters AP BBC CNN",
        f"{cleaned} live updates Reuters AP BBC",
        f"{cleaned} war strike bombing update",
    ]


def run_fact_check(
    text: str,
    dataset: list[dict] | None = None,
    use_llm: bool = False,
    api_key: str | None = None,
    top_k: int = 3,
) -> dict:
    is_valid, error = validate_claim_input(text)
    if not is_valid:
        return {
            "error": error,
            "results": [],
            "extraction_method": "validation",
            "claim_count": 0,
            "original_input": text,
        }

    records = dataset or load_claims_dataset()
    extraction = extract_claims(text, use_llm=use_llm, api_key=api_key)
    claims = extraction.get("claims") or [text.strip()]

    results: list[dict] = []
    for claim in claims:
        top_matches = retrieve_top_k(claim, dataset=records, top_k=max(1, top_k))
        classification = classify_claim(claim, top_matches=top_matches, use_llm=use_llm, api_key=api_key)
        claim_type = classify_claim_type(claim)
        if claim_type == "current_event":
            query_candidates = _current_event_queries(claim)
            search_query = query_candidates[0]
            google_mode = "news"
        elif claim_type == "scientific_claim":
            query_candidates = [f"{claim} fact check study evidence research"]
            search_query = f"{claim} fact check study evidence research"
            google_mode = "news"
        else:
            query_candidates = [f"{claim} fact check evidence news"]
            search_query = f"{claim} fact check evidence news"
            google_mode = "news"

        raw_sources: list[dict] = []
        for candidate in query_candidates:
            search_query = candidate
            raw_sources = fetch_google_sources(search_query, mode=google_mode, max_results=10)
            if raw_sources:
                break
        sources = [source for source in raw_sources if source.get("url")]
        if claim_type == "current_event":
            sources = filter_sources(sources) or sources[:4]
        else:
            sources = filter_sources(sources)
        sources = sources[:5]
        for source in sources:
            combined_text = f"{source.get('title', '')} {source.get('snippet', '')}"
            source["description"] = source.get("snippet", "")
            source["stance"] = detect_stance(combined_text)
            source["relevance_score"] = relevance_score(
                {"title": source.get("title", ""), "description": source.get("snippet", "")},
                search_query,
            )
            source["credibility"] = source.get("credibility", get_source_score(source.get("url", "")))
        consensus = compute_source_consensus(sources)
        trust_score = compute_source_trust(sources)
        base_verdict = classification["label"].upper()
        if consensus["refute"] > consensus["support"]:
            adjusted_verdict = "REFUTED"
        elif consensus["support"] > consensus["refute"]:
            adjusted_verdict = "SUPPORTED"
        else:
            adjusted_verdict = base_verdict

        if claim_type == "current_event" and len(sources) >= 2 and adjusted_verdict == base_verdict:
            adjusted_verdict = "LIKELY TRUE"

        source_confidence = compute_source_confidence(trust_score, consensus["support"], consensus["refute"])
        match_bonus = min(len(top_matches) * 3, 9)
        enhanced_confidence = round(min(source_confidence + match_bonus, 95), 2)
        if claim_type == "current_event":
            enhanced_confidence = round(min(max(enhanced_confidence, 85) + (5 if len(sources) >= 2 else 0), 95), 2)

        result = {
            "claim": claim,
            "claim_type": claim_type,
            "search_query": search_query,
            "label": classification["label"],
            "verdict": base_verdict,
            "confidence": enhanced_confidence,
            "matched_claim": classification.get("matched_claim", ""),
            "source": classification.get("source", ""),
            "method": classification.get("method", "rule-based-similarity"),
            "top_matches": [match for match in top_matches if float(match.get("similarity_score", 0) or 0) >= 20],
            "sources": sources,
            "source_fetch_active": has_google_source_access(),
            "source_fetch_mode": google_mode,
            "consensus": consensus,
            "adjusted_verdict": adjusted_verdict,
            "trust_score": trust_score,
            "enhanced_confidence": round(enhanced_confidence / 100.0, 2),
        }
        if claim_type == "current_event" and not sources:
            result["top_matches"] = []
        if not sources:
            result["wiki"] = fetch_wikipedia_summary(claim)
        result["explanation"] = generate_explanation(result)
        results.append(result)

    return {
        "results": results,
        "extraction_method": extraction.get("method", "rule-based"),
        "claim_count": len(results),
        "original_input": text,
    }


def run_live_updates(
    region: str = "Global",
    topic: str = "All",
    dataset: list[dict] | None = None,
    news_api_key: str | None = None,
    max_items: int = 6,
) -> dict:
    records = dataset or load_claims_dataset()
    fetched = fetch_updates(region=region, topic=topic, news_api_key=news_api_key, max_items=max_items)
    updates = fetched.get("updates") or []
    if not updates:
        fallback = fetch_updates(region="Global", topic=topic, news_api_key=None, max_items=max_items)
        updates = fallback.get("updates") or []
        fetched["source"] = fallback.get("source", "simulated")
        fetched["region"] = fallback.get("region", "Global")
        fetched["topic"] = fallback.get("topic", "All")

    assessments = assess_batch(updates, dataset=records)
    return {
        "assessments": assessments,
        "source": fetched.get("source", "simulated"),
        "region": fetched.get("region", "Global"),
        "topic": fetched.get("topic", "All"),
        "count": len(assessments),
    }


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def print_fact_check_results(results: dict) -> None:
    print_separator("=")
    print("VIRAL CLAIM RADAR PRO++ | FACT CHECK")
    print_separator("=")
    if results.get("error"):
        print(f"Error: {results['error']}")
        return

    print(f"Input: {results.get('original_input', '')}")
    print(f"Claims detected: {results.get('claim_count', 0)} | Extraction: {results.get('extraction_method', 'rule-based')}")
    for index, item in enumerate(results.get("results", []), start=1):
        print_separator()
        print(f"Claim {index}: {item.get('claim', '')}")
        print(f"Verdict: {LABEL_EMOJIS.get(item.get('label'), '??')} {item.get('label', 'Uncertain')}")
        print(f"Confidence: {format_confidence_bar(item.get('confidence', 0))}")
        print(f"Explanation: {item.get('explanation', '')}")
        if item.get("top_matches"):
            print("Top matches:")
            for match in item["top_matches"]:
                print(f"  - {match.get('label')} | {match.get('similarity_score', 0):.0f}% | {match.get('claim', '')}")


def print_live_update_results(results: dict) -> None:
    print_separator("=")
    print(f"VIRAL CLAIM RADAR PRO++ | LIVE RADAR | {results.get('region', 'Global')}")
    print_separator("=")
    print(f"Feed source: {results.get('source', 'simulated')} | Items: {results.get('count', 0)}")
    for index, item in enumerate(results.get("assessments", []), start=1):
        print_separator()
        print(f"Update {index}: {item.get('headline', '')}")
        print(f"Claim: {item.get('claim', '')}")
        print(f"Verdict: {LABEL_EMOJIS.get(item.get('label'), '??')} {item.get('label', 'Uncertain')}")
        print(f"Confidence: {format_confidence_bar(item.get('confidence', 0))}")
        print(f"Reasoning: {item.get('reasoning', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Viral Claim Radar PRO++ local demo")
    subparsers = parser.add_subparsers(dest="command")

    fact = subparsers.add_parser("fact-check", help="Fact check one or more claims")
    fact.add_argument("claim", type=str)
    fact.add_argument("--top-k", type=int, default=3)
    fact.add_argument("--json", action="store_true")
    fact.add_argument("--no-llm", action="store_true")

    live = subparsers.add_parser("live-updates", help="Run live update radar")
    live.add_argument("--region", type=str, default="Global", choices=get_available_regions())
    live.add_argument("--topic", type=str, default="All", choices=get_available_topics())
    live.add_argument("--max", type=int, default=6)
    live.add_argument("--json", action="store_true")

    subparsers.add_parser("stats", help="Show dataset stats")
    subparsers.add_parser("demo", help="Run a small end-to-end demo")

    args = parser.parse_args()

    if args.command == "fact-check":
        output = run_fact_check(args.claim, use_llm=not args.no_llm, top_k=args.top_k)
        print(json.dumps(output, indent=2) if args.json else "")
        if not args.json:
            print_fact_check_results(output)
        return

    if args.command == "live-updates":
        output = run_live_updates(region=args.region, topic=args.topic, max_items=args.max)
        print(json.dumps(output, indent=2) if args.json else "")
        if not args.json:
            print_live_update_results(output)
        return

    if args.command == "stats":
        print(json.dumps(get_dataset_stats(load_claims_dataset()), indent=2))
        return

    if args.command == "demo":
        sample = "Vaccines cause autism. Climate change is driven by human activity."
        print_fact_check_results(run_fact_check(sample, use_llm=False))
        print_live_update_results(run_live_updates(region="Global", topic="All", max_items=4))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
