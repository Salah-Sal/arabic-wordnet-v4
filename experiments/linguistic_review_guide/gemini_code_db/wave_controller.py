#!/usr/bin/env python3
"""
AWN4 Noun Review — Wave Controller & Campaign Progress Tracker

Orchestrates the full 84,956-synset noun review by partitioning work into
BFS-depth waves, tracking progress in campaign.db, and wrapping the existing
batch_runner.py / extract_synset_info.py pipeline.

The wave controller is a thin orchestration layer — it does NOT modify the
underlying pipeline logic. It wraps existing tools:

    - generate_bfs_batch.py  →  produces wave batch files (waves/WX.txt)
    - extract_synset_info.py →  prepares synset metadata (prepared/{synset_id}/)
    - docker/run_batch.sh    →  launches Dockerized batch_runner.py

Progress is tracked in campaign.db (SQLite WAL-mode), which cross-references
the per-run .batch_status.db maintained by batch_runner.py.

Subcommands:
    init      Create campaign.db, generate wave batch files via generate_bfs_batch.py
    status    Dashboard: per-wave and overall progress, throughput, cost, ETA
    sync      Scan disk for .review.yaml files, update campaign.db from disk truth
    prepare   Run extract_synset_info.py for a wave's synsets
    execute   Run docker/run_batch.sh for a wave (with auto sub-wave splitting)

Usage:
    python3 wave_controller.py init                          # First-time setup
    python3 wave_controller.py sync                          # Scan disk → update DB
    python3 wave_controller.py status                        # Progress dashboard
    python3 wave_controller.py prepare W2                    # Prepare wave W2
    python3 wave_controller.py execute W2                    # Execute wave W2
    python3 wave_controller.py execute W4 --continue-on-error  # Large wave with sub-waves

See README.md for full documentation and architecture overview.
"""

import argparse
import math
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CAMPAIGN_YAML = SCRIPT_DIR / "campaign.yaml"
DEFAULT_CAMPAIGN_DB = SCRIPT_DIR / "campaign.db"
WAVES_DIR = SCRIPT_DIR / "waves"
GENERATE_BFS = SCRIPT_DIR / "generate_bfs_batch.py"
EXTRACT_SYNSET = SCRIPT_DIR / "extract_synset_info.py"
DOCKER_RUN_BATCH = SCRIPT_DIR / "docker" / "run_batch.sh"


# ---------------------------------------------------------------------------
# Campaign DB helpers
# ---------------------------------------------------------------------------

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS waves (
    wave_id        TEXT PRIMARY KEY,
    depth_min      INTEGER NOT NULL,
    depth_max      INTEGER NOT NULL,
    synset_count   INTEGER DEFAULT 0,
    batch_file     TEXT,
    status         TEXT DEFAULT 'pending',
    prepared_count INTEGER DEFAULT 0,
    reviewed_count INTEGER DEFAULT 0,
    failed_count   INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    started_at     TEXT,
    finished_at    TEXT
);

