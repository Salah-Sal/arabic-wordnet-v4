#!/usr/bin/env python3
"""AWN4 Unified Review Orchestrator.

Coordinates multiple review engines (Claude, Gemini) across BFS-depth waves,
manages quotas, prevents duplicate work, and auto-restarts on quota resets.

Parallel multi-model execution is achieved through three layers:
- Per-model SQLite DBs (BATCH_DB_NAME env var) — eliminates DB contention
  when multiple containers write to the same wave output directory
- In-flight synset tracking with fair-share partitioning — prevents assigning
  the same synsets to concurrently running containers
- JIT dedup in batch runners — catches residual race conditions where a
  parallel container completes a synset between batch assignment and processing

Each model's container receives isolated DB/summary filenames derived from
its ``id`` field (e.g., ``.batch_status.gemini-flash.db``), set automatically
by ContainerManager.launch via the BATCH_DB_NAME and BATCH_SUMMARY_NAME
environment variables.

Usage:
    python3 orchestrator.py status
    python3 orchestrator.py remaining [--wave W2] [--output /tmp/remaining.txt]
    python3 orchestrator.py start --models gemini-flash,claude-sonnet
    python3 orchestrator.py start --models gemini-flash --wave W3
    python3 orchestrator.py start --models gemini-flash --dry-run
    python3 orchestrator.py prepare --wave W3
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import json

import yaml

# ── Paths ──

GUIDE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = GUIDE_DIR / "orchestrator_config.yaml"
DB_PATH = GUIDE_DIR / "output" / "orchestrator.db"

# ── Logging ──

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# ── Config ──


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── SQLite ──


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wave_state (
            wave_id         TEXT PRIMARY KEY,
            total_synsets   INTEGER NOT NULL,
            reviewed        INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS model_state (
            model_id        TEXT PRIMARY KEY,
            status          TEXT NOT NULL DEFAULT 'idle',
            quota_resets_at TEXT,
            container_name  TEXT,
            total_reviewed  INTEGER DEFAULT 0,
            last_launched   TEXT
        );
        CREATE TABLE IF NOT EXISTS container_runs (
            run_id          TEXT PRIMARY KEY,
            model_id        TEXT NOT NULL,
            wave_id         TEXT NOT NULL,
            batch_file      TEXT NOT NULL,
            synset_count    INTEGER NOT NULL,
            started_at      TEXT NOT NULL,
            finished_at     TEXT,
            exit_code       INTEGER,
            new_reviews     INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'running'
        );
    """)
    conn.commit()
    return conn


# ── WaveManager ──


