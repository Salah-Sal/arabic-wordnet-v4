#!/usr/bin/env python3
"""Prepare evidence files for Claude Code autonomous review.

Decompresses .evidence.yaml.gz files, applies process_evidence() slimming,
extracts synset_info + synset_info_masked, writes to prepared/{synset_id}/.

Usage:
    python prepare.py --evidence-dir /path/to/evidence          # all files
    python prepare.py --synset awn4-00081062-n                   # single synset
    python prepare.py --output-dir prepared --force --stats      # overwrite + stats
"""
from __future__ import annotations

import argparse
import gzip
import sys
import time
from pathlib import Path

import yaml

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader

# ── Import from legacy (pure Python, no DSPy) ──
SCRIPT_DIR = Path(__file__).resolve().parent
GUIDE_DIR = SCRIPT_DIR.parent  # linguistic_review_guide/
sys.path.insert(0, str(GUIDE_DIR / "legacy"))
from assemble_prompts_v2 import (  # noqa: E402
    ArabicDumper,
    process_evidence,
    extract_synset_info,
)

# Import masking function (pure Python, no DSPy)
sys.path.insert(0, str(GUIDE_DIR))
from dspy_review.extractors import mask_synset_info  # noqa: E402

# ── Defaults ──
DEFAULT_EVIDENCE_DIR = (
    GUIDE_DIR.parent / "manual_linguist_review" / "linguist_workspace"
    / "output" / "evidence"
)
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "prepared"


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        Dumper=ArabicDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=200,
    )


def read_evidence(path: Path) -> dict:
    if path.suffix == ".gz" or path.name.endswith(".yaml.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return yaml.load(f, Loader=_Loader)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


def extract_synset_id(filename: str) -> str:
    return filename.replace(".evidence.yaml.gz", "").replace(".evidence.yaml", "")


def list_evidence_files(evidence_dir: Path) -> list[Path]:
    files = sorted(evidence_dir.glob("*.evidence.yaml*"))
    return [f for f in files if f.name.endswith((".evidence.yaml", ".evidence.yaml.gz"))]


def process_one(filepath: Path, output_dir: Path, force: bool = False) -> dict:
    """Process a single evidence file. Returns stats dict."""
    synset_id = extract_synset_id(filepath.name)
    out_dir = output_dir / synset_id

    if not force and (out_dir / "evidence.yaml").exists():
        return {"synset_id": synset_id, "status": "skip"}

    raw = read_evidence(filepath)
    synset_info = extract_synset_info(raw)
    synset_info_masked = mask_synset_info(synset_info)
    processed = process_evidence(raw)
    evidence_yaml = dump_yaml(processed)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "synset_info.yaml").write_text(synset_info, encoding="utf-8")
    (out_dir / "synset_info_masked.yaml").write_text(synset_info_masked, encoding="utf-8")
    (out_dir / "evidence.yaml").write_text(evidence_yaml, encoding="utf-8")

    return {
        "synset_id": synset_id,
        "status": "ok",
        "evidence_lines": evidence_yaml.count("\n"),
        "synset_info_lines": synset_info.count("\n"),
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR,
        help=f"Directory with .evidence.yaml[.gz] files (default: {DEFAULT_EVIDENCE_DIR})",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for prepared files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--synset", type=str, default=None,
        help="Process a single synset ID (e.g., awn4-00081062-n)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing prepared files",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print detailed per-synset stats",
    )
    args = parser.parse_args()

    evidence_dir = args.evidence_dir
    output_dir = args.output_dir

    # ── Discover files ──
    if args.synset:
        # Find the specific file
        candidates = list(evidence_dir.glob(f"{args.synset}.evidence.yaml*"))
        if not candidates:
            print(f"Error: no evidence file for {args.synset} in {evidence_dir}")
            sys.exit(1)
        files = candidates[:1]
    else:
        files = list_evidence_files(evidence_dir)

    if not files:
        print(f"No evidence files found in {evidence_dir}")
        sys.exit(1)

    print(f"Evidence dir: {evidence_dir}")
    print(f"Output dir:   {output_dir}")
    print(f"Files to process: {len(files)}")
    print()

    # ── Process ──
    ok = skip = fail = 0
    t0 = time.time()

    for i, filepath in enumerate(files, 1):
        synset_id = extract_synset_id(filepath.name)
        try:
            result = process_one(filepath, output_dir, force=args.force)
            if result["status"] == "skip":
                skip += 1
                if args.stats:
                    print(f"[{i}/{len(files)}] SKIP: {synset_id}")
            else:
                ok += 1
                if args.stats:
                    print(
                        f"[{i}/{len(files)}] OK: {synset_id} "
                        f"({result['evidence_lines']} evidence lines, "
                        f"{result['synset_info_lines']} info lines)"
                    )
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(files)}] FAIL: {synset_id}: {e}")

        if not args.stats and i % 1000 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed
            print(f"  Progress: {i}/{len(files)} ({rate:.0f}/s)")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s: {ok} ok, {skip} skipped, {fail} failed")


if __name__ == "__main__":
    main()
