#!/usr/bin/env python3
"""Estimate the cost of processing all synsets in the evidence corpus.

Samples N synsets, runs the full 6-step pipeline on each, measures token
usage via DSPy's track_usage(), and extrapolates to the full corpus.

Usage:
    python -m dspy_review.estimate_cost --evidence-dir /path/to/evidence -n 10
    python -m dspy_review.estimate_cost --evidence-dir /path/to/evidence -n 5 --model gemini-3.1-flash-lite
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

from dspy_review.config import add_model_args
from dspy_review.shared import (
    ALGORITHM_PATH,
    OUTPUT_SCHEMA_PATH,
    extract_synset_id,
    list_evidence_files,
    load_synset_data,
    load_text,
)

# ═══════════════════════════════════════════════════════════════
# Pricing tables (per 1M tokens, USD, Paid Tier)
# ═══════════════════════════════════════════════════════════════

PRICING = {
    "gemini/gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
    "gemini/gemini-3-flash-preview":        {"input": 0.15, "output": 0.60},
    "gemini/gemini-3.1-pro-preview":        {"input": 1.25, "output": 10.00},
    "gemini/gemini-2.5-flash-preview-05-20": {"input": 0.15, "output": 0.60},
    "gemini/gemini-2.5-pro-preview-05-06":  {"input": 1.25, "output": 10.00},
    # OpenRouter (free stealth models)
    "openrouter/openrouter/hunter-alpha":   {"input": 0.00, "output": 0.00},
    "openrouter/openrouter/healer-alpha":   {"input": 0.00, "output": 0.00},
    # Cerebras (free tier)
    "cerebras/qwen-3-235b-a22b-instruct-2507": {"input": 0.00, "output": 0.00},
    "cerebras/gpt-oss-120b":                   {"input": 0.00, "output": 0.00},
    "cerebras/llama3.1-8b":                    {"input": 0.00, "output": 0.00},
}

# Fallback pricing if model not in table
DEFAULT_PRICING = {"input": 0.25, "output": 1.50}


def extract_token_totals(token_usage: dict) -> tuple[int, int]:
    """Sum prompt_tokens and completion_tokens across all models in usage dict."""
    total_input = 0
    total_output = 0
    for model_data in token_usage.values():
        if isinstance(model_data, dict):
            total_input += model_data.get("prompt_tokens", 0)
            total_output += model_data.get("completion_tokens", 0)
    return total_input, total_output


def format_tokens(n: int | float) -> str:
    """Format token count with commas."""
    return f"{n:,.0f}"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--evidence-dir", required=True,
        help="Directory with .evidence.yaml[.gz] files",
    )
    parser.add_argument(
        "--sample-size", "-n", type=int, default=10,
        help="Number of synsets to sample (default: 10)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Save detailed results JSON (default: output/cost_estimate)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )
    add_model_args(parser)
    args = parser.parse_args()

    # ── Discover evidence files ──
    evidence_dir = Path(args.evidence_dir)
    all_files = list_evidence_files(evidence_dir)
    total_corpus = len(all_files)

    if total_corpus == 0:
        print(f"No evidence files found in {evidence_dir}")
        sys.exit(1)

    n = min(args.sample_size, total_corpus)
    random.seed(args.seed)
    sample_files = random.sample(all_files, n)

    print(f"Corpus: {total_corpus:,} evidence files in {evidence_dir}")
    print(f"Sample: {n} synsets (seed={args.seed})")
    print()

    # ── Import pipeline (heavy import, do after arg parsing) ──
    from dspy_review.pipeline import StepDecomposedReviewer

    reviewer = StepDecomposedReviewer(
        model=args.model,
        sub_model=args.sub_model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    # ── Load spec files ──
    algorithm = load_text(ALGORITHM_PATH)
    output_schema = load_text(OUTPUT_SCHEMA_PATH)

    # Resolve pricing
    model_name = reviewer.lm.model
    pricing = PRICING.get(model_name, DEFAULT_PRICING)
    print(f"Model: {model_name}")
    print(f"Pricing: ${pricing['input']}/1M input, ${pricing['output']}/1M output")
    print()

    # ── Run pipeline on each sample ──
    per_synset_stats = []

    for i, filepath in enumerate(sample_files, 1):
        synset_id = extract_synset_id(filepath.name)
        print(f"{'=' * 60}")
        print(f"[{i}/{n}] {synset_id}")

        try:
            data = load_synset_data(filepath)
            ev_lines = data["evidence_yaml"].count("\n")
            print(f"  Evidence: {ev_lines} lines")

            t0 = time.time()
            results = reviewer.review(
                synset_info=data["synset_info"],
                evidence_yaml=data["evidence_yaml"],
                algorithm=algorithm,
                output_schema=output_schema,
            )
            wall_time = time.time() - t0

            token_usage = results.get("token_usage", {})
            input_tok, output_tok = extract_token_totals(token_usage)

            stat = {
                "synset_id": synset_id,
                "file": filepath.name,
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "total_tokens": input_tok + output_tok,
                "wall_time_s": round(wall_time, 1),
                "evidence_lines": ev_lines,
            }
            per_synset_stats.append(stat)

            print(f"  Tokens: {format_tokens(input_tok)} in / {format_tokens(output_tok)} out")
            print(f"  Time: {wall_time:.1f}s")

        except Exception as e:
            print(f"  ERROR: {e}")
            per_synset_stats.append({
                "synset_id": synset_id,
                "file": filepath.name,
                "error": str(e),
            })

        print()

    # ── Aggregate stats ──
    successful = [s for s in per_synset_stats if "error" not in s]
    if not successful:
        print("All samples failed. Cannot estimate cost.")
        sys.exit(1)

    inputs = [s["input_tokens"] for s in successful]
    outputs = [s["output_tokens"] for s in successful]
    totals = [s["total_tokens"] for s in successful]
    times = [s["wall_time_s"] for s in successful]

    avg_in = statistics.mean(inputs)
    avg_out = statistics.mean(outputs)
    avg_total = statistics.mean(totals)
    avg_time = statistics.mean(times)

    std_in = statistics.stdev(inputs) if len(inputs) > 1 else 0
    std_out = statistics.stdev(outputs) if len(outputs) > 1 else 0
    std_total = statistics.stdev(totals) if len(totals) > 1 else 0

    # ── Extrapolate to full corpus ──
    est_total_in = avg_in * total_corpus
    est_total_out = avg_out * total_corpus

    cost_in = est_total_in / 1_000_000 * pricing["input"]
    cost_out = est_total_out / 1_000_000 * pricing["output"]
    total_cost = cost_in + cost_out

    est_total_time_h = (avg_time * total_corpus) / 3600

    # ── Print summary ──
    print("=" * 60)
    print(f"COST ESTIMATE — {total_corpus:,} synsets")
    print(f"  Model: {model_name}")
    print(f"  Sample: {len(successful)}/{n} successful")
    print()
    print("  Per-synset averages:")
    print(f"    Input tokens:  {format_tokens(avg_in)} (± {format_tokens(std_in)})")
    print(f"    Output tokens: {format_tokens(avg_out)} (± {format_tokens(std_out)})")
    print(f"    Total tokens:  {format_tokens(avg_total)} (± {format_tokens(std_total)})")
    print(f"    Wall time:     {avg_time:.1f}s")
    print()
    print(f"    Min total: {format_tokens(min(totals))} | Max total: {format_tokens(max(totals))}")
    print()
    print("  Extrapolated totals:")
    print(f"    Input:  {est_total_in / 1e9:.2f}B tokens")
    print(f"    Output: {est_total_out / 1e9:.2f}B tokens")
    print(f"    Time:   {est_total_time_h:,.0f} hours ({est_total_time_h / 24:,.0f} days) sequential")
    print()
    print("  Estimated cost:")
    print(f"    Input:  ${cost_in:,.2f}")
    print(f"    Output: ${cost_out:,.2f}")
    print(f"    TOTAL:  ${total_cost:,.2f}")
    print("=" * 60)

    # ── Save detailed results ──
    output_dir = Path(args.output_dir) if args.output_dir else (
        Path(__file__).resolve().parent.parent / "output" / "cost_estimate"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "model": model_name,
        "pricing": pricing,
        "corpus_size": total_corpus,
        "sample_size": len(successful),
        "seed": args.seed,
        "per_synset_avg": {
            "input_tokens": round(avg_in),
            "output_tokens": round(avg_out),
            "total_tokens": round(avg_total),
            "wall_time_s": round(avg_time, 1),
        },
        "per_synset_std": {
            "input_tokens": round(std_in),
            "output_tokens": round(std_out),
            "total_tokens": round(std_total),
        },
        "extrapolated": {
            "total_input_tokens": round(est_total_in),
            "total_output_tokens": round(est_total_out),
            "input_cost_usd": round(cost_in, 2),
            "output_cost_usd": round(cost_out, 2),
            "total_cost_usd": round(total_cost, 2),
            "est_sequential_hours": round(est_total_time_h, 1),
        },
        "per_synset": per_synset_stats,
    }

    result_path = output_dir / "cost_estimate.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results saved to {result_path}")


if __name__ == "__main__":
    main()
