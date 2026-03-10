#!/usr/bin/env python3
"""
slim_evidence.py — Strip provably dead weight from evidence YAML files.

Gentle approach: only removes what is guaranteed redundant or empty.
Preserves all semantic content, enriched child tables, and entry fields.

What gets removed:
  1. step7_chronological  (100% duplicate of step1, verified across 40+ files)
  2. Debug metadata       (sql_template, query_params, excluded_entry_ids,
                           al_variants_searched — internal plumbing)
  3. _meta section        (identical across all 120K files)
  4. Empty/null values    (cross_refs: [], provenance: null, etc. — omitted,
                           populated values are preserved)

What is KEPT (was previously stripped):
  - step9_specialized (80% of files have results)
  - All enriched child tables when populated (definitions, examples, plurals, etc.)
  - All entry fields when populated (headword, root, pos, form, etc.)
  - All synset subfields (ili, examples_ar, oewn.*, hypernym chain defs, etc.)
  - step3 sub-structures (from_entry_id, roots_from_components, etc.)

Usage:
    python3 slim_evidence.py INPUT_DIR                     # -> INPUT_DIR_slim/
    python3 slim_evidence.py INPUT_DIR OUTPUT_DIR
    python3 slim_evidence.py INPUT_DIR --in-place
    python3 slim_evidence.py INPUT_DIR --dry-run --sample 100
"""
from __future__ import annotations

import argparse
import gzip
import os
import random
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader

try:
    _Dumper = yaml.CSafeDumper
except AttributeError:
    _Dumper = yaml.SafeDumper

# ═══════════════════════════════════════════════════════════════════════════════
# Debug keys to remove from step containers
# ═══════════════════════════════════════════════════════════════════════════════

STEP_DEBUG_KEYS = frozenset({
    "sql_template", "query_params", "excluded_entry_ids", "al_variants_searched",
})

# Values considered "empty" — safe to omit from entry dicts
_EMPTY_VALUES = (None, [], {}, "")


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_debug(step_dict: dict) -> None:
    """Remove debug/plumbing keys from a step container (mutating)."""
    for k in STEP_DEBUG_KEYS:
        step_dict.pop(k, None)


def _strip_empty(entry: dict) -> dict:
    """Remove keys with empty/null values from an entry dict.

    Preserves all keys that carry actual data — only omits [], None, {}, "".
    """
    return {k: v for k, v in entry.items() if v not in _EMPTY_VALUES}


def _strip_entries_in(container: dict, key: str = "entries") -> None:
    """Strip empty/null values from each entry in a list within a container."""
    items = container.get(key)
    if items and isinstance(items, list):
        container[key] = [_strip_empty(e) for e in items]


# ═══════════════════════════════════════════════════════════════════════════════
# Core slimming logic
# ═══════════════════════════════════════════════════════════════════════════════

def slim_artifact(art: dict) -> dict:
    """Gentle slim: drop step7, debug metadata, _meta, and empty/null values.

    Preserves all semantic content — enriched child tables, entry fields,
    step9, synset metadata, hypernym chain definitions, etc.
    """
    out = {}

    # ── 1. Replace _meta with slim marker ─────────────────────────────────
    out["_meta"] = {"slimmed": True}

    # ── 2. Keep synset as-is (all subfields preserved) ────────────────────
    out["synset"] = art.get("synset", {})

    # ── 3. Process per_lemma ──────────────────────────────────────────────
    per_lemma_out = {}
    for lemma_key, ld in art.get("per_lemma", {}).items():
        slim_ld = dict(ld)

        # Drop step7 (proven 100% duplicate of step1)
        slim_ld.pop("step7_chronological", None)

        # Strip debug from step1
        s1 = slim_ld.get("step1_headword")
        if s1:
            _strip_debug(s1)
            _strip_entries_in(s1)
            # by_component sub-entries
            by_comp = s1.get("by_component")
            if by_comp and isinstance(by_comp, dict):
                for comp_data in by_comp.values():
                    _strip_debug(comp_data)
                    _strip_entries_in(comp_data)
                    # proclitic_stripped sub-entries
                    ps = comp_data.get("proclitic_stripped")
                    if ps and isinstance(ps, dict):
                        _strip_debug(ps)
                        _strip_entries_in(ps)

        # Strip debug from step2
        s2 = slim_ld.get("step2_definitions")
        if s2:
            _strip_debug(s2)
            # step2 has entries_with_senses, not entries
            ews = s2.get("entries_with_senses")
            if ews and isinstance(ews, list):
                s2["entries_with_senses"] = [_strip_empty(e) for e in ews]

        # Strip debug from step3
        s3 = slim_ld.get("step3_root_family")
        if s3:
            for root_data in s3.get("by_root", {}).values():
                _strip_debug(root_data)
                _strip_entries_in(root_data)

        # Strip debug from step6
        s6 = slim_ld.get("step6_examples")
        if s6:
            _strip_debug(s6)
            # step6 has "examples" not "entries", and they're a different shape
            exs = s6.get("examples")
            if exs and isinstance(exs, list):
                s6["examples"] = [_strip_empty(e) for e in exs]

        # Strip debug from step8
        s8 = slim_ld.get("step8_reverse_lookup")
        if s8:
            _strip_debug(s8)
            _strip_entries_in(s8)

        per_lemma_out[lemma_key] = slim_ld
    out["per_lemma"] = per_lemma_out

    # ── 4. Process per_synset ─────────────────────────────────────────────
    ps_in = art.get("per_synset", {})
    ps_out = dict(ps_in)

    # step4
    s4 = ps_out.get("step4_fts_keyword")
    if s4:
        _strip_debug(s4)
        _strip_entries_in(s4)

    # step5
    s5 = ps_out.get("step5_english_bridge")
    if s5:
        _strip_debug(s5)
        _strip_entries_in(s5)

    # step9 — keep the step, just strip debug from each filter
    s9 = ps_out.get("step9_specialized")
    if s9:
        for filt in s9.get("filters_applied", []):
            _strip_debug(filt)
            _strip_entries_in(filt)

    out["per_synset"] = ps_out

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# I/O helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _read_gz(path: Path) -> dict:
    """Read a gzipped YAML file and return the parsed dict."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


def _write_gz(data: dict, path: Path) -> int:
    """Write data as gzipped YAML, return compressed size in bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp.gz")
    os.close(fd)
    try:
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
            yaml.dump(
                data, f, Dumper=_Dumper,
                allow_unicode=True, default_flow_style=False,
                sort_keys=False, width=120,
            )
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path.stat().st_size


