#!/usr/bin/env python3
"""Generic retrieval evaluation runner.

Selects test synsets, builds queries, calls a pluggable backend's search(),
and records raw results for analysis.py.

Usage:
    python run_eval.py --backend mixedbread_store --num-synsets 30
    python run_eval.py --backend mixedbread_store --setup --num-synsets 38
    python run_eval.py --backend faiss_bge_m3 --setup --num-synsets 30
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

from queries import (
    PREPARED_DIR,
    build_queries,
    load_manifest,
    select_test_synsets,
)


def run_evaluation(backend, config: dict, synsets: list[dict],
                   manifest: dict, reverse_index: dict,
                   top_k: int = 50, queries_per_synset: int = 3,
                   sleep: float = 0.5) -> list[dict]:
    """Run queries via backend.search() and record results."""
    # Build set of uploaded entry_ids for filtering ground truth
    uploaded_entry_ids = set()
    for hw, info in manifest.items():
        for eid in info["entry_ids"]:
            uploaded_entry_ids.add(eid)

    results = []
    query_count = 0
    skipped_count = 0

    for synset_data in synsets:
        sid = synset_data["synset_id"]
        queries = build_queries(synset_data)[:queries_per_synset]

        for qinfo in queries:
            gt_ids = set(qinfo["ground_truth_entry_ids"]) & uploaded_entry_ids
            gt_headwords = {reverse_index.get(str(eid)) for eid in gt_ids} - {None}

            if not gt_ids:
                skipped_count += 1
                print(f"  [skip] {sid} | {qinfo['type']} | "
                      f"0 GT overlap -- skipping", file=sys.stderr)
                results.append({
                    "synset_id": sid,
                    "query_type": qinfo["type"],
                    "query_text": qinfo["query"],
                    "ground_truth_entry_ids": [],
                    "ground_truth_headwords": [],
                    "ground_truth_count": 0,
                    "uploaded_gt_count": 0,
                    "retrieved": [],
                    "retrieved_count": 0,
                    "error": None,
                    "skipped": True,
                })
                continue

            query_count += 1
            print(f"  [{query_count}] {sid} | {qinfo['type']} | "
                  f"GT={len(gt_ids)} | q=\"{qinfo['query'][:50]}...\"",
                  file=sys.stderr)

            try:
                retrieved = backend.search(qinfo["query"], top_k, config)
                result = {
                    "synset_id": sid,
                    "query_type": qinfo["type"],
                    "query_text": qinfo["query"],
                    "ground_truth_entry_ids": list(gt_ids),
                    "ground_truth_headwords": list(gt_headwords),
                    "ground_truth_count": len(gt_ids),
                    "uploaded_gt_count": len(gt_ids),
                    "retrieved": retrieved,
                    "retrieved_count": len(retrieved),
                    "error": None,
                    "skipped": False,
                }
            except Exception as e:
                result = {
                    "synset_id": sid,
                    "query_type": qinfo["type"],
                    "query_text": qinfo["query"],
                    "ground_truth_entry_ids": list(gt_ids),
                    "ground_truth_headwords": list(gt_headwords),
                    "ground_truth_count": len(gt_ids),
                    "uploaded_gt_count": len(gt_ids),
                    "retrieved": [],
                    "retrieved_count": 0,
                    "error": str(e),
                    "skipped": False,
                }

            results.append(result)
            if sleep > 0:
                time.sleep(sleep)

    print(f"\n  API calls: {query_count} | Skipped (no GT): {skipped_count}",
          file=sys.stderr)
    return results


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--backend", required=True,
                        help="Backend module name (e.g. mixedbread_store)")
    parser.add_argument("--setup", action="store_true",
                        help="Run backend.setup() before evaluation")
    parser.add_argument("--num-synsets", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--queries-per-synset", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--export-dir", type=Path, default=Path("export"))
    parser.add_argument("--append", action="store_true",
                        help="Append to existing results instead of overwriting")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Seconds between API calls (default: 0.5)")
    args = parser.parse_args()

    # Dynamic backend import
    backend = importlib.import_module(f"backends.{args.backend}")

    # Output directory
    run_dir = Path("runs") / args.backend
    run_dir.mkdir(parents=True, exist_ok=True)

    # Optional setup (ingestion / indexing)
    config_path = run_dir / "config.json"
    if args.setup:
        print(f"Running {args.backend}.setup()...", file=sys.stderr)
        config = backend.setup(args.export_dir)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"Config saved: {config_path}", file=sys.stderr)
    else:
        if not config_path.exists():
            print(f"Error: {config_path} not found. Run with --setup first.",
                  file=sys.stderr)
            sys.exit(1)
        config = json.loads(config_path.read_text(encoding="utf-8"))

    manifest, reverse_index = load_manifest(args.export_dir)

    print(f"Selecting {args.num_synsets} test synsets (offset={args.offset})...",
          file=sys.stderr)
    synsets = select_test_synsets(PREPARED_DIR, args.num_synsets, offset=args.offset)
    print(f"Selected {len(synsets)} synsets with evidence", file=sys.stderr)

    results = run_evaluation(
        backend, config, synsets, manifest, reverse_index,
        top_k=args.top_k, queries_per_synset=args.queries_per_synset,
        sleep=args.sleep,
    )

    # Save results
    results_path = run_dir / "retrieval_results.json"
    if args.append and results_path.exists():
        existing = json.loads(results_path.read_text(encoding="utf-8"))
        results = existing + results
        print(f"Appended ({len(existing)} prior + {len(results) - len(existing)} new)",
              file=sys.stderr)

    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    actual = sum(1 for r in results if not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    errors = sum(1 for r in results if r["error"])
    print(f"\nEvaluation complete:", file=sys.stderr)
    print(f"  Queries:      {actual}", file=sys.stderr)
    print(f"  Skipped:      {skipped}", file=sys.stderr)
    print(f"  Errors:       {errors}", file=sys.stderr)
    print(f"  Results at:   {results_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