class WaveManager:
    """Reads wave files and determines which wave is active."""

    WAVE_IDS = ["W0", "W1", "W2", "W3", "W4", "W5", "W6"]

    def __init__(self, waves_dir: Path, prepared_dir: Path):
        self.waves_dir = waves_dir
        self.prepared_dir = prepared_dir
        self._wave_cache: dict[str, list[str]] = {}

    def read_wave_file(self, wave_id: str) -> list[str]:
        if wave_id in self._wave_cache:
            return self._wave_cache[wave_id]
        path = self.waves_dir / f"{wave_id}.txt"
        if not path.exists():
            logger.warning(f"Wave file not found: {path}")
            return []
        ids = [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self._wave_cache[wave_id] = ids
        return ids

    def all_wave_synsets(self) -> dict[str, list[str]]:
        return {wid: self.read_wave_file(wid) for wid in self.WAVE_IDS}

    def is_prepared(self, synset_id: str) -> bool:
        return (self.prepared_dir / synset_id / "synset_info.yaml").exists()

    def get_active_wave(
        self, completed: set[str], force_wave: Optional[str] = None
    ) -> tuple[Optional[str], list[str]]:
        """Return (wave_id, remaining_synset_ids) for the first incomplete wave."""
        wave_order = self.WAVE_IDS
        if force_wave:
            if force_wave not in self.WAVE_IDS:
                logger.error(f"Unknown wave: {force_wave}")
                return None, []
            idx = self.WAVE_IDS.index(force_wave)
            wave_order = self.WAVE_IDS[idx:]

        for wave_id in wave_order:
            wave_ids = self.read_wave_file(wave_id)
            remaining = [s for s in wave_ids if s not in completed]
            if remaining:
                ready = [s for s in remaining if self.is_prepared(s)]
                unprepared = len(remaining) - len(ready)
                if unprepared:
                    logger.warning(
                        f"[{wave_id}] {unprepared}/{len(remaining)} synsets need "
                        f"preparation. Run: python3 orchestrator.py prepare --wave {wave_id}"
                    )
                return wave_id, ready
        return None, []  # all done


# ── WorkQueue ──


class WorkQueue:
    """Scans wave subdirs + legacy dirs for completed reviews."""

    def __init__(
        self,
        output_root: Path,
        wave_ids: list[str],
        legacy_dirs: list[Path] | None = None,
    ):
        self.output_root = output_root
        self.wave_ids = wave_ids
        self.legacy_dirs = legacy_dirs or []
        self.completed: set[str] = set()
        self.refresh()

    def refresh(self):
        found: set[str] = set()
        # Scan wave subdirs: output/reviews/W0/, W1/, ...
        if self.output_root.exists():
            for wid in self.wave_ids:
                wave_dir = self.output_root / wid
                if not wave_dir.exists():
                    continue
                for f in wave_dir.iterdir():
                    if f.name.endswith(".review.yaml"):
                        found.add(f.name[: -len(".review.yaml")])
        # Scan legacy flat dirs
        for d in self.legacy_dirs:
            if not d.exists():
                continue
            for f in d.iterdir():
                if f.name.endswith(".review.yaml"):
                    found.add(f.name[: -len(".review.yaml")])
        self.completed = found
        logger.debug(
            f"Dedup scan: {len(self.completed)} unique reviews "
            f"(wave dirs + {len(self.legacy_dirs)} legacy dirs)"
        )

    def write_batch_file(
        self, synset_ids: list[str], model_id: str, run_id: str
    ) -> Path:
        """Write a batch file for a container launch. Returns the path."""
        batch_path = Path(tempfile.gettempdir()) / f"orch_{model_id}_{run_id}.txt"
        header = (
            f"# Orchestrator batch for {model_id}\n"
            f"# Run: {run_id}\n"
            f"# Generated: {datetime.now(timezone.utc).isoformat()}\n"
            f"# Synsets: {len(synset_ids)}\n"
            f"#\n"
        )
        batch_path.write_text(header + "\n".join(synset_ids) + "\n")
        return batch_path


# ── QuotaManager ──


class QuotaManager:
    """Probes Gemini quota availability via CLI."""

    # Pattern: "reset after 1h2m30s" or similar from TerminalQuotaError
    RESET_RE = re.compile(
        r"reset\s+(?:after\s+)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", re.IGNORECASE
    )
    QUOTA_ERROR_RE = re.compile(
        r"(TerminalQuotaError|quota|rate.?limit|RESOURCE_EXHAUSTED|429)", re.IGNORECASE
    )

    def __init__(self):
        self._reset_times: dict[str, datetime] = {}

    async def probe(self, model_cfg: dict) -> tuple[bool, Optional[float]]:
        """Probe quota for a free-tier model.

        Returns (available, reset_seconds_or_None).
        """
        if model_cfg.get("quota_type") == "paid":
            return True, None

        probe_cmd = model_cfg.get("quota_probe")
        if not probe_cmd:
            return True, None

        try:
            # Use isolated GEMINI_CLI_HOME to avoid interference
            env = os.environ.copy()
            probe_home = Path(tempfile.gettempdir()) / "orch_quota_probe"
            probe_home.mkdir(exist_ok=True)
            env["GEMINI_CLI_HOME"] = str(probe_home)

            proc = await asyncio.create_subprocess_shell(
                probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = (stdout or b"").decode() + (stderr or b"").decode()

            if self.QUOTA_ERROR_RE.search(output):
                reset_secs = self._parse_reset_time(output)
                model_id = model_cfg["id"]
                if reset_secs:
                    self._reset_times[model_id] = datetime.now(timezone.utc) + timedelta(
                        seconds=reset_secs
                    )
                return False, reset_secs

            return True, None

        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Quota probe failed for {model_cfg['id']}: {e}")
            return True, None  # assume available on probe failure

    def _parse_reset_time(self, output: str) -> Optional[float]:
        m = self.RESET_RE.search(output)
        if not m:
            return None
        h = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        s = int(m.group(3) or 0)
        return h * 3600 + mins * 60 + s

    def get_reset_time(self, model_id: str) -> Optional[datetime]:
        return self._reset_times.get(model_id)

    def clear_reset(self, model_id: str):
        self._reset_times.pop(model_id, None)


# ── ContainerManager ──


class ContainerManager:
    """Launches and monitors Docker containers via run_batch.sh."""

    def __init__(self, guide_dir: Path):
        self.guide_dir = guide_dir
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    def is_running(self, model_id: str) -> bool:
        proc = self._processes.get(model_id)
        return proc is not None and proc.returncode is None

    async def launch(
        self,
        model_cfg: dict,
        batch_file: Path,
        run_id: str,
        wave_output_dir: Path,
        on_exit: asyncio.Event | None = None,
    ) -> tuple[str, asyncio.subprocess.Process]:
        """Launch a container. Returns (run_id, process).

        wave_output_dir is exported as OUTPUT_DIR so run_batch.sh writes
        reviews into the correct wave subdirectory.

        Per-model env vars set automatically:
            BATCH_DB_NAME = ``.batch_status.<model_id>.db`` — isolates
                each model's SQLite status DB to prevent write contention
                when multiple containers share the same OUTPUT_DIR.
            BATCH_SUMMARY_NAME = ``.batch_summary.<model_id>.json`` —
                per-model summary file for orchestrator post-run parsing.
        """
        model_id = model_cfg["id"]
        run_batch = self.guide_dir / model_cfg["run_batch_sh"]
        workers = model_cfg.get("workers", 2)

        env = os.environ.copy()
        env["MODEL"] = model_cfg["model_env"]
        env["OUTPUT_DIR"] = str(wave_output_dir)
        # Per-model DB/summary filenames to avoid SQLite contention
        env["BATCH_DB_NAME"] = f".batch_status.{model_id}.db"
        env["BATCH_SUMMARY_NAME"] = f".batch_summary.{model_id}.json"

        cmd = [
            "bash",
            str(run_batch),
            "--batch",
            str(batch_file),
            "--workers",
            str(workers),
            "--adaptive",
        ]

        logger.info(
            f"[{model_id}] Launching container: {workers} workers, "
            f"{batch_file.name} → {wave_output_dir.name}"
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(self.guide_dir),
        )
        self._processes[model_id] = proc
        return run_id, proc

    def release(self, model_id: str):
        self._processes.pop(model_id, None)

    async def stop_all(self):
        """SIGTERM all running containers."""
        for model_id, proc in list(self._processes.items()):
            if proc.returncode is None:
                logger.info(f"[{model_id}] Sending SIGTERM to container (pid {proc.pid})")
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
        # Wait for all to exit (up to 15s)
        for model_id, proc in list(self._processes.items()):
            try:
                await asyncio.wait_for(proc.wait(), timeout=15)
            except asyncio.TimeoutError:
                logger.warning(f"[{model_id}] Force-killing container")
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

    AUTH_ERROR_RE = re.compile(
        r"(authentication_error|authentication_failed|401.*authentication|"
        r"OAuth\s+token.*expired|invalid.?api.?key|Unauthorized)", re.IGNORECASE)

    BATCH_SUMMARY_RE = re.compile(r"BATCH_EXIT_SUMMARY:(\{.*\})")

    def detect_quota_error(self, output: str) -> bool:
        """Check if container output indicates quota exhaustion."""
        return bool(QuotaManager.QUOTA_ERROR_RE.search(output))

    def detect_auth_error(self, output: str) -> bool:
        """Check if container output indicates an authentication failure."""
        return bool(self.AUTH_ERROR_RE.search(output))

    def parse_batch_summary(self, output: str) -> dict | None:
        """Parse BATCH_EXIT_SUMMARY JSON from container output."""
        m = self.BATCH_SUMMARY_RE.search(output)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
        return None


# ── ProgressDashboard ──


class ProgressDashboard:
    """Prints a unified status view."""

    def __init__(
        self,
        wave_mgr: WaveManager,
        work_queue: WorkQueue,
        config: dict,
        db: sqlite3.Connection,
    ):
        self.wave_mgr = wave_mgr
        self.work_queue = work_queue
        self.config = config
        self.db = db
        self.tree_size = config["campaign"]["tree_size"]
        self._start_time = time.monotonic()
        self._start_count = len(work_queue.completed)

    def render(
        self,
        active_wave: Optional[str],
        model_states: dict[str, dict],
    ) -> str:
        total_reviewed = len(self.work_queue.completed)
        overall_pct = total_reviewed / self.tree_size * 100 if self.tree_size else 0

        lines = []
        lines.append("")
        lines.append("━━━ AWN4 Review Orchestrator ━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Active wave info
        if active_wave:
            wave_ids = self.wave_mgr.read_wave_file(active_wave)
            wave_reviewed = sum(1 for s in wave_ids if s in self.work_queue.completed)
            wave_total = len(wave_ids)
            wave_pct = wave_reviewed / wave_total * 100 if wave_total else 0
            lines.append(
                f"Active wave: {active_wave}  |  "
                f"{wave_reviewed:,}/{wave_total:,} ({wave_pct:.1f}%)  |  "
                f"{wave_total - wave_reviewed:,} remaining"
            )
        else:
            lines.append("Active wave: ALL DONE")

        lines.append(
            f"Overall:               |  "
            f"{total_reviewed:,}/{self.tree_size:,} ({overall_pct:.1f}%)"
        )

        # Session rate
        elapsed_h = (time.monotonic() - self._start_time) / 3600
        session_new = total_reviewed - self._start_count
        if elapsed_h > 0.01:
            rate = session_new / elapsed_h
            lines.append(f"Session: +{session_new} reviews in {elapsed_h:.1f}h (~{rate:.0f}/hr)")

        lines.append("")
        lines.append(f" {'Model':<16} {'Status':<24} {'Reviews':>8}   Rate")

        for mcfg in self.config.get("models", []):
            mid = mcfg["id"]
            ms = model_states.get(mid, {})
            status = ms.get("status", "not selected")
            reviewed = ms.get("total_reviewed", 0)

            status_str = status
            if status == "auth_failed":
                status_str = "AUTH FAILED"
            elif status == "backoff":
                consec = ms.get("_consec_failures", 0)
                status_str = f"backoff (fail #{consec})"
            elif status == "quota_exhausted":
                reset_at = ms.get("quota_resets_at")
                if reset_at:
                    try:
                        rt = datetime.fromisoformat(reset_at)
                        remaining = rt - datetime.now(timezone.utc)
                        if remaining.total_seconds() > 0:
                            mins = int(remaining.total_seconds() / 60)
                            status_str = f"quota (resets in {mins}m)"
                        else:
                            status_str = "quota (reset due)"
                    except ValueError:
                        pass
            elif status == "running":
                w = mcfg.get("workers", 2)
                status_str = f"running ({w}w)"

            rate_str = "--"
            lines.append(f" {mid:<16} {status_str:<24} {reviewed:>8}   {rate_str}")

        # Wave progress bar
        lines.append("")
        wave_bar = " Waves: "
        for wid in WaveManager.WAVE_IDS:
            wids = self.wave_mgr.read_wave_file(wid)
            done_count = sum(1 for s in wids if s in self.work_queue.completed)
            total = len(wids)
            if total == 0:
                wave_bar += f" {wid} ?"
            elif done_count == total:
                wave_bar += f" {wid} \u25a0"
            elif done_count > 0:
                filled = int(done_count / total * 5)
                wave_bar += f" {wid} " + "\u2593" * filled + "\u2591" * (5 - filled)
            else:
                wave_bar += f" {wid} \u2591"
        lines.append(wave_bar)
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        return "\n".join(lines)


# ── Docker Image Builder ──


async def build_docker_images(guide_dir: Path, model_cfgs: list[dict]):
    """Build Docker images for selected pipelines (one-time, sequential)."""
    built: set[str] = set()
    for mcfg in model_cfgs:
        run_batch = guide_dir / mcfg["run_batch_sh"]
        docker_dir = run_batch.parent
        # Determine image name from run_batch.sh
        image_name = _image_name_from_script(run_batch)
        if image_name in built:
            continue

        # Check if image exists
        result = subprocess.run(
            ["docker", "image", "inspect", image_name],
            capture_output=True,
        )
        if result.returncode == 0:
            logger.info(f"Docker image '{image_name}' already exists")
            built.add(image_name)
            continue

        logger.info(f"Building Docker image '{image_name}' from {docker_dir}")
        proc = await asyncio.create_subprocess_exec(
            "docker", "build", "-t", image_name, str(docker_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            logger.error(
                f"Docker build failed for {image_name}:\n{stdout.decode()[-500:]}"
            )
            sys.exit(1)
        built.add(image_name)


def _image_name_from_script(run_batch: Path) -> str:
    """Extract IMAGE_NAME from run_batch.sh."""
    text = run_batch.read_text()
    m = re.search(r'IMAGE_NAME="([^"]+)"', text)
    if m:
        return m.group(1)
    # Fallback
    return "reviewer-" + run_batch.parent.parent.name


# ── Orchestrator ──


class Orchestrator:
    """Main orchestration loop."""

    def __init__(
        self,
        config: dict,
        selected_models: list[str],
        force_wave: Optional[str] = None,
        dry_run: bool = False,
    ):
        """Initialize the orchestrator.

        Sets up wave/work-queue/quota/container managers and per-model state.

        Key state:
            model_states: Per-model dict tracking status (idle/running/
                backoff/quota_exhausted/auth_failed), quota reset times,
                and cumulative review counts.
            _in_flight: ``{model_id: set(synset_ids)}`` — synsets currently
                assigned to a running container. Used by ``_schedule_once``
                to exclude already-assigned synsets when launching a new
                container for a different model.
            _consecutive_failures: Per-model failure counter driving
                exponential backoff (reset on success or quota events).

        Per-model env var scheme (set in ContainerManager.launch):
            BATCH_DB_NAME = ``.batch_status.<model_id>.db``
            BATCH_SUMMARY_NAME = ``.batch_summary.<model_id>.json``
        """
        self.config = config
        self.dry_run = dry_run
        self.force_wave = force_wave
        self.shutdown_event = asyncio.Event()
        self._sigint_count = 0

        # Resolve paths relative to GUIDE_DIR
        waves_dir = GUIDE_DIR / config["campaign"]["waves_dir"]
        prepared_dir = GUIDE_DIR / config["prepared_dir"]
        self.output_root = GUIDE_DIR / config["output_root"]
        legacy_dirs = [GUIDE_DIR / d for d in config.get("legacy_output_dirs", [])]

        self.wave_mgr = WaveManager(waves_dir, prepared_dir)
        self.work_queue = WorkQueue(
            self.output_root, WaveManager.WAVE_IDS, legacy_dirs
        )
        self.quota_mgr = QuotaManager()
        self.container_mgr = ContainerManager(GUIDE_DIR)
        self.db = init_db()

        # Filter to selected models
        all_models = {m["id"]: m for m in config.get("models", [])}
        self.model_cfgs: list[dict] = []
        for mid in selected_models:
            if mid not in all_models:
                logger.error(f"Unknown model: {mid}. Available: {list(all_models.keys())}")
                sys.exit(1)
            self.model_cfgs.append(all_models[mid])

        # Track model state in-memory
        self.model_states: dict[str, dict] = {}
        for mcfg in self.model_cfgs:
            self.model_states[mcfg["id"]] = {
                "status": "idle",
                "quota_resets_at": None,
                "total_reviewed": 0,
            }

        # In-flight synset tracking: model_id → set of synset IDs currently
        # assigned to its running container (enables parallel execution)
        self._in_flight: dict[str, set[str]] = {}

        # Failure tracking for backoff logic
        self._consecutive_failures: dict[str, int] = {}
        self._last_failure_class: dict[str, str] = {}

        # Circuit breaker config
        cb_cfg = config.get("circuit_breaker", {})
        self._max_backoff_s = cb_cfg.get("max_backoff_s", 1800)

        self.dashboard = ProgressDashboard(
            self.wave_mgr, self.work_queue, config, self.db
        )

    def _setup_signals(self, loop: asyncio.AbstractEventLoop):
        def handle_sigint():
            self._sigint_count += 1
            if self._sigint_count == 1:
                logger.info("SIGINT received — shutting down gracefully...")
                self.shutdown_event.set()
            else:
                logger.warning("Second SIGINT — force exit")
                os._exit(1)

        loop.add_signal_handler(signal.SIGINT, handle_sigint)
        loop.add_signal_handler(signal.SIGTERM, handle_sigint)

    async def run(self):
        loop = asyncio.get_running_loop()
        self._setup_signals(loop)

        # Build Docker images
        if not self.dry_run:
            await build_docker_images(GUIDE_DIR, self.model_cfgs)

        # Initial scan
        self.work_queue.refresh()
        active_wave, remaining = self.wave_mgr.get_active_wave(
            self.work_queue.completed, self.force_wave
        )

        if not active_wave:
            logger.info("All waves complete!")
            return

        logger.info(
            f"Active wave: {active_wave} | "
            f"{len(remaining)} synsets remaining | "
            f"{len(self.work_queue.completed)} total reviewed"
        )

        if self.dry_run:
            self._print_dry_run(active_wave, remaining)
            return

        # Start background tasks
        tasks = [
            asyncio.create_task(self._progress_loop()),
            asyncio.create_task(self._dedup_loop()),
            asyncio.create_task(self._scheduling_loop()),
        ]

        # Add quota polling for free-tier models
        free_models = [m for m in self.model_cfgs if m.get("quota_type") == "free"]
        if free_models:
            tasks.append(asyncio.create_task(self._quota_poll_loop(free_models)))

        # Wait until shutdown
        await self.shutdown_event.wait()

        # Cleanup
        logger.info("Stopping all containers...")
        await self.container_mgr.stop_all()

        for t in tasks:
            t.cancel()

        # Final status
        self.work_queue.refresh()
        active_wave, remaining = self.wave_mgr.get_active_wave(
            self.work_queue.completed, self.force_wave
        )
        print(
            self.dashboard.render(active_wave, self.model_states)
        )
        logger.info("Orchestrator shutdown complete.")

    def _print_dry_run(self, active_wave: str, remaining: list[str]):
        wave_output_dir = self.output_root / active_wave
        print(f"\n--- DRY RUN ---")
        print(f"Active wave: {active_wave}")
        print(f"Output dir:  {wave_output_dir}")
        print(f"Remaining synsets: {len(remaining)}")
        print(f"Selected models:")
        for mcfg in self.model_cfgs:
            mid = mcfg["id"]
            print(f"  {mid}: {mcfg['run_batch_sh']} ({mcfg['workers']}w)")
        print(f"\nWould launch containers for {len(remaining)} synsets.")
        print(f"Batch files would be written to /tmp/orch_<model>_<run_id>.txt")

    async def _scheduling_loop(self):
        """Main scheduling loop — runs every 30s."""
        while not self.shutdown_event.is_set():
            try:
                await self._schedule_once()
            except Exception:
                logger.exception("Scheduling error")
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=30
                )
                return  # shutdown requested
            except asyncio.TimeoutError:
                pass

    async def _schedule_once(self):
        """Run one scheduling pass for all selected models.

        Decision tree per model:
        1. Skip if container already running for this model
        2. Skip if auth_failed (permanent until manual restart)
        3. Skip if in backoff (exponential delay not yet elapsed)
        4. Skip/retry if quota_exhausted (probe again after reset time)
        5. Exclude synsets currently in-flight by other models' containers
        6. Fair-share partition: if other models are idle, take only a
           proportional share of available synsets so they get work too
        7. Launch container with per-model DB/summary env vars
        """
        # Refresh completed set
        self.work_queue.refresh()

        active_wave, remaining = self.wave_mgr.get_active_wave(
            self.work_queue.completed, self.force_wave
        )

        if not active_wave:
            logger.info("All waves complete!")
            self.shutdown_event.set()
            return

        # Check for wave transition
        self._update_wave_db(active_wave)

        if not remaining:
            logger.info(f"Wave {active_wave} has no ready synsets (unprepared?)")
            return

        # Compute per-wave output dir
        wave_output_dir = self.output_root / active_wave
        wave_output_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)

        all_exhausted = True
        for mcfg in self.model_cfgs:
            mid = mcfg["id"]
            ms = self.model_states[mid]

            # Skip if already running
            if self.container_mgr.is_running(mid):
                all_exhausted = False
                continue

            # Auth failed — permanently stopped until manual restart
            if ms["status"] == "auth_failed":
                continue

            # Backoff — wait for exponential delay to elapse
            if ms["status"] == "backoff":
                consec = self._consecutive_failures.get(mid, 0)
                backoff_s = min(60 * (2 ** max(consec - 1, 0)), self._max_backoff_s)
                last_launched = ms.get("last_launched")
                if last_launched:
                    try:
                        last_dt = datetime.fromisoformat(last_launched)
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        elapsed = (now - last_dt).total_seconds()
                        if elapsed < backoff_s:
                            remaining_s = backoff_s - elapsed
                            logger.debug(
                                f"[{mid}] Backoff: {remaining_s:.0f}s remaining "
                                f"(fail #{consec}, delay {backoff_s}s)"
                            )
                            continue
                    except ValueError:
                        pass
                ms["status"] = "idle"  # backoff elapsed, retry
                logger.info(f"[{mid}] Backoff elapsed, retrying")

            # Handle quota exhaustion
            if ms["status"] == "quota_exhausted":
                reset_at = self.quota_mgr.get_reset_time(mid)
                if reset_at and datetime.now(timezone.utc) < reset_at:
                    continue  # still waiting

                # Reset time reached — probe again
                available, reset_secs = await self.quota_mgr.probe(mcfg)
                if not available:
                    if reset_secs:
                        logger.info(
                            f"[{mid}] Quota still exhausted, resets in {reset_secs:.0f}s"
                        )
                    continue

                logger.info(f"[{mid}] Quota available again!")
                ms["status"] = "idle"
                self.quota_mgr.clear_reset(mid)

            # Exclude synsets currently assigned to other running containers
            in_flight = set()
            for other_mid, sids in self._in_flight.items():
                if other_mid != mid and self.container_mgr.is_running(other_mid):
                    in_flight |= sids
            available = [s for s in remaining if s not in in_flight]

            if not available:
                logger.debug(f"[{mid}] No available synsets (all in-flight by other models)")
                all_exhausted = False
                continue

            # Fair-share: if other idle models may also need synsets,
            # only take a proportional share so they get work too
            other_idle = sum(
                1 for m in self.model_cfgs
                if m["id"] != mid
                and not self.container_mgr.is_running(m["id"])
                and self.model_states[m["id"]]["status"] not in ("auth_failed",)
            )
            if other_idle > 0:
                pool_size = len(available)
                share = max(1, pool_size // (other_idle + 1))
                available = available[:share]
                logger.info(
                    f"[{mid}] Fair-share: taking {share}/{pool_size} "
                    f"synsets ({other_idle} other idle model(s))"
                )

            # Launch container
            run_id = str(uuid.uuid4())[:8]
            self._in_flight[mid] = set(available)
            batch_file = self.work_queue.write_batch_file(available, mid, run_id)

            ms["status"] = "running"
            ms["last_launched"] = datetime.now(timezone.utc).isoformat()
            all_exhausted = False

            # Record in DB
            self.db.execute(
                "INSERT OR REPLACE INTO container_runs "
                "(run_id, model_id, wave_id, batch_file, synset_count, started_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'running')",
                (run_id, mid, active_wave, str(batch_file), len(available),
                 datetime.now(timezone.utc).isoformat()),
            )
            self.db.commit()

            # Launch and monitor in background
            _, proc = await self.container_mgr.launch(
                mcfg, batch_file, run_id, wave_output_dir
            )
            asyncio.create_task(
                self._monitor_container(
                    mcfg, proc, run_id, active_wave, batch_file, wave_output_dir
                )
            )

        if all_exhausted and not any(
            self.container_mgr.is_running(m["id"]) for m in self.model_cfgs
        ):
            # All models exhausted, find nearest reset
            nearest = None
            for mcfg in self.model_cfgs:
                rt = self.quota_mgr.get_reset_time(mcfg["id"])
                if rt and (nearest is None or rt < nearest):
                    nearest = rt
            if nearest:
                wait_mins = max(0, (nearest - datetime.now(timezone.utc)).total_seconds() / 60)
                logger.info(
                    f"All models quota-exhausted. Nearest reset in {wait_mins:.0f}m. Polling..."
                )

    async def _monitor_container(
        self,
        model_cfg: dict,
        proc: asyncio.subprocess.Process,
        run_id: str,
        wave_id: str,
        batch_file: Path,
        wave_output_dir: Path | None = None,
    ):
        """Monitor a container process until it exits."""
        mid = model_cfg["id"]

        try:
            stdout, stderr = await proc.communicate()
            exit_code = proc.returncode
            output_text = (stdout or b"").decode(errors="replace") + \
                          (stderr or b"").decode(errors="replace")
        except Exception as e:
            logger.error(f"[{mid}] Container monitoring error: {e}")
            exit_code = -1
            output_text = str(e)

        # Count new reviews
        self.work_queue.refresh()
        ms = self.model_states[mid]

        # Parse structured batch summary (all batch runners emit this)
        batch_summary = self.container_mgr.parse_batch_summary(output_text)

        # Detect auth error (highest priority — unrecoverable)
        is_auth = self.container_mgr.detect_auth_error(output_text)
        if batch_summary and batch_summary.get("circuit_breaker_reason", ""):
            reason = batch_summary["circuit_breaker_reason"]
            if reason.startswith("AUTH_ERROR"):
                is_auth = True

        # Detect quota error
        is_quota = self.container_mgr.detect_quota_error(output_text)

        if is_auth:
            # Auth failure — permanently stop this model
            ms["status"] = "auth_failed"
            status = "auth_failed"
            self._consecutive_failures[mid] = 0
            logger.error(
                f"[{mid}] AUTH FAILURE detected (exit {exit_code}). "
                f"Model disabled until manual restart. Check credentials/tokens."
            )
        elif is_quota:
            ms["status"] = "quota_exhausted"
            status = "quota_exhausted"
            self._consecutive_failures[mid] = 0
            logger.warning(f"[{mid}] Container hit quota limit (exit {exit_code})")
            # Probe for reset time
            _, reset_secs = await self.quota_mgr.probe(model_cfg)
            if reset_secs:
                reset_at = datetime.now(timezone.utc) + timedelta(seconds=reset_secs)
                ms["quota_resets_at"] = reset_at.isoformat()
                logger.info(f"[{mid}] Quota resets at {reset_at.strftime('%H:%M UTC')}")
        elif exit_code == 0:
            # Check for catastrophic failure rate (exit 0 but >=95% failed)
            if batch_summary and batch_summary.get("failure_rate", 0) >= 0.95:
                consec = self._consecutive_failures.get(mid, 0) + 1
                self._consecutive_failures[mid] = consec
                ms["status"] = "backoff"
                ms["last_launched"] = datetime.now(timezone.utc).isoformat()
                ms["_consec_failures"] = consec
                status = "failed_high_rate"
                logger.warning(
                    f"[{mid}] Container exited 0 but {batch_summary['failure_rate']:.0%} failure rate. "
                    f"Backoff #{consec}."
                )
            else:
                ms["status"] = "idle"
                status = "completed"
                self._consecutive_failures[mid] = 0
                logger.info(f"[{mid}] Container completed successfully")
        elif batch_summary and batch_summary.get("circuit_breaker_tripped"):
            # Non-zero exit with circuit breaker tripped — backoff
            consec = self._consecutive_failures.get(mid, 0) + 1
            self._consecutive_failures[mid] = consec
            ms["status"] = "backoff"
            ms["last_launched"] = datetime.now(timezone.utc).isoformat()
            ms["_consec_failures"] = consec
            status = "circuit_breaker"
            reason = batch_summary.get("circuit_breaker_reason", "unknown")
            logger.warning(
                f"[{mid}] Circuit breaker tripped: {reason}. Backoff #{consec}."
            )
        else:
            # Normal non-zero exit — some synsets failed, retry remaining
            ms["status"] = "idle"
            status = "failed"
            last_lines = output_text.strip().split("\n")[-5:]
            logger.warning(
                f"[{mid}] Container failed (exit {exit_code}):\n  "
                + "\n  ".join(last_lines)
            )

        # Update DB
        self.db.execute(
            "UPDATE container_runs SET finished_at=?, exit_code=?, status=? "
            "WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), exit_code, status, run_id),
        )
        self.db.commit()

        # Release resources
        self._in_flight.pop(mid, None)
        self.container_mgr.release(mid)

        # Cleanup batch file
        try:
            batch_file.unlink(missing_ok=True)
        except OSError:
            pass

    async def _progress_loop(self):
        """Print dashboard periodically."""
        interval = self.config.get("polling", {}).get("progress_interval_s", 60)
        while not self.shutdown_event.is_set():
            try:
                self.work_queue.refresh()
                active_wave, _ = self.wave_mgr.get_active_wave(
                    self.work_queue.completed, self.force_wave
                )
                print(self.dashboard.render(active_wave, self.model_states))
            except Exception:
                logger.exception("Dashboard error")
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=interval
                )
                return
            except asyncio.TimeoutError:
                pass

    async def _dedup_loop(self):
        """Refresh completed set periodically."""
        interval = self.config.get("polling", {}).get("dedup_scan_interval_s", 120)
        while not self.shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=interval
                )
                return
            except asyncio.TimeoutError:
                self.work_queue.refresh()

    async def _quota_poll_loop(self, free_models: list[dict]):
        """Periodically probe quotas for free-tier models."""
        interval = self.config.get("polling", {}).get("quota_check_interval_s", 300)
        while not self.shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=interval
                )
                return
            except asyncio.TimeoutError:
                pass

            for mcfg in free_models:
                mid = mcfg["id"]
                if self.model_states[mid]["status"] == "quota_exhausted":
                    available, reset_secs = await self.quota_mgr.probe(mcfg)
                    if available:
                        logger.info(f"[{mid}] Quota restored!")
                        self.model_states[mid]["status"] = "idle"
                        self.quota_mgr.clear_reset(mid)

    def _update_wave_db(self, active_wave: str):
        """Update wave_state table."""
        for wid in WaveManager.WAVE_IDS:
            wave_ids = self.wave_mgr.read_wave_file(wid)
            reviewed = sum(1 for s in wave_ids if s in self.work_queue.completed)
            total = len(wave_ids)
            if reviewed == total and total > 0:
                status = "done"
            elif wid == active_wave:
                status = "active"
            else:
                status = "pending"

            self.db.execute(
                "INSERT OR REPLACE INTO wave_state (wave_id, total_synsets, reviewed, status) "
                "VALUES (?, ?, ?, ?)",
                (wid, total, reviewed, status),
            )
        self.db.commit()


# ── CLI Commands ──


def cmd_status(config: dict):
    """Print current status (one-shot, no containers)."""
    waves_dir = GUIDE_DIR / config["campaign"]["waves_dir"]
    prepared_dir = GUIDE_DIR / config["prepared_dir"]
    output_root = GUIDE_DIR / config["output_root"]
    legacy_dirs = [GUIDE_DIR / d for d in config.get("legacy_output_dirs", [])]
    tree_size = config["campaign"]["tree_size"]

    wave_mgr = WaveManager(waves_dir, prepared_dir)
    work_queue = WorkQueue(output_root, WaveManager.WAVE_IDS, legacy_dirs)

    # Per-directory counts
    print("\n━━━ AWN4 Review Status ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("\nWave directories:")
    for wid in WaveManager.WAVE_IDS:
        wdir = output_root / wid
        if wdir.exists():
            count = sum(1 for f in wdir.iterdir() if f.name.endswith(".review.yaml"))
            print(f"  {wid}: {count}")
    if legacy_dirs:
        print("\nLegacy directories:")
        for d in legacy_dirs:
            if d.exists():
                count = sum(1 for f in d.iterdir() if f.name.endswith(".review.yaml"))
                print(f"  {d.name}: {count}")
            else:
                print(f"  {d.name}: (not found)")

    total = len(work_queue.completed)
    pct = total / tree_size * 100 if tree_size else 0
    print(f"\nUnique reviewed: {total:,}/{tree_size:,} ({pct:.1f}%)")

    # Per-wave breakdown
    print(f"\n{'Wave':<6} {'Total':>7} {'Done':>7} {'Remain':>7} {'Prepared':>9}  Status")
    print("-" * 55)
    for wid in WaveManager.WAVE_IDS:
        wids = wave_mgr.read_wave_file(wid)
        done = sum(1 for s in wids if s in work_queue.completed)
        remaining = len(wids) - done
        prepared = sum(1 for s in wids if wave_mgr.is_prepared(s))
        if done == len(wids) and len(wids) > 0:
            status = "done"
        elif done > 0:
            status = "active"
        else:
            status = "pending"
        print(
            f"{wid:<6} {len(wids):>7,} {done:>7,} {remaining:>7,} "
            f"{prepared:>7,}    {status}"
        )

    # Active wave
    active, remaining = wave_mgr.get_active_wave(work_queue.completed)
    if active:
        print(f"\nNext work: {active} ({len(remaining)} ready synsets)")
    else:
        print("\nAll waves complete!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


def cmd_remaining(config: dict, wave: Optional[str], output_file: Optional[str]):
    """Show or export remaining synsets."""
    waves_dir = GUIDE_DIR / config["campaign"]["waves_dir"]
    prepared_dir = GUIDE_DIR / config["prepared_dir"]
    output_root = GUIDE_DIR / config["output_root"]
    legacy_dirs = [GUIDE_DIR / d for d in config.get("legacy_output_dirs", [])]

    wave_mgr = WaveManager(waves_dir, prepared_dir)
    work_queue = WorkQueue(output_root, WaveManager.WAVE_IDS, legacy_dirs)

    if wave:
        target_wave = wave
    else:
        target_wave, _ = wave_mgr.get_active_wave(work_queue.completed)
        if not target_wave:
            print("All waves complete.")
            return

    wave_ids = wave_mgr.read_wave_file(target_wave)
    remaining = [s for s in wave_ids if s not in work_queue.completed]
    prepared = [s for s in remaining if wave_mgr.is_prepared(s)]
    unprepared = [s for s in remaining if not wave_mgr.is_prepared(s)]

    print(f"\n{target_wave}: {len(remaining)} remaining ({len(prepared)} prepared, {len(unprepared)} unprepared)")

    if output_file:
        Path(output_file).write_text("\n".join(remaining) + "\n")
        print(f"Written to {output_file}")
    else:
        if len(remaining) <= 20:
            for s in remaining:
                prep = "ready" if wave_mgr.is_prepared(s) else "NEEDS PREP"
                print(f"  {s}  [{prep}]")
        else:
            print(f"  (use --output <file> to export full list)")


def cmd_prepare(config: dict, wave: str):
    """Run extract_synset_info.py for a wave's synsets."""
    waves_dir = GUIDE_DIR / config["campaign"]["waves_dir"]
    prepared_dir = GUIDE_DIR / config["prepared_dir"]
    wave_file = waves_dir / f"{wave}.txt"

    if not wave_file.exists():
        print(f"Error: wave file not found: {wave_file}")
        sys.exit(1)

    extract_script = GUIDE_DIR / "review_pipeline" / "extract_synset_info.py"
    if not extract_script.exists():
        print(f"Error: extract_synset_info.py not found at {extract_script}")
        sys.exit(1)

    cmd = [
        sys.executable,
        str(extract_script),
        "--batch", str(wave_file),
        "--output-dir", str(prepared_dir),
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def cmd_start(
    config: dict,
    models: list[str],
    wave: Optional[str],
    dry_run: bool,
):
    """Start the orchestrator."""
    orch = Orchestrator(config, models, force_wave=wave, dry_run=dry_run)
    asyncio.run(orch.run())


# ── Main ──


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show current progress (no containers launched)")

    # remaining
    p_rem = sub.add_parser("remaining", help="Show remaining synsets for a wave")
    p_rem.add_argument("--wave", type=str, default=None, help="Wave ID (default: active)")
    p_rem.add_argument("--output", type=str, default=None, help="Write to file")

    # start
    p_start = sub.add_parser("start", help="Start the orchestrator")
    p_start.add_argument(
        "--models", type=str, required=True,
        help="Comma-separated model IDs (e.g., gemini-flash,claude-sonnet)",
    )
    p_start.add_argument("--wave", type=str, default=None, help="Start from this wave")
    p_start.add_argument("--dry-run", action="store_true", help="Show plan without launching")

    # prepare
    p_prep = sub.add_parser("prepare", help="Prepare synsets for a wave")
    p_prep.add_argument("--wave", type=str, required=True, help="Wave ID (e.g., W3)")

    args = parser.parse_args()

    config = load_config()

    if args.command == "status":
        cmd_status(config)
    elif args.command == "remaining":
        cmd_remaining(config, args.wave, args.output)
    elif args.command == "start":
        cmd_start(config, args.models.split(","), args.wave, args.dry_run)
    elif args.command == "prepare":
        cmd_prepare(config, args.wave)


if __name__ == "__main__":
    main()