# ═══════════════════════════════════════════════════════════════════════════════
# Worker function (runs in subprocess)
# ═══════════════════════════════════════════════════════════════════════════════

def _process_file(args: tuple) -> tuple[str, int, int, bool]:
    """Process one evidence file. Returns: (filename, orig_bytes, new_bytes, skipped)."""
    src_path, dst_path, dry_run = args
    src_path = Path(src_path)
    dst_path = Path(dst_path) if dst_path else None
    fname = src_path.name
    orig_size = src_path.stat().st_size

    try:
        art = _read_gz(src_path)
    except Exception as e:
        print(f"  WARN: {fname}: failed to read: {e}", file=sys.stderr)
        return (fname, orig_size, orig_size, True)

    # Skip already-slimmed files
    meta = art.get("_meta", {})
    if isinstance(meta, dict) and meta.get("slimmed"):
        return (fname, orig_size, orig_size, True)

    slimmed = slim_artifact(art)

    if dry_run:
        buf = yaml.dump(
            slimmed, Dumper=_Dumper,
            allow_unicode=True, default_flow_style=False,
            sort_keys=False, width=120,
        ).encode("utf-8")
        import gzip as gz
        compressed = gz.compress(buf, compresslevel=6)
        return (fname, orig_size, len(compressed), False)

    new_size = _write_gz(slimmed, dst_path or src_path)
    return (fname, orig_size, new_size, False)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    parser = argparse.ArgumentParser(
        description="Strip dead weight from evidence YAML files (gentle mode).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_dir", help="Directory containing .evidence.yaml.gz files")
    parser.add_argument("output_dir", nargs="?", default=None,
                        help="Output directory (default: INPUT_DIR_slim/)")
    parser.add_argument("--in-place", action="store_true",
                        help="Overwrite original files (no output dir)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report savings without writing")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel workers (default: 8)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process only first N files")
    parser.add_argument("--sample", type=int, default=0,
                        help="Process N random files")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.in_place:
        output_dir = None
    elif args.output_dir:
        output_dir = Path(args.output_dir)
    elif args.dry_run:
        output_dir = None
    else:
        output_dir = input_dir.parent / (input_dir.name + "_slim")

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in input_dir.iterdir()
                   if f.name.endswith(".evidence.yaml.gz"))
    total = len(files)
    print(f"Found {total} evidence files in {input_dir}", file=sys.stderr)

    if args.sample and args.sample < total:
        files = random.sample(files, args.sample)
        print(f"Sampled {args.sample} files", file=sys.stderr)
    elif args.limit and args.limit < len(files):
        files = files[:args.limit]
        print(f"Limited to {args.limit} files", file=sys.stderr)

    work = []
    for f in files:
        if output_dir:
            dst = output_dir / f.name
        else:
            dst = None
        work.append((str(f), str(dst) if dst else None, args.dry_run))

    n = len(work)
    done = 0
    skipped = 0
    total_orig = 0
    total_new = 0

    mode_label = "dry-run" if args.dry_run else ("in-place" if args.in_place else f"-> {output_dir}")
    print(f"Processing {n} files ({mode_label}) with {args.workers} workers...",
          file=sys.stderr)

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_process_file, w): w for w in work}
        for fut in as_completed(futures):
            fname, orig, new, skip = fut.result()
            done += 1
            total_orig += orig
            total_new += new
            if skip:
                skipped += 1
            if done % 2000 == 0 or done == n:
                pct = (1 - total_new / total_orig) * 100 if total_orig else 0
                print(
                    f"  [{done}/{n}] {_fmt_bytes(total_orig)} -> {_fmt_bytes(total_new)} "
                    f"({pct:.1f}% reduction, {skipped} skipped)",
                    file=sys.stderr,
                )

    print(file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    pct = (1 - total_new / total_orig) * 100 if total_orig else 0
    print(f"Files processed: {done}  (skipped: {skipped})", file=sys.stderr)
    print(f"Original:  {_fmt_bytes(total_orig)}", file=sys.stderr)
    print(f"Slimmed:   {_fmt_bytes(total_new)}", file=sys.stderr)
    print(f"Reduction: {_fmt_bytes(total_orig - total_new)} ({pct:.1f}%)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
