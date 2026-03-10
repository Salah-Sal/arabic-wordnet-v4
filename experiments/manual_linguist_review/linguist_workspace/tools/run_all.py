#!/usr/bin/env python3
"""
run_all.py — Run the automated evidence collection pipeline on all AWN4 synsets.

Features:
    - Multiprocessing pool (each worker gets its own DictDB + WNBridge)
    - Atomic writes (temp file → os.replace) — no more 0-byte corrupted files
    - Optional gzip compression (5:1 ratio, ~28 GB vs ~141 GB for full run)
    - Retry with backoff on per-synset failures
    - Improved --resume: detects .yaml and .yaml.gz, skips 0-byte files, cleans .tmp

Usage:
    python3 tools/run_all.py                          # full run, compressed, auto workers
    python3 tools/run_all.py --resume                 # resume interrupted run
    python3 tools/run_all.py --workers 4 --pos n      # 4 workers, nouns only
    python3 tools/run_all.py --limit 100 --no-compress # first 100, plain YAML
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collect_evidence import (
    DictDB,
    WNBridge,
    _ArabicDumper,
    collect_evidence,
)

import wn


# ═══════════════════════════════════════════════════════════════════════════════
# Worker state (module-level globals, set per-process by _worker_init)
# ═══════════════════════════════════════════════════════════════════════════════

_worker_db: DictDB | None = None
_worker_wn: WNBridge | None = None
_worker_output_dir: Path | None = None
_worker_compress: bool = True
_worker_max_retries: int = 3


def _worker_init(db_path: str, output_dir: str, compress: bool, max_retries: int) -> None:
    """Pool initializer: create per-process DictDB + WNBridge."""
    global _worker_db, _worker_wn, _worker_output_dir, _worker_compress, _worker_max_retries
    _worker_db = DictDB(db_path)
    _worker_wn = WNBridge()
    _worker_output_dir = Path(output_dir)
    _worker_compress = compress
    _worker_max_retries = max_retries


def _worker_process(synset_id: str) -> tuple[str, bool, str | None, int]:
    """Process a single synset: collect evidence, write artifact, return status.

    Returns (synset_id, success, error_msg_or_None, attempts).
    """
    last_error = None
    for attempt in range(1, _worker_max_retries + 1):
        try:
            artifact = collect_evidence(synset_id, _worker_db, _worker_wn)
            ext = ".evidence.yaml.gz" if _worker_compress else ".evidence.yaml"
            final_path = _worker_output_dir / f"{synset_id}{ext}"
            _write_artifact_atomic(artifact, final_path, _worker_compress)
            return (synset_id, True, None, attempt)
        except Exception:
            last_error = traceback.format_exc()
            if attempt < _worker_max_retries:
                time.sleep(0.5 * attempt)  # brief backoff
    return (synset_id, False, last_error, _worker_max_retries)


# ═══════════════════════════════════════════════════════════════════════════════
# Atomic write with optional gzip compression
# ═══════════════════════════════════════════════════════════════════════════════

def _write_artifact_atomic(artifact: dict, final_path: Path, compress: bool) -> None:
    """Write evidence artifact atomically: yaml.dump → temp file → os.replace."""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    try:
        if compress:
            with gzip.open(tmp_path, "wt", encoding="utf-8", compresslevel=6) as f:
                yaml.dump(artifact, f, Dumper=_ArabicDumper, allow_unicode=True,
                          default_flow_style=False, sort_keys=False, width=120)
        else:
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.dump(artifact, f, Dumper=_ArabicDumper, allow_unicode=True,
                          default_flow_style=False, sort_keys=False, width=120)
        os.replace(tmp_path, final_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Resumption helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _filter_resumed(synset_ids: list[str], output_dir: Path) -> list[str]:
    """Filter out already-completed synsets, skipping corrupted 0-byte files."""
    existing: set[str] = set()
    corrupted: list[str] = []

    for p in output_dir.glob("*.evidence.yaml"):
        sid = p.stem.replace(".evidence", "")
        if p.stat().st_size > 0:
            existing.add(sid)
        else:
            corrupted.append(str(p))

    for p in output_dir.glob("*.evidence.yaml.gz"):
        sid = p.name.replace(".evidence.yaml.gz", "")
        if p.stat().st_size > 0:
            existing.add(sid)
        else:
            corrupted.append(str(p))

    # Clean leftover .tmp files from prior crashes
    tmp_count = 0
    for tmp in output_dir.glob("*.tmp"):
        tmp.unlink()
        tmp_count += 1

    if corrupted:
        print(f"  Found {len(corrupted)} corrupted (0-byte) files, will re-process:", file=sys.stderr)
        for p in corrupted[:5]:
            print(f"    {p}", file=sys.stderr)
        if len(corrupted) > 5:
            print(f"    ... and {len(corrupted) - 5} more", file=sys.stderr)

    if tmp_count:
        print(f"  Cleaned {tmp_count} leftover .tmp files", file=sys.stderr)

    before = len(synset_ids)
    synset_ids = [sid for sid in synset_ids if sid not in existing]
    print(f"Resuming: {before - len(synset_ids)} already done, {len(synset_ids)} remaining",
          file=sys.stderr)
    return synset_ids


# ═══════════════════════════════════════════════════════════════════════════════
# Progress and error reporting
# ═══════════════════════════════════════════════════════════════════════════════

def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}m"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h{m:02d}m"


def _report_progress(processed: int, total: int, success: int, errors: int,
                     t_start: float) -> None:
    elapsed = time.time() - t_start
    rate = processed / elapsed if elapsed > 0 else 0
    eta = (total - processed) / rate if rate > 0 else 0
    pct = 100.0 * processed / total if total > 0 else 0
    print(
        f"\r[{processed:,}/{total:,}] {pct:.1f}% | "
        f"{success:,} ok, {errors:,} err | "
        f"{rate:.1f} synsets/s | "
        f"ETA {_format_duration(eta)}",
        end="", file=sys.stderr, flush=True,
    )


def _write_error_log(error_records: list[dict], output_dir: Path) -> None:
    """Write structured JSONL error log + backward-compat plain ID list."""
    if not error_records:
        return

    # Structured log
    err_jsonl = output_dir / "_errors.jsonl"
    with open(err_jsonl, "w", encoding="utf-8") as f:
        for record in error_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Backward-compat plain list
    err_txt = output_dir / "_errors.txt"
    with open(err_txt, "w") as f:
        for record in error_records:
            f.write(record["synset_id"] + "\n")

    print(f"  Error details: {err_jsonl}", file=sys.stderr)
    print(f"  Error IDs:     {err_txt}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Run evidence pipeline on all AWN4 synsets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                                    # full run, compressed, auto workers
  %(prog)s --resume                           # resume interrupted run
  %(prog)s --resume --no-compress             # resume in plain YAML mode
  %(prog)s --workers 4 --pos n --limit 1000   # 4 workers, first 1000 nouns
""",
    )
    # Existing flags
    parser.add_argument("--db", default="data/arabic_dict.db", help="Path to arabic_dict.db")
    parser.add_argument("--output-dir", default="output/evidence", help="Output directory")
    parser.add_argument("--resume", action="store_true", help="Skip synsets with existing output")
    parser.add_argument("--pos", choices=["n", "v", "a", "s", "r"], help="Filter by POS")
    parser.add_argument("--limit", type=int, help="Process only first N synsets")
    # New flags
    parser.add_argument("--workers", "-j", type=int, default=None,
                        help="Number of parallel workers (default: min(cpu_count, 8))")
    parser.add_argument("--compress", action="store_true", default=True,
                        help="Write .yaml.gz output (default: on)")
    parser.add_argument("--no-compress", action="store_false", dest="compress",
                        help="Write plain .yaml output")
    parser.add_argument("--retries", type=int, default=3,
                        help="Max retry attempts per synset (default: 3)")
    parser.add_argument("--chunksize", type=int, default=16,
                        help="imap_unordered chunk size (default: 16)")
    args = parser.parse_args()

    # Resolve paths
    workspace = Path(__file__).resolve().parent.parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = workspace / args.db
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = workspace / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    n_workers = args.workers or min(cpu_count(), 8)

    # ── Collect synset IDs ──────────────────────────────────────────────
    ar_lexicons = [l for l in wn.lexicons() if l.language == "arb"]
    if not ar_lexicons:
        print("Error: AWN4 not loaded. Run: python3 -c \"import wn; wn.add(...)\"", file=sys.stderr)
        sys.exit(1)
    ar_wn = wn.Wordnet(ar_lexicons[0].specifier())
    synsets = ar_wn.synsets()

    if args.pos:
        synsets = [s for s in synsets if s.pos == args.pos]
    if args.limit:
        synsets = synsets[:args.limit]

    synset_ids = [s.id for s in synsets]

    # ── Resumption ──────────────────────────────────────────────────────
    if args.resume:
        synset_ids = _filter_resumed(synset_ids, output_dir)

    total = len(synset_ids)
    if total == 0:
        print("Nothing to process.", file=sys.stderr)
        sys.exit(0)

    ext_label = ".yaml.gz" if args.compress else ".yaml"
    print(f"Processing {total:,} synsets → {output_dir} ({ext_label})", file=sys.stderr)
    print(f"Workers: {n_workers} | Retries: {args.retries} | Chunksize: {args.chunksize}",
          file=sys.stderr)

    # ── Run pool ────────────────────────────────────────────────────────
    success = 0
    errors = 0
    retried = 0
    error_records: list[dict] = []
    t_start = time.time()

    pool = Pool(
        processes=n_workers,
        initializer=_worker_init,
        initargs=(str(db_path), str(output_dir), args.compress, args.retries),
    )

    try:
        for result in pool.imap_unordered(_worker_process, synset_ids, chunksize=args.chunksize):
            sid, ok, err_msg, attempts = result

            if ok:
                success += 1
                if attempts > 1:
                    retried += 1
            else:
                errors += 1
                error_records.append({
                    "synset_id": sid,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "attempts": attempts,
                    "traceback": err_msg,
                })

            processed = success + errors
            if processed % 100 == 0 or processed == total:
                _report_progress(processed, total, success, errors, t_start)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Terminating workers...", file=sys.stderr)
        pool.terminate()
        pool.join()
        elapsed = time.time() - t_start
        processed = success + errors
        print(f"Partial run: {processed:,} processed in {_format_duration(elapsed)} "
              f"({success:,} ok, {errors:,} err)", file=sys.stderr)
        if error_records:
            _write_error_log(error_records, output_dir)
        print("Use --resume to continue.", file=sys.stderr)
        sys.exit(130)
    finally:
        pool.close()
        pool.join()

    # ── Summary ─────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(file=sys.stderr)  # newline after \r progress
    print(f"\nDone in {_format_duration(elapsed)}.", file=sys.stderr)
    print(f"  Success: {success:,}/{total:,}", file=sys.stderr)
    if retried:
        print(f"  Retried: {retried:,} (succeeded after retry)", file=sys.stderr)
    print(f"  Errors:  {errors:,}/{total:,}", file=sys.stderr)

    _write_error_log(error_records, output_dir)

    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
