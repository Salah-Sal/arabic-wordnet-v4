#!/usr/bin/env python3
"""Compute retrieval metrics from evaluation results.

Reads retrieval_results.json and computes Recall@K, MRR, Precision@K,
broken down by query type.

Usage:
    python analysis.py --backend mixedbread_store
    python analysis.py --results runs/mixedbread_store/retrieval_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def compute_metrics(results: list[dict], manifest: dict) -> dict:
    """Compute retrieval metrics per query type and overall."""

    # Build filename → headword_norm lookup
    filename_to_hw = {}
    for hw, info in manifest.items():
        filename_to_hw[info["filename"]] = hw

    # Build filename → entry_ids lookup
    filename_to_eids = {}
    for hw, info in manifest.items():
        filename_to_eids[info["filename"]] = set(info["entry_ids"])

    metrics_by_type = defaultdict(lambda: {
        "recall_at_10": [], "recall_at_25": [], "recall_at_50": [],
        "precision_at_10": [], "mrr": [], "count": 0,
        "gt_in_uploaded": [], "gt_total": [],
    })

    for result in results:
        if result["error"]:
            continue

        qtype = result["query_type"]
        gt_headwords = set(result.get("ground_truth_headwords", []))
        gt_count = len(gt_headwords)

        if gt_count == 0:
            continue

        # Extract retrieved headwords from filenames
        retrieved_hws = []
        for r in result["retrieved"]:
            fname = r.get("filename")
            if fname:
                # Extract just the filename from a potential path
                basename = Path(fname).name if fname else None
                hw = filename_to_hw.get(basename)
                if hw:
                    retrieved_hws.append(hw)

        # Compute recall at different K values
        for k, key in [(10, "recall_at_10"), (25, "recall_at_25"), (50, "recall_at_50")]:
            found = set(retrieved_hws[:k]) & gt_headwords
            recall = len(found) / gt_count if gt_count > 0 else 0
            metrics_by_type[qtype][key].append(recall)

        # Precision@10
        top10_hws = set(retrieved_hws[:10])
        relevant_in_top10 = len(top10_hws & gt_headwords)
        p10 = relevant_in_top10 / min(10, len(retrieved_hws)) if retrieved_hws else 0
        metrics_by_type[qtype]["precision_at_10"].append(p10)

        # MRR
        rr = 0
        for i, hw in enumerate(retrieved_hws):
            if hw in gt_headwords:
                rr = 1.0 / (i + 1)
                break
        metrics_by_type[qtype]["mrr"].append(rr)

        metrics_by_type[qtype]["count"] += 1
        metrics_by_type[qtype]["gt_in_uploaded"].append(gt_count)

    return dict(metrics_by_type)


def avg(lst: list[float]) -> float:
    return sum(lst) / len(lst) if lst else 0


def format_report(metrics: dict, results: list[dict],
                  backend_name: str = "Retrieval") -> str:
    """Generate a markdown report."""
    lines = [
        f"# {backend_name} Retrieval Evaluation Report",
        "",
        "## Overview",
        "",
        f"- **Total queries evaluated:** {sum(1 for r in results if not r.get('skipped'))}",
        f"- **Skipped (0 GT overlap):** {sum(1 for r in results if r.get('skipped'))}",
        f"- **Errors:** {sum(1 for r in results if r['error'])}",
        f"- **Query types:** {', '.join(metrics.keys())}",
        "",
        "## Metrics by Query Type",
        "",
        "| Query Type | N | Recall@10 | Recall@25 | Recall@50 | P@10 | MRR | Avg GT |",
        "|------------|---|-----------|-----------|-----------|------|-----|--------|",
    ]

    overall = {"recall_at_10": [], "recall_at_25": [], "recall_at_50": [],
               "precision_at_10": [], "mrr": []}

    for qtype in ["arabic_lemma", "english_bridge", "definition_keyword"]:
        m = metrics.get(qtype, {})
        if not m or m.get("count", 0) == 0:
            continue

        r10 = avg(m["recall_at_10"])
        r25 = avg(m["recall_at_25"])
        r50 = avg(m["recall_at_50"])
        p10 = avg(m["precision_at_10"])
        mrr = avg(m["mrr"])
        gt_avg = avg(m["gt_in_uploaded"])

        lines.append(
            f"| {qtype} | {m['count']} | {r10:.1%} | {r25:.1%} | {r50:.1%} | "
            f"{p10:.1%} | {mrr:.3f} | {gt_avg:.1f} |"
        )

        for k in overall:
            overall[k].extend(m.get(k, []))

    # Overall row
    if overall["recall_at_10"]:
        lines.append(
            f"| **Overall** | {len(overall['recall_at_10'])} | "
            f"{avg(overall['recall_at_10']):.1%} | {avg(overall['recall_at_25']):.1%} | "
            f"{avg(overall['recall_at_50']):.1%} | {avg(overall['precision_at_10']):.1%} | "
            f"{avg(overall['mrr']):.3f} | — |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- **Recall@K** = fraction of ground-truth entries found in top-K results.",
        "  SQL baseline has 100% recall (evidence.json was generated from SQL).",
        "- **Precision@10** = fraction of top-10 results that are relevant.",
        "- **MRR** = mean reciprocal rank of first relevant result (1.0 = always first).",
        "- **Avg GT** = average number of ground truth entries per query "
        "(filtered to entries we uploaded).",
        "",
        "## Per-Synset Results",
        "",
    ])

    # Per-synset detail
    by_synset = defaultdict(list)
    for r in results:
        if not r["error"]:
            by_synset[r["synset_id"]].append(r)

    for sid in sorted(by_synset):
        lines.append(f"### {sid}")
        for r in by_synset[sid]:
            gt_n = len(r.get("ground_truth_headwords", []))
            retr_n = r["retrieved_count"]
            lines.append(
                f"- **{r['query_type']}**: q=\"{r['query_text'][:50]}...\" | "
                f"GT={gt_n} | Retrieved={retr_n}"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", type=str, default=None,
                        help="Backend name (sets default --results and output paths)")
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--manifest", type=Path,
                        default=Path("export/manifest.json"))
    args = parser.parse_args()

    # Resolve results path from --backend or --results
    if args.results is None:
        if args.backend:
            args.results = Path("runs") / args.backend / "retrieval_results.json"
        else:
            args.results = Path("runs/mixedbread_store/retrieval_results.json")

    if not args.results.exists():
        print(f"Error: {args.results} not found. Run run_eval.py first.",
              file=sys.stderr)
        sys.exit(1)

    results = json.loads(args.results.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    backend_label = args.backend.replace("_", " ").title() if args.backend else "Retrieval"
    metrics = compute_metrics(results, manifest)
    report = format_report(metrics, results, backend_name=backend_label)

    # Write report alongside results
    if args.backend:
        report_path = Path("runs") / args.backend / "report.md"
    else:
        report_path = args.results.parent / "report.md"
    report_path.write_text(report, encoding="utf-8")

    # Print summary to stderr
    print(report[:2000], file=sys.stderr)
    print(f"\nFull report: {report_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
