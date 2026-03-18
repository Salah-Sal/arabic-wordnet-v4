#!/usr/bin/env python3
"""Generate BFS-ordered batch files for the AWN4 noun review pipeline.

Traverses the AWN4 noun hierarchy breadth-first (entity → leaves) and
outputs synset IDs one per line, compatible with both extract_synset_info.py
and batch_runner.py --batch.

Usage:
    python3 generate_bfs_batch.py --dry-run                      # Preview stats
    python3 generate_bfs_batch.py -o batches/noun_all.txt        # Full tree
    python3 generate_bfs_batch.py --max-depth 4 -o noun_L0-L4.txt
    python3 generate_bfs_batch.py --min-depth 5 --max-depth 5    # L5 only
    python3 generate_bfs_batch.py --require-evidence -o batch.txt

Requirements:
    pip install wn
    wn database must contain awn4.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

try:
    import wn
except ImportError:
    print("Error: wn package not installed. Run: pip install wn", file=sys.stderr)
    sys.exit(1)


# ── Default paths ──

EVIDENCE_DIR_DEFAULT = (
    Path(__file__).resolve().parent.parent.parent
    / "manual_linguist_review" / "linguist_workspace" / "output" / "evidence"
)


# ── WordNet loading (same pattern as extract_synset_info.py) ──

def load_awn4():
    """Load AWN4 Wordnet instance via the wn library."""
    ar_lexicons = [l for l in wn.lexicons() if l.language == "arb"]
    if not ar_lexicons:
        print("Error: AWN4 not loaded in wn database.", file=sys.stderr)
        sys.exit(1)
    return wn.Wordnet(ar_lexicons[0].specifier())


# ── BFS traversal ──

def bfs_noun_hierarchy(ar_wn, max_depth=None, min_depth=0):
    """BFS from noun root(s), yielding (synset_id, depth) in level order.

    Each synset appears exactly once, at its minimum BFS depth.
    The visited set handles DAG structure (multiple hypernym parents).
    """
    roots = [s for s in ar_wn.synsets(pos="n") if not s.hypernyms()]
    if not roots:
        print("Error: no noun root synsets found.", file=sys.stderr)
        sys.exit(1)

    visited = set()
    queue = deque()
    for root in roots:
        queue.append((root, 0))
        visited.add(root.id)

    effective_max = max_depth if max_depth is not None else float("inf")

    while queue:
        synset, depth = queue.popleft()

        if min_depth <= depth <= effective_max:
            yield synset.id, depth

        if depth >= effective_max:
            continue

        for child in synset.hyponyms():
            if child.id not in visited:
                visited.add(child.id)
                queue.append((child, depth + 1))


# ── Main ──

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--max-depth", type=int, default=None,
        help="Maximum BFS depth inclusive (default: all levels)",
    )
    parser.add_argument(
        "--min-depth", type=int, default=0,
        help="Minimum BFS depth inclusive (default: 0)",
    )
    parser.add_argument(
        "--require-evidence", action="store_true",
        help="Only include synsets with evidence files",
    )
    parser.add_argument(
        "--evidence-dir", type=Path, default=None,
        help="Path to evidence directory (auto-detected if not set)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output batch file path (default: stdout)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print statistics only, don't write batch file",
    )
    args = parser.parse_args()

    evidence_dir = args.evidence_dir or EVIDENCE_DIR_DEFAULT
    if args.require_evidence and not evidence_dir.is_dir():
        print(f"Error: evidence directory not found: {evidence_dir}", file=sys.stderr)
        sys.exit(1)

    # Load AWN4
    print("Loading AWN4...", file=sys.stderr)
    ar_wn = load_awn4()

    # Count total noun synsets for tree size
    total_nouns = len(ar_wn.synsets(pos="n"))
    print(f"Total AWN4 noun synsets: {total_nouns}", file=sys.stderr)

    # BFS traversal
    level_counts = defaultdict(int)
    synsets = []  # (synset_id, depth)
    skipped_no_evidence = 0

    for sid, depth in bfs_noun_hierarchy(ar_wn, args.max_depth, args.min_depth):
        level_counts[depth] += 1
        if args.require_evidence:
            evidence_path = evidence_dir / f"{sid}.evidence.yaml.gz"
            if not evidence_path.exists():
                skipped_no_evidence += 1
                continue
        synsets.append((sid, depth))

    # Print summary to stderr
    depth_lo = args.min_depth
    depth_hi = args.max_depth if args.max_depth is not None else max(level_counts) if level_counts else 0
    depth_label = f"L{depth_lo}" if depth_lo == depth_hi else f"L{depth_lo}-L{depth_hi}"

    print(f"\nBFS Noun Batch: {depth_label}", file=sys.stderr)
    print(f"  Depth range: {depth_lo}-{depth_hi}", file=sys.stderr)
    for d in sorted(level_counts):
        print(f"    L{d}: {level_counts[d]:>6}", file=sys.stderr)
    print(f"  BFS total:  {sum(level_counts.values())}", file=sys.stderr)
    if skipped_no_evidence:
        print(f"  No evidence: {skipped_no_evidence} (filtered out)", file=sys.stderr)
    print(f"  Output:     {len(synsets)} synsets", file=sys.stderr)
    print(f"  Tree size:  {total_nouns}", file=sys.stderr)

    if args.dry_run:
        print("\nDry run — no file written.", file=sys.stderr)
        return

    # Build header
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    level_summary = " ".join(f"L{d}:{level_counts[d]}" for d in sorted(level_counts))
    header_lines = [
        f"# BFS Noun Batch: {depth_label}",
        f"# Generated: {now}",
        f"# Depth: {depth_lo}-{depth_hi} | Total: {len(synsets)} | Tree: {total_nouns}",
        f"#",
        f"# {level_summary}",
        f"#",
    ]
    header = "\n".join(header_lines) + "\n"
    body = "\n".join(sid for sid, _ in synsets) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(header + body, encoding="utf-8")
        print(f"\nWrote {len(synsets)} synsets to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(header + body)


if __name__ == "__main__":
    main()
