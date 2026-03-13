#!/usr/bin/env python3
"""Evaluate Mixedbread Store retrieval against evidence.json ground truth.

For each test synset, runs 3 query types against the Store and records which
ground-truth entries were found. Saves raw results for analysis.py.

Query types:
  A — Arabic lemma query (mirrors SQL Q1: headword lookup)
  B — English bridge query (mirrors SQL Q3: translation FTS)
  C — Definition keyword query (mirrors SQL Q4: Arabic FTS)

Usage:
    python evaluate_retrieval.py --num-synsets 30
    python evaluate_retrieval.py --num-synsets 10 --queries-per-synset 2
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import yaml
from pathlib import Path

from dotenv import load_dotenv
from mixedbread import Mixedbread

# Load .env
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
PREPARED_DIR = (Path(__file__).resolve().parent.parent
                / "linguistic_review_guide" / "claude_code_db" / "prepared")


def load_store_config() -> dict:
    config_path = Path(__file__).parent / "store_config.json"
    if not config_path.exists():
        print("Error: store_config.json not found. Run upload_store.py first.",
              file=sys.stderr)
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_manifest(export_dir: Path) -> tuple[dict, dict]:
    """Load manifest and reverse index (entry_id → headword_norm)."""
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    reverse = json.loads((export_dir / "entry_id_to_headword.json").read_text(encoding="utf-8"))
    return manifest, reverse


def load_synset_data(synset_dir: Path) -> dict | None:
    """Load evidence.json and synset_info.yaml for a synset."""
    evidence_path = synset_dir / "evidence.json"
    info_path = synset_dir / "synset_info.yaml"

    if not evidence_path.exists() or not info_path.exists():
        return None

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    info = yaml.safe_load(info_path.read_text(encoding="utf-8"))

    return {"evidence": evidence, "info": info, "synset_id": synset_dir.name}


def select_test_synsets(prepared_dir: Path, num: int,
                        offset: int = 0) -> list[dict]:
    """Select synsets that have evidence.json, stratified across levels."""
    candidates = []
    for synset_dir in sorted(prepared_dir.iterdir()):
        if not synset_dir.is_dir():
            continue
        data = load_synset_data(synset_dir)
        if data and data["evidence"].get("headword_entries"):
            candidates.append(data)

    random.seed(42)
    random.shuffle(candidates)
    return candidates[offset:offset + num]


def build_queries(synset_data: dict) -> list[dict]:
    """Build the 3 query types from synset data."""
    evidence = synset_data["evidence"]
    info = synset_data["info"]
    queries = []

    # Query A: Arabic lemma query
    lemma_terms = evidence.get("query_meta", {}).get("lemma_terms", [])
    if lemma_terms:
        # Use bare forms only (without ال) for a more natural query
        bare_terms = [t for t in lemma_terms if not t.startswith("ال")]
        if not bare_terms:
            bare_terms = lemma_terms
        queries.append({
            "type": "arabic_lemma",
            "query": " ".join(bare_terms),
            "ground_truth_entry_ids": [
                e["entry_id"] for e in evidence.get("headword_entries", [])
            ],
        })

    # Query B: English bridge query
    english_terms = evidence.get("query_meta", {}).get("english_terms", [])
    if english_terms:
        queries.append({
            "type": "english_bridge",
            "query": " ".join(english_terms),
            "ground_truth_entry_ids": [
                e["entry_id"] for e in evidence.get("english_bridge", [])
            ],
        })

    # Query C: Definition keyword query (use Arabic definition from synset_info)
    ar_def = info.get("definition_ar", "")
    if ar_def:
        queries.append({
            "type": "definition_keyword",
            "query": ar_def,
            "ground_truth_entry_ids": list(set(
                [e["entry_id"] for e in evidence.get("headword_entries", [])] +
                [e["entry_id"] for e in evidence.get("english_bridge", [])]
            )),
        })

    return queries


def run_evaluation(mxbai: Mixedbread, store_id: str, synsets: list[dict],
                   manifest: dict, reverse_index: dict,
                   top_k: int = 50, queries_per_synset: int = 3) -> list[dict]:
    """Run queries and record results."""
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
            # Filter ground truth to only entries we actually uploaded
            gt_ids = set(qinfo["ground_truth_entry_ids"]) & uploaded_entry_ids
            gt_headwords = {reverse_index.get(str(eid)) for eid in gt_ids} - {None}

            # Skip queries with no ground truth in uploaded data
            if not gt_ids:
                skipped_count += 1
                print(f"  [skip] {sid} | {qinfo['type']} | "
                      f"0 GT overlap — skipping", file=sys.stderr)
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
                response = mxbai.stores.search(
                    query=qinfo["query"],
                    store_identifiers=[store_id],
                    top_k=top_k,
                )

                # Extract returned chunks and map to headwords
                retrieved = []
                for i, chunk in enumerate(response.data):
                    # The file name encodes the entry group
                    filename = getattr(chunk, 'filename', None) or getattr(chunk, 'file_name', None)
                    score = getattr(chunk, 'score', None)
                    content_preview = ""
                    if hasattr(chunk, 'content'):
                        content_preview = str(chunk.content)[:200]
                    elif hasattr(chunk, 'text'):
                        content_preview = str(chunk.text)[:200]
                    retrieved.append({
                        "rank": i + 1,
                        "filename": str(filename) if filename else None,
                        "score": float(score) if score is not None else None,
                        "content_preview": content_preview,
                    })

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
            time.sleep(0.5)  # Be gentle with rate limits

    print(f"\n  API calls: {query_count} | Skipped (no GT): {skipped_count}",
          file=sys.stderr)
    return results


def main():
    random.seed(42)

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--num-synsets", type=int, default=30,
                        help="Number of test synsets (default: 30)")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip first N synsets (for continuing from previous run)")
    parser.add_argument("--queries-per-synset", type=int, default=3,
                        help="Max queries per synset (default: 3)")
    parser.add_argument("--top-k", type=int, default=50,
                        help="Number of results to retrieve per query (default: 50)")
    parser.add_argument("--export-dir", type=Path, default=Path("export"),
                        help="Path to export/ directory with manifest")
    parser.add_argument("--append", action="store_true",
                        help="Append to existing results file instead of overwriting")
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    api_key = os.getenv("MIXEDBREAD_API_KEY")
    if not api_key:
        print("Error: MIXEDBREAD_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    config = load_store_config()
    manifest, reverse_index = load_manifest(args.export_dir)

    mxbai = Mixedbread(api_key=api_key)

    # Select test synsets
    print(f"Selecting {args.num_synsets} test synsets (offset={args.offset})...",
          file=sys.stderr)
    synsets = select_test_synsets(PREPARED_DIR, args.num_synsets, offset=args.offset)
    print(f"Selected {len(synsets)} synsets with evidence", file=sys.stderr)

    total_queries = len(synsets) * args.queries_per_synset
    print(f"Running up to {total_queries} queries (budget: 100/month)", file=sys.stderr)

    # Run evaluation
    results = run_evaluation(
        mxbai, config["store_id"], synsets, manifest, reverse_index,
        top_k=args.top_k, queries_per_synset=args.queries_per_synset,
    )

    # Save results (append to existing if --append)
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    results_path = results_dir / "retrieval_results.json"

    if args.append and results_path.exists():
        existing = json.loads(results_path.read_text(encoding="utf-8"))
        results = existing + results
        print(f"Appended to existing results ({len(existing)} prior + "
              f"{len(results) - len(existing)} new)", file=sys.stderr)

    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Quick summary
    actual = sum(1 for r in results if not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    errors = sum(1 for r in results if r["error"])
    print(f"\nEvaluation complete:", file=sys.stderr)
    print(f"  API queries:  {actual}", file=sys.stderr)
    print(f"  Skipped (0 GT): {skipped}", file=sys.stderr)
    print(f"  Errors:       {errors}", file=sys.stderr)
    print(f"  Results at:   {results_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