CREATE TABLE IF NOT EXISTS sub_waves (
    sub_wave_id  TEXT PRIMARY KEY,
    wave_id      TEXT NOT NULL REFERENCES waves(wave_id),
    batch_file   TEXT,
    run_id       TEXT,
    synset_count INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    reviewed     INTEGER DEFAULT 0,
    failed       INTEGER DEFAULT 0,
    cost_usd     REAL DEFAULT 0.0,
    started_at   TEXT,
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS synset_waves (
    synset_id   TEXT PRIMARY KEY,
    wave_id     TEXT NOT NULL,
    sub_wave_id TEXT,
    bfs_depth   INTEGER,
    prepared    INTEGER DEFAULT 0,
    reviewed    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sw_wave ON synset_waves(wave_id);
CREATE INDEX IF NOT EXISTS idx_sw_sub  ON synset_waves(sub_wave_id);
"""


def open_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) campaign.db with WAL mode."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Batch file helpers
# ---------------------------------------------------------------------------

def read_batch_ids(batch_file: Path) -> list[str]:
    """Read synset IDs from a batch file, skipping comment lines and blanks.

    Batch files have a header block of ``# ...`` lines followed by one
    synset ID per line (e.g. ``awn4-00001740-n``).
    """
    ids = []
    with open(batch_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.append(line)
    return ids


def parse_batch_depth_counts(batch_file: Path) -> dict[int, int]:
    """Parse the '# L0:1 L1:10 ...' header line to get per-depth counts."""
    counts = {}
    with open(batch_file) as f:
        for line in f:
            if not line.startswith("#"):
                break
            # Look for lines like "# L0:1 L1:10 L2:85"
            if "L0:" in line or "L1:" in line or "L2:" in line or "L3:" in line or "L4:" in line or "L5:" in line:
                import re
                for m in re.finditer(r"L(\d+):(\d+)", line):
                    counts[int(m.group(1))] = int(m.group(2))
    return counts


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Create campaign.db, generate wave batch files, populate synset_waves.

    For each wave defined in campaign.yaml, this:
    1. Calls generate_bfs_batch.py with the wave's depth range to produce waves/WX.txt
    2. Inserts/updates the wave row in campaign.db
    3. Populates synset_waves with every synset ID from the batch file

    Idempotent: re-running skips existing batch files (use --force to regenerate).
    """
    config = load_config(args.config)
    campaign = config["campaign"]
    waves = config["waves"]

    # Create waves/ directory
    WAVES_DIR.mkdir(exist_ok=True)

    db = open_db(args.db)

    for wave in waves:
        wave_id = wave["id"]
        depth_min, depth_max = wave["depth"]
        batch_file = WAVES_DIR / f"{wave_id}.txt"

        # Generate batch file via generate_bfs_batch.py
        if batch_file.exists() and not args.force:
            print(f"  {wave_id}: {batch_file.name} already exists, skipping generation")
        else:
            print(f"  {wave_id}: generating batch file (depth {depth_min}-{depth_max})...")
            cmd = [
                sys.executable, str(GENERATE_BFS),
                "--min-depth", str(depth_min),
                "--max-depth", str(depth_max),
                "-o", str(batch_file),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"    ERROR: {result.stderr.strip()}", file=sys.stderr)
                continue
            if result.stderr:
                # generate_bfs_batch.py prints stats to stderr
                for line in result.stderr.strip().split("\n"):
                    print(f"    {line}")

        # Read synset IDs from the batch file
        synset_ids = read_batch_ids(batch_file)
        depth_counts = parse_batch_depth_counts(batch_file)

        # Determine initial status from config
        initial_status = wave.get("status", "pending")

        # Upsert wave row
        db.execute("""
            INSERT INTO waves (wave_id, depth_min, depth_max, synset_count, batch_file, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(wave_id) DO UPDATE SET
                depth_min = excluded.depth_min,
                depth_max = excluded.depth_max,
                synset_count = excluded.synset_count,
                batch_file = excluded.batch_file
        """, (wave_id, depth_min, depth_max, len(synset_ids), str(batch_file), initial_status))

        # Populate synset_waves (assign depth based on depth_counts if we can infer it)
        # For simplicity, we assign depth as None and let sync fill it from batch headers
        # Actually, we can reconstruct depth from the BFS order in the file
        # But it's simpler to just set wave_id and let depth remain approximate
        for sid in synset_ids:
            db.execute("""
                INSERT INTO synset_waves (synset_id, wave_id)
                VALUES (?, ?)
                ON CONFLICT(synset_id) DO UPDATE SET wave_id = excluded.wave_id
            """, (sid, wave_id))

        print(f"  {wave_id}: {len(synset_ids)} synsets (L{depth_min}-L{depth_max})")

    db.commit()

    # Summary
    total = db.execute("SELECT COUNT(*) FROM synset_waves").fetchone()[0]
    print(f"\nCampaign initialized: {total} synsets across {len(waves)} waves")
    print(f"Database: {args.db}")
    print(f"Batch files: {WAVES_DIR}/")

    db.close()


# ---------------------------------------------------------------------------
# Subcommand: sync
# ---------------------------------------------------------------------------

def cmd_sync(args):
    """Scan output dir for .review.yaml files and update campaign.db.

    This is the source-of-truth reconciliation step:
    1. Counts *.review.yaml files → marks synset_waves.reviewed
    2. Counts prepared/*/ dirs → marks synset_waves.prepared
    3. Aggregates counts per wave (reviewed_count, prepared_count)
    4. Pulls cost/failure data from .batch_status.db (if it exists)
    5. Auto-detects wave status: done | partial | pending

    Safe to run at any time — purely reads disk state and updates campaign.db.
    """
    config = load_config(args.config)
    campaign = config["campaign"]

    output_dir = (SCRIPT_DIR / campaign["output_dir"]).resolve()
    prepared_dir = (SCRIPT_DIR / campaign["prepared_dir"]).resolve()
    batch_status_db = output_dir / ".batch_status.db"

    db = open_db(args.db)

    # 1. Scan for existing .review.yaml files (wave subdirs + flat fallback)
    review_files = []
    for wave_dir in sorted(output_dir.iterdir()) if output_dir.exists() else []:
        if wave_dir.is_dir() and wave_dir.name.startswith("W"):
            review_files.extend(wave_dir.glob("*.review.yaml"))
    # Also check flat layout (legacy or transition period)
    review_files.extend(output_dir.glob("*.review.yaml"))
    reviewed_ids = {f.stem.replace(".review", "") for f in review_files}
    print(f"Found {len(reviewed_ids)} review files in {output_dir}")

    # 2. Scan for prepared/ directories
    prepared_ids = set()
    if prepared_dir.exists():
        prepared_ids = {d.name for d in prepared_dir.iterdir() if d.is_dir()}
    print(f"Found {len(prepared_ids)} prepared directories in {prepared_dir}")

    # 3. Update synset_waves
    updated_reviewed = 0
    updated_prepared = 0
    for sid, in db.execute("SELECT synset_id FROM synset_waves"):
        changes = {}
        if sid in reviewed_ids:
            changes["reviewed"] = 1
            updated_reviewed += 1
        if sid in prepared_ids:
            changes["prepared"] = 1
            updated_prepared += 1
        if changes:
            sets = ", ".join(f"{k} = {v}" for k, v in changes.items())
            db.execute(f"UPDATE synset_waves SET {sets} WHERE synset_id = ?", (sid,))

    db.commit()
    print(f"Updated: {updated_reviewed} reviewed, {updated_prepared} prepared")

    # 4. Aggregate per-wave counts
    for row in db.execute("""
        SELECT wave_id,
               COUNT(*) as total,
               SUM(reviewed) as reviewed,
               SUM(prepared) as prepared
        FROM synset_waves
        GROUP BY wave_id
        ORDER BY wave_id
    """):
        wave_id, total, reviewed, prepared = row
        db.execute("""
            UPDATE waves
            SET reviewed_count = ?, prepared_count = ?
            WHERE wave_id = ?
        """, (reviewed, prepared, wave_id))

    # 5. Pull cost/failure data from .batch_summary.json (preferred) or .batch_status.db
    summary_json_path = output_dir / ".batch_summary.json"
    if summary_json_path.exists():
        import json as _json
        try:
            summary = _json.loads(summary_json_path.read_text())
            total_cost = summary.get("total_cost", 0.0)
            total_failed = summary.get("failed", 0)
            print(f"Batch summary JSON: total cost ${total_cost:.2f}, {total_failed} failures")
            # Apply cost to all waves proportionally (summary is per-run aggregate)
            for wave_id, in db.execute("SELECT wave_id FROM waves"):
                db.execute(
                    "UPDATE waves SET total_cost_usd = ? WHERE wave_id = ?",
                    (total_cost, wave_id)
                )
        except (ValueError, OSError) as e:
            print(f"WARNING: .batch_summary.json unreadable ({e}), skipping cost data")
    elif batch_status_db.exists():
        try:
            bsdb = sqlite3.connect(str(batch_status_db))
            bsdb.execute("PRAGMA integrity_check")
            # Sum costs across all runs
            total_cost = bsdb.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0) FROM batch_runs"
            ).fetchone()[0]

            # Count failures per synset (across all runs, take worst status)
            failed_ids = set()
            for sid, in bsdb.execute(
                "SELECT DISTINCT synset_id FROM synset_status WHERE status = 'failed'"
            ):
                # Only count as failed if NOT also succeeded in another run
                succeeded = bsdb.execute(
                    "SELECT 1 FROM synset_status WHERE synset_id = ? AND status = 'success'",
                    (sid,)
                ).fetchone()
                if not succeeded:
                    failed_ids.add(sid)

            # Per-synset costs (sum across all runs for each synset)
            synset_costs = {}
            for sid, cost in bsdb.execute(
                "SELECT synset_id, COALESCE(SUM(cost_usd), 0) FROM synset_status GROUP BY synset_id"
            ):
                synset_costs[sid] = cost

            bsdb.close()
        except sqlite3.DatabaseError as e:
            print(f"WARNING: .batch_status.db is corrupted ({e}), skipping cost/failure data")
            total_cost = 0
            failed_ids = set()
            synset_costs = {}

        # Distribute costs and failures into waves
        for wave_id, in db.execute("SELECT wave_id FROM waves"):
            wave_synsets = {r[0] for r in db.execute(
                "SELECT synset_id FROM synset_waves WHERE wave_id = ?", (wave_id,)
            )}
            wave_failed = len(failed_ids & wave_synsets)
            wave_cost = sum(synset_costs.get(sid, 0) for sid in wave_synsets)
            db.execute(
                "UPDATE waves SET failed_count = ?, total_cost_usd = ? WHERE wave_id = ?",
                (wave_failed, wave_cost, wave_id)
            )

        print(f"Batch status DB: total cost ${total_cost:.2f}, {len(failed_ids)} net failures")

    # 6. Auto-detect wave status
    for row in db.execute("SELECT wave_id, synset_count, reviewed_count, failed_count FROM waves"):
        wave_id, total, reviewed, failed = row
        if total == 0:
            continue
        if reviewed >= total:
            new_status = "done"
        elif reviewed > 0:
            new_status = "partial"
        else:
            new_status = "pending"
        # Don't override executing status
        current = db.execute("SELECT status FROM waves WHERE wave_id = ?",
                             (wave_id,)).fetchone()[0]
        if current != "executing":
            db.execute("UPDATE waves SET status = ? WHERE wave_id = ?",
                       (new_status, wave_id))

    db.commit()
    db.close()
    print("Sync complete.")


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Display campaign progress dashboard.

    Shows:
    - Overall progress (reviewed / tree_size)
    - Per-wave table (status, progress, depth, prepared, failed)
    - Sub-wave details (if any exist)
    - Throughput estimate and ETA based on .batch_status.db timing data
    """
    config = load_config(args.config)
    campaign = config["campaign"]
    tree_size = campaign["tree_size"]

    db = open_db(args.db)

    # Check if waves table has data
    wave_count = db.execute("SELECT COUNT(*) FROM waves").fetchone()[0]
    if wave_count == 0:
        print("No campaign data. Run 'wave_controller.py init' first.")
        db.close()
        return

    # Overall stats
    totals = db.execute("""
        SELECT COALESCE(SUM(synset_count), 0),
               COALESCE(SUM(reviewed_count), 0),
               COALESCE(SUM(prepared_count), 0),
               COALESCE(SUM(failed_count), 0),
               COALESCE(SUM(total_cost_usd), 0)
        FROM waves
    """).fetchone()
    total_synsets, total_reviewed, total_prepared, total_failed, total_cost = totals

    pct = (total_reviewed / tree_size * 100) if tree_size else 0

    print(f"\n  AWN4 Noun Review: {total_reviewed}/{tree_size:,} ({pct:.1f}%)")
    print(f"  Prepared: {total_prepared:,}  |  Failed: {total_failed}  |  Cost: ${total_cost:.2f}")
    print()

    # Per-wave table
    hdr = f"  {'Wave':<6} {'Status':<10} {'Progress':<16} {'Depth':<8} {'Prepared':<10} {'Failed':<8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for row in db.execute("""
        SELECT wave_id, depth_min, depth_max, synset_count, status,
               prepared_count, reviewed_count, failed_count
        FROM waves
        ORDER BY depth_min, wave_id
    """):
        wid, dmin, dmax, count, status, prepared, reviewed, failed = row
        if dmin == dmax:
            depth_str = f"L{dmin}"
        else:
            depth_str = f"L{dmin}-L{dmax}"

        progress = f"{reviewed}/{count}"
        print(f"  {wid:<6} {status:<10} {progress:<16} {depth_str:<8} {prepared:<10} {failed:<8}")

    # Sub-waves if any exist
    sub_count = db.execute("SELECT COUNT(*) FROM sub_waves").fetchone()[0]
    if sub_count > 0:
        print(f"\n  Sub-waves: {sub_count}")
        for row in db.execute("""
            SELECT sub_wave_id, wave_id, synset_count, status, reviewed, failed
            FROM sub_waves ORDER BY sub_wave_id
        """):
            swid, wid, count, status, reviewed, failed = row
            print(f"    {swid:<14} ({wid})  {status:<10}  {reviewed}/{count}  failed:{failed}")

    # Throughput estimate
    if total_reviewed > 0:
        output_dir = (SCRIPT_DIR / campaign["output_dir"]).resolve()
        summary_json_path = output_dir / ".batch_summary.json"
        batch_status_db = output_dir / ".batch_status.db"

        first_start = None
        last_finish = None

        # Prefer .batch_summary.json (safe to read while container runs)
        if summary_json_path.exists():
            import json as _json
            try:
                summary = _json.loads(summary_json_path.read_text())
                last_finish = summary.get("finished_at")
            except (ValueError, OSError):
                pass

        # Fall back to .batch_status.db for first_start (or full timing)
        if batch_status_db.exists():
            try:
                bsdb = sqlite3.connect(str(batch_status_db))
                first_start = bsdb.execute(
                    "SELECT MIN(started_at) FROM batch_runs"
                ).fetchone()[0]
                if not last_finish:
                    last_finish = bsdb.execute(
                        "SELECT MAX(finished_at) FROM batch_runs WHERE finished_at IS NOT NULL"
                    ).fetchone()[0]
                bsdb.close()
            except sqlite3.DatabaseError:
                pass

        if first_start and last_finish:
            start_dt = datetime.fromisoformat(first_start)
            end_dt = datetime.fromisoformat(last_finish)
            elapsed_days = max((end_dt - start_dt).total_seconds() / 86400, 0.01)
            rate = total_reviewed / elapsed_days
            remaining = tree_size - total_reviewed
            est_days = remaining / rate if rate > 0 else float("inf")
            print(f"\n  Throughput: ~{rate:.0f} synsets/day")
            print(f"  Remaining: ~{remaining:,} synsets (~{est_days:.0f} days at current rate)")

    print()
    db.close()


# ---------------------------------------------------------------------------
# Subcommand: prepare
# ---------------------------------------------------------------------------

def cmd_prepare(args):
    """Run extract_synset_info.py for a wave's synsets.

    Generates prepared/{synset_id}/ directories containing:
    - synset_info.yaml (full metadata)
    - synset_info_masked.yaml (lemmas removed for blind generation)
    - evidence.json (pre-fetched dictionary evidence)

    Idempotent: extract_synset_info.py skips existing prepared/ dirs
    unless --force is passed.
    """
    db = open_db(args.db)

    # Verify wave exists
    wave = db.execute("SELECT wave_id, batch_file, synset_count FROM waves WHERE wave_id = ?",
                      (args.wave_id,)).fetchone()
    if not wave:
        print(f"Error: wave '{args.wave_id}' not found. Run 'init' first.", file=sys.stderr)
        db.close()
        sys.exit(1)

    wave_id, batch_file, synset_count = wave
    batch_path = Path(batch_file)

    if not batch_path.exists():
        print(f"Error: batch file {batch_path} not found.", file=sys.stderr)
        db.close()
        sys.exit(1)

    print(f"Preparing {wave_id}: {synset_count} synsets from {batch_path.name}")

    # extract_synset_info.py already skips existing prepared/ dirs
    cmd = [sys.executable, str(EXTRACT_SYNSET), "--batch", str(batch_path)]
    if args.force:
        cmd.append("--force")

    db.execute("UPDATE waves SET status = 'preparing' WHERE wave_id = ?", (wave_id,))
    db.commit()

    result = subprocess.run(cmd)

    if result.returncode == 0:
        db.execute("UPDATE waves SET status = 'prepared' WHERE wave_id = ?", (wave_id,))
        db.commit()
        print(f"Preparation complete for {wave_id}. Run 'sync' to update counts.")
    else:
        print(f"Preparation failed for {wave_id} (exit code {result.returncode})",
              file=sys.stderr)

    db.close()


# ---------------------------------------------------------------------------
# Subcommand: execute
# ---------------------------------------------------------------------------

def cmd_execute(args):
    """Run docker/run_batch.sh for a wave, splitting into sub-waves if needed.

    For small waves (synset_count <= sub_wave_size or no sub_wave_size configured):
        Runs the entire wave as a single docker/run_batch.sh invocation.

    For large waves (synset_count > sub_wave_size):
        1. Splits the batch file into chunks of sub_wave_size synsets
        2. Creates sub-wave batch files (waves/WX_subN.txt)
        3. Registers sub-waves in campaign.db
        4. Executes sub-waves sequentially (use --continue-on-error to skip failures)

    The underlying batch_runner.py handles concurrency, retry, and model fallback
    within each (sub-)wave execution.
    """
    config = load_config(args.config)
    db = open_db(args.db)

    # Look up wave config
    wave_row = db.execute(
        "SELECT wave_id, batch_file, synset_count FROM waves WHERE wave_id = ?",
        (args.wave_id,)
    ).fetchone()
    if not wave_row:
        print(f"Error: wave '{args.wave_id}' not found.", file=sys.stderr)
        db.close()
        sys.exit(1)

    wave_id, batch_file, synset_count = wave_row
    batch_path = Path(batch_file)

    # Find wave config for sub_wave_size and workers
    wave_cfg = None
    for w in config["waves"]:
        if w["id"] == wave_id:
            wave_cfg = w
            break

    workers = args.workers or (wave_cfg.get("workers", 2) if wave_cfg else 2)
    sub_wave_size = wave_cfg.get("sub_wave_size") if wave_cfg else None

    if sub_wave_size and synset_count > sub_wave_size:
        # Split into sub-waves
        synset_ids = read_batch_ids(batch_path)
        num_subs = math.ceil(len(synset_ids) / sub_wave_size)
        print(f"Splitting {wave_id} ({len(synset_ids)} synsets) into {num_subs} sub-waves of ~{sub_wave_size}")

        for i in range(num_subs):
            chunk = synset_ids[i * sub_wave_size : (i + 1) * sub_wave_size]
            sub_id = f"{wave_id}_sub{i}"
            sub_batch = WAVES_DIR / f"{sub_id}.txt"

            # Write sub-wave batch file with header
            with open(sub_batch, "w") as f:
                f.write(f"# Sub-wave {sub_id} from {wave_id}\n")
                f.write(f"# Total: {len(chunk)} | Tree: {config['campaign']['tree_size']}\n")
                f.write("#\n")
                for sid in chunk:
                    f.write(sid + "\n")

            # Register sub-wave in DB
            db.execute("""
                INSERT INTO sub_waves (sub_wave_id, wave_id, batch_file, synset_count, status)
                VALUES (?, ?, ?, ?, 'pending')
                ON CONFLICT(sub_wave_id) DO UPDATE SET
                    batch_file = excluded.batch_file,
                    synset_count = excluded.synset_count
            """, (sub_id, wave_id, str(sub_batch), len(chunk)))

            # Tag synsets with sub_wave_id
            for sid in chunk:
                db.execute("UPDATE synset_waves SET sub_wave_id = ? WHERE synset_id = ?",
                           (sub_id, sid))

        db.commit()

        # Execute sub-waves sequentially
        db.execute("UPDATE waves SET status = 'executing', started_at = ? WHERE wave_id = ?",
                   (datetime.now(timezone.utc).isoformat(), wave_id))
        db.commit()

        for i in range(num_subs):
            sub_id = f"{wave_id}_sub{i}"
            sub_row = db.execute(
                "SELECT sub_wave_id, batch_file, status FROM sub_waves WHERE sub_wave_id = ?",
                (sub_id,)
            ).fetchone()

            if sub_row[2] == "done":
                print(f"  {sub_id}: already done, skipping")
                continue

            sub_batch = sub_row[1]
            print(f"\n  Executing sub-wave {sub_id} ({sub_row[1]})...")

            db.execute("UPDATE sub_waves SET status = 'executing', started_at = ? WHERE sub_wave_id = ?",
                       (datetime.now(timezone.utc).isoformat(), sub_id))
            db.commit()

            rc = _run_docker_batch(sub_batch, workers, args.resume)

            now = datetime.now(timezone.utc).isoformat()
            if rc == 0:
                db.execute("UPDATE sub_waves SET status = 'done', finished_at = ? WHERE sub_wave_id = ?",
                           (now, sub_id))
            else:
                db.execute("UPDATE sub_waves SET status = 'partial', finished_at = ? WHERE sub_wave_id = ?",
                           (now, sub_id))
                print(f"  {sub_id}: batch_runner exited with code {rc}")
                if not args.continue_on_error:
                    print("  Stopping. Use --continue-on-error to proceed to next sub-wave.")
                    db.commit()
                    break
            db.commit()

    else:
        # Run the whole wave as one batch
        print(f"Executing {wave_id}: {synset_count} synsets, {workers} workers")

        db.execute("UPDATE waves SET status = 'executing', started_at = ? WHERE wave_id = ?",
                   (datetime.now(timezone.utc).isoformat(), wave_id))
        db.commit()

        rc = _run_docker_batch(str(batch_path), workers, args.resume)

        now = datetime.now(timezone.utc).isoformat()
        if rc == 0:
            db.execute("UPDATE waves SET status = 'done', finished_at = ? WHERE wave_id = ?",
                       (now, wave_id))
        else:
            db.execute("UPDATE waves SET status = 'partial', finished_at = ? WHERE wave_id = ?",
                       (now, wave_id))
            print(f"batch_runner exited with code {rc}")

        db.commit()

    db.close()
    print(f"\nExecution finished for {wave_id}. Run 'sync' to update review counts.")


def _run_docker_batch(batch_file: str, workers: int, resume: bool) -> int:
    """Invoke docker/run_batch.sh and return its exit code.

    Args:
        batch_file: Path to the wave/sub-wave batch file (.txt with synset IDs)
        workers: Number of concurrent workers to pass to batch_runner.py
        resume: If True, passes --resume to batch_runner.py to retry failed synsets

    Returns:
        Exit code from docker/run_batch.sh (0 = all succeeded, 1 = some failed)
    """
    cmd = [str(DOCKER_RUN_BATCH), "--batch", batch_file, "--workers", str(workers)]
    if resume:
        cmd.append("--resume")
    result = subprocess.run(cmd)
    return result.returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AWN4 Noun Review — Wave Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s init                          Initialize campaign (first time)
  %(prog)s init --force                  Regenerate all wave batch files
  %(prog)s sync                          Scan disk, update campaign.db
  %(prog)s status                        Show progress dashboard
  %(prog)s prepare W2                    Prepare synsets for wave W2
  %(prog)s execute W2                    Execute wave W2 in Docker
  %(prog)s execute W2 --workers 4        Override worker count
  %(prog)s execute W4 --continue-on-error Continue past sub-wave failures
""",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CAMPAIGN_YAML,
                        help="Path to campaign.yaml")
    parser.add_argument("--db", type=Path, default=DEFAULT_CAMPAIGN_DB,
                        help="Path to campaign.db")

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize campaign: create DB and wave batch files")
    p_init.add_argument("--force", action="store_true",
                        help="Regenerate batch files even if they exist")

    # status
    sub.add_parser("status", help="Show campaign progress dashboard")

    # sync
    sub.add_parser("sync", help="Scan disk for reviews and update campaign.db")

    # prepare
    p_prep = sub.add_parser("prepare", help="Prepare synsets for a wave")
    p_prep.add_argument("wave_id", help="Wave ID (e.g. W2)")
    p_prep.add_argument("--force", action="store_true",
                        help="Overwrite existing prepared directories")

    # execute
    p_exec = sub.add_parser("execute", help="Execute review for a wave")
    p_exec.add_argument("wave_id", help="Wave ID (e.g. W2)")
    p_exec.add_argument("--workers", type=int, default=None,
                        help="Override worker count from campaign.yaml")
    p_exec.add_argument("--resume", action="store_true",
                        help="Resume interrupted batch_runner run")
    p_exec.add_argument("--continue-on-error", action="store_true",
                        help="Continue to next sub-wave if current one fails")

    args = parser.parse_args()

    {
        "init": cmd_init,
        "status": cmd_status,
        "sync": cmd_sync,
        "prepare": cmd_prepare,
        "execute": cmd_execute,
    }[args.command](args)


if __name__ == "__main__":
    main()
