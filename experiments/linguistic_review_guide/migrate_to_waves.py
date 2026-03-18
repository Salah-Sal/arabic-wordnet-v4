#!/usr/bin/env python3
"""Migrate AWN4 reviews from 4 flat directories into a unified wave-based tree.

Reads wave files (W0.txt–W6.txt) to map synset→wave, scans all 4 legacy
output directories, resolves duplicates by keeping the newest file (mtime),
and copies winners into output/reviews/{wave_id}/.

Usage:
    python3 migrate_to_waves.py              # dry-run (default)
    python3 migrate_to_waves.py --execute    # actually copy files
    python3 migrate_to_waves.py --execute --force  # overwrite existing files

Safety: Copy-only — old directories are never modified.  Can be re-run safely.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──

GUIDE_DIR = Path(__file__).resolve().parent

LEGACY_DIRS = [
    GUIDE_DIR / "output" / "reviews_pipeline_v2",
    GUIDE_DIR / "output" / "reviews_gemini_pipeline_v2",
    GUIDE_DIR / "output" / "reviews_claude_db",
    GUIDE_DIR / "output" / "reviews_gemini_db",
]

WAVES_DIR = GUIDE_DIR / "gemini_code_db" / "waves"
OUTPUT_ROOT = GUIDE_DIR / "output" / "reviews"
WAVE_IDS = ["W0", "W1", "W2", "W3", "W4", "W5", "W6"]

# File extensions that travel with a review
REVIEW_EXTENSIONS = [".review.yaml", ".trajectory.jsonl", ".stderr.log"]


def read_wave_file(wave_id: str) -> list[str]:
    """Read synset IDs from a wave file, skipping comments and blanks."""
    path = WAVES_DIR / f"{wave_id}.txt"
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def build_synset_wave_map() -> dict[str, str]:
    """Build synset_id → wave_id mapping from all wave files."""
    mapping: dict[str, str] = {}
    for wid in WAVE_IDS:
        for sid in read_wave_file(wid):
            mapping[sid] = wid
    return mapping


def scan_legacy_dirs() -> dict[str, list[tuple[Path, float]]]:
    """Scan all legacy dirs.  Returns {synset_id: [(dir_path, mtime), ...]}."""
    found: dict[str, list[tuple[Path, float]]] = {}
    for d in LEGACY_DIRS:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.name.endswith(".review.yaml"):
                synset_id = f.name[: -len(".review.yaml")]
                mtime = f.stat().st_mtime
                found.setdefault(synset_id, []).append((d, mtime))
    return found


def resolve_duplicates(
    found: dict[str, list[tuple[Path, float]]],
) -> tuple[dict[str, Path], list[dict]]:
    """For each synset, pick the directory with the newest mtime.

    Returns:
        winners: {synset_id: winning_dir_path}
        log: list of resolution dicts (for audit trail)
    """
    winners: dict[str, Path] = {}
    log: list[dict] = []

    for synset_id, entries in found.items():
        if len(entries) == 1:
            winners[synset_id] = entries[0][0]
        else:
            # Sort by mtime descending — newest first
            entries.sort(key=lambda e: e[1], reverse=True)
            winner_dir, winner_mtime = entries[0]
            winners[synset_id] = winner_dir
            log.append({
                "synset_id": synset_id,
                "winner": winner_dir.name,
                "winner_mtime": datetime.fromtimestamp(
                    winner_mtime, tz=timezone.utc
                ).isoformat(),
                "losers": [
                    {
                        "dir": e[0].name,
                        "mtime": datetime.fromtimestamp(
                            e[1], tz=timezone.utc
                        ).isoformat(),
                    }
                    for e in entries[1:]
                ],
            })

    return winners, log


def copy_review_files(
    synset_id: str, source_dir: Path, dest_dir: Path, force: bool
) -> list[str]:
    """Copy all associated files for a synset.  Returns list of copied filenames."""
    copied = []
    for ext in REVIEW_EXTENSIONS:
        src = source_dir / f"{synset_id}{ext}"
        if not src.exists():
            continue
        dst = dest_dir / src.name
        if dst.exists() and not force:
            continue
        shutil.copy2(src, dst)
        copied.append(src.name)
    return copied


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually copy files (default is dry-run)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files in destination",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        print("=== DRY RUN (pass --execute to copy files) ===\n")

    # 1. Build synset→wave mapping
    synset_wave = build_synset_wave_map()
    print(f"Wave mapping: {len(synset_wave):,} synsets across {len(WAVE_IDS)} waves")

    # 2. Scan legacy dirs
    found = scan_legacy_dirs()
    total_files = sum(len(v) for v in found.values())
    print(f"Legacy dirs:  {total_files:,} review files, {len(found):,} unique synsets")

    # 3. Resolve duplicates
    winners, dup_log = resolve_duplicates(found)
    duplicates = total_files - len(winners)
    print(f"Duplicates:   {duplicates} resolved (kept newest by mtime)")

    # 4. Map to waves
    wave_counts: dict[str, int] = {wid: 0 for wid in WAVE_IDS}
    wave_counts["_orphans"] = 0
    orphans: list[str] = []

    for synset_id in winners:
        wave_id = synset_wave.get(synset_id)
        if wave_id:
            wave_counts[wave_id] += 1
        else:
            wave_counts["_orphans"] += 1
            orphans.append(synset_id)

    # 5. Copy files (or report in dry-run)
    total_copied = 0
    for synset_id, source_dir in winners.items():
        wave_id = synset_wave.get(synset_id, "_orphans")
        dest_dir = OUTPUT_ROOT / wave_id

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            copied = copy_review_files(synset_id, source_dir, dest_dir, args.force)
            total_copied += len(copied)

    # 6. Write manifest
    manifest = {
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "total_unique_synsets": len(winners),
        "total_legacy_files": total_files,
        "duplicates_resolved": duplicates,
        "per_wave": {k: v for k, v in sorted(wave_counts.items()) if v > 0},
        "orphans": sorted(orphans),
        "duplicate_resolutions": dup_log,
    }

    if not dry_run:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        manifest_path = OUTPUT_ROOT / "_migration_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        )
        print(f"\nManifest: {manifest_path}")
        print(f"Copied:   {total_copied} files")

    # 7. Summary
    print(f"\n{'Wave':<10} {'Synsets':>8}")
    print("-" * 20)
    for wid in WAVE_IDS:
        if wave_counts[wid]:
            print(f"{wid:<10} {wave_counts[wid]:>8,}")
    if wave_counts["_orphans"]:
        print(f"{'_orphans':<10} {wave_counts['_orphans']:>8,}")
    print("-" * 20)
    print(f"{'TOTAL':<10} {len(winners):>8,}")

    if dry_run:
        print("\n(No files were copied. Run with --execute to migrate.)")


if __name__ == "__main__":
    main()
