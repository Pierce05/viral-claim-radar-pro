"""CLI and programmatic entrypoints for Viral Claim Radar PRO++."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.claim_extractor import extract_claims
from modules.classifier import classify_claim
from modules.consensus_engine import assess_batch
from modules.dataset_loader import get_dataset_stats, load_claims_dataset
from modules.retriever import retrieve_top_k
from modules.update_fetcher import fetch_updates, get_available_regions
from modules.utils import LABEL_EMOJIS, format_confidence_bar, validate_claim_input


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
        results.append(
            {
                "claim": claim,
                "label": classification["label"],
                "confidence": classification["confidence"],
                "explanation": classification["explanation"],
                "matched_claim": classification.get("matched_claim", ""),
                "source": classification.get("source", ""),
                "method": classification.get("method", "rule-based-similarity"),
                "top_matches": top_matches,
            }
        )

    return {
        "results": results,
        "extraction_method": extraction.get("method", "rule-based"),
        "claim_count": len(results),
        "original_input": text,
    }


def run_live_updates(
    region: str = "Global",
    dataset: list[dict] | None = None,
    news_api_key: str | None = None,
    max_items: int = 6,
) -> dict:
    records = dataset or load_claims_dataset()
    fetched = fetch_updates(region=region, news_api_key=news_api_key, max_items=max_items)
    updates = fetched.get("updates") or []
    if not updates:
        fallback = fetch_updates(region="Global", news_api_key=None, max_items=max_items)
        updates = fallback.get("updates") or []
        fetched["source"] = fallback.get("source", "simulated")
        fetched["region"] = fallback.get("region", "Global")

    assessments = assess_batch(updates, dataset=records)
    return {
        "assessments": assessments,
        "source": fetched.get("source", "simulated"),
        "region": fetched.get("region", "Global"),
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
        output = run_live_updates(region=args.region, max_items=args.max)
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
        print_live_update_results(run_live_updates(region="Global", max_items=4))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
