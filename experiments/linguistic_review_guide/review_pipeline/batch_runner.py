#!/usr/bin/env python3
"""Concurrent batch runner for AWN4 linguistic review pipeline.

Orchestrates parallel run_review.sh invocations with:
- Adaptive concurrency (AIMD) or fixed semaphore limiting (up to 50 workers)
- SQLite WAL-mode status DB for resumption
- Exponential backoff retries
- SIGINT/SIGTERM graceful shutdown
- Progress reporting with tree %, throughput, ETA

Usage:
    python3 batch_runner.py awn4-02592253-n awn4-06731387-n --workers 4
    python3 batch_runner.py --all --workers 8
    python3 batch_runner.py --batch synset_list.txt --workers 10 --adaptive
    python3 batch_runner.py --resume --workers 4
"""

import argparse
import asyncio
import collections
import dataclasses
import json
import logging
import os
import re
import signal
import sys
import time
import uuid
from pathlib import Path

# batch_status.py lives alongside this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_status import BatchStatusDB

LOG_FMT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATEFMT = "%H:%M:%S"
logger = logging.getLogger("batch_runner")

MAX_WORKERS = 50
BACKOFF_DELAYS = [10, 30, 90]  # seconds between retries

RATE_LIMIT_PATTERNS = [
    "rate limit", "rate_limit", "ratelimit", "429", "529",
    "too many requests", "overloaded", "capacity",
]

AUTH_ERROR_PATTERNS = [
    "authentication_error", "authentication_failed",
    "401", "oauth token", "token expired", "token has expired",
    "invalid api key", "invalid_api_key", "unauthorized",
    "api key not valid", "credentials",
]

# Max cooldown cap to avoid blocking on stale/incorrect resetsAt timestamps
MAX_COOLDOWN_SECONDS = 3600  # 1 hour


class ErrorClassifier:
    """Classifies subprocess failures into actionable categories."""

    @staticmethod
    def classify(combined_text: str, is_rate_limited: bool, exit_code: int) -> str:
        low = combined_text.lower()
        if any(p in low for p in AUTH_ERROR_PATTERNS):
            return "auth"
        if is_rate_limited:
            return "rate_limit"
        if exit_code == -9:
            return "timeout"
        return "unknown"


class CircuitBreaker:
    """Stops a batch on repeated same-class failures.

    Auth errors trip immediately. Other error classes trip after
    `threshold` consecutive failures of the same type.
    """

    def __init__(self, threshold: int, shutdown_event: asyncio.Event):
        self._threshold = threshold
        self._shutdown_event = shutdown_event
        self._consecutive: dict[str, int] = {}
        self._trip_reason: str | None = None
        self._lock = asyncio.Lock()

    @property
    def tripped(self) -> bool:
        return self._trip_reason is not None

    @property
    def trip_reason(self) -> str | None:
        return self._trip_reason

    async def record_success(self):
        async with self._lock:
            self._consecutive.clear()

    async def record_failure(self, error_class: str) -> bool:
        async with self._lock:
            if error_class == "auth":
                self._trip_reason = f"AUTH_ERROR:{error_class}"
                self._shutdown_event.set()
                return True
            for cls in list(self._consecutive):
                if cls != error_class:
                    self._consecutive[cls] = 0
            self._consecutive[error_class] = self._consecutive.get(error_class, 0) + 1
            if self._consecutive[error_class] >= self._threshold:
                self._trip_reason = f"CONSECUTIVE:{error_class}:{self._consecutive[error_class]}"
                self._shutdown_event.set()
                return True
            return False


@dataclasses.dataclass
class TrajectoryInfo:
    """Structured info extracted from a trajectory JSONL file."""
    rate_limited: bool = False
    resets_at: float | None = None        # Unix epoch (from resetsAt)
    rate_limit_type: str | None = None    # e.g., "five_hour"
    utilization: float | None = None      # 0.0-1.0 (from allowed_warning)
    error_message: str | None = None
    cost: float = 0.0


class GlobalCooldown:
    """Coordinates a cluster-wide pause when any worker hits a rate limit.

    When set, all workers that try to acquire the semaphore will first
    await the cooldown expiry. This prevents N-1 workers from blindly
    hitting the same rate limit while one worker has already been rejected.
    """

    def __init__(self):
        self._resets_at: float = 0.0  # time.time() epoch
        self._lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        return time.time() < self._resets_at

    @property
    def remaining(self) -> float:
        return max(0.0, self._resets_at - time.time())

    async def set_cooldown(self, resets_at: float | None, fallback_seconds: float = 60.0):
        """Set a cooldown. Uses resets_at (epoch) if available, else fallback."""
        async with self._lock:
            if resets_at is not None:
                new_reset = min(resets_at, time.time() + MAX_COOLDOWN_SECONDS)
            else:
                new_reset = time.time() + fallback_seconds
            # Only extend, never shorten an active cooldown
            if new_reset > self._resets_at:
                self._resets_at = new_reset
                remaining = self._resets_at - time.time()
                logger.warning(
                    f"[cooldown] Global rate-limit pause: {remaining:.0f}s "
                    f"until {time.strftime('%H:%M:%S', time.localtime(self._resets_at))}"
                )

    async def wait_if_active(self):
        """Block until the cooldown expires. No-op if not active."""
        remaining = self.remaining
        if remaining > 0:
            logger.info(f"[cooldown] Waiting {remaining:.0f}s for rate-limit cooldown...")
            await asyncio.sleep(remaining)


class AdaptiveSemaphore:
    """asyncio.Semaphore with a dynamically adjustable limit.

    set_limit(n) changes the ceiling without killing in-flight tasks.
    When shrinking, _value may go negative — in-flight tasks drain naturally
    and new acquires block until capacity is available.
    """

    def __init__(self, value: int):
        self._limit = value
        self._value = value
        self._waiters: collections.deque = collections.deque()

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def active(self) -> int:
        return self._limit - self._value

    def set_limit(self, new_limit: int) -> None:
        new_limit = max(1, min(new_limit, MAX_WORKERS))
        delta = new_limit - self._limit
        self._limit = new_limit
        self._value += delta
        # Wake waiters for newly available slots; each woken acquire()
        # will decrement _value itself, so we only wake min(_value, waiters).
        to_wake = max(0, self._value)
        while to_wake > 0 and self._waiters:
            fut = self._waiters.popleft()
            if not fut.done():
                fut.set_result(None)
                to_wake -= 1

    async def acquire(self) -> None:
        while self._value <= 0:
            fut = asyncio.get_running_loop().create_future()
            self._waiters.append(fut)
            try:
                await fut
            except asyncio.CancelledError:
                try:
                    self._waiters.remove(fut)
                except ValueError:
                    pass
                raise
        self._value -= 1

    def release(self) -> None:
        self._value += 1
        # Wake one waiter; it will decrement _value in acquire().
        while self._waiters:
            fut = self._waiters.popleft()
            if not fut.done():
                fut.set_result(None)
                return

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()


class ConcurrencyController:
    """AIMD concurrency tuner for an AdaptiveSemaphore.

    Additive Increase: +1 worker after `streak_threshold` consecutive successes.
    Multiplicative Decrease: halve workers on rate-limit detection.
    """

    def __init__(self, semaphore: AdaptiveSemaphore, streak_threshold: int = 5):
        self.sem = semaphore
        self.streak_threshold = streak_threshold
        self._streak = 0

    @property
    def streak(self) -> int:
        return self._streak

    def on_success(self) -> None:
        self._streak += 1
        if self._streak >= self.streak_threshold:
            old = self.sem.limit
            new = min(old + 1, MAX_WORKERS)
            if new != old:
                self.sem.set_limit(new)
                logger.info(f"[concurrency] +1 worker: {old}→{new} (streak={self._streak})")
            self._streak = 0

    def on_rate_limit(self) -> None:
        self._streak = 0
        old = self.sem.limit
        new = max(old // 2, 1)
        self.sem.set_limit(new)
        logger.warning(f"[concurrency] rate-limit → halved: {old}→{new}")

    def on_failure(self) -> None:
        self._streak = 0

    @staticmethod
    def is_rate_limited(text: str) -> bool:
        low = text.lower()
        return any(p in low for p in RATE_LIMIT_PATTERNS)


def _parse_tree_size(batch_path: Path) -> int | None:
    """Parse '# ... Tree: N' from batch file header."""
    try:
        with open(batch_path) as f:
            for line in f:
                if not line.startswith("#"):
                    break
                m = re.search(r"Tree:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        pass
    return None


class BatchRunner:
    """Orchestrates concurrent synset reviews via run_review.sh subprocesses."""

    def __init__(
        self,
        synset_ids: list[str],
        workers: int = 4,
        max_retries: int = 2,
        timeout_minutes: int = 30,
        run_id: str | None = None,
        model: str | None = None,
        resume_items: list[tuple[str, int]] | None = None,
        adaptive: bool = False,
        tree_size: int | None = None,
        circuit_breaker_threshold: int = 5,
    ):
        self.synset_ids = synset_ids
        self.workers = min(workers, MAX_WORKERS)
        self.max_retries = max_retries
        self.timeout_s = timeout_minutes * 60
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.model = model or os.environ.get("MODEL", "sonnet")
        self.resume_items = resume_items  # [(synset_id, last_attempt)] from --resume
        self.tree_size = tree_size  # total noun synsets for % display

        # Paths (same env vars as run_review.sh)
        self.script_dir = Path(__file__).resolve().parent
        self.run_review_sh = self.script_dir / "run_review.sh"
        guide_dir = self.script_dir.parent
        self.output_dir = Path(
            os.environ.get("OUTPUT_DIR", str(guide_dir / "output" / "reviews_pipeline_v2"))
        )
        self.prepared_dir = Path(
            os.environ.get("PREPARED_DIR", str(self.script_dir / "prepared"))
        )

        # Status DB
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db = BatchStatusDB(self.output_dir / ".batch_status.db")

        # Concurrency control (adaptive AIMD or static semaphore)
        if adaptive:
            self.semaphore = AdaptiveSemaphore(self.workers)
            self.controller = ConcurrencyController(self.semaphore)
        else:
            self.semaphore = asyncio.Semaphore(self.workers)
            self.controller = None
        self.cooldown = GlobalCooldown()  # global rate-limit pause (always active)
        self.shutdown_event = asyncio.Event()
        self.circuit_breaker = CircuitBreaker(
            threshold=circuit_breaker_threshold, shutdown_event=self.shutdown_event
        )
        self.active_procs: dict[str, asyncio.subprocess.Process] = {}
        self._start_time = None  # set in run()

    async def run(self) -> int:
        """Main entry point. Returns 0 if all succeeded, 1 if any failed."""
        self._setup_signals()
        self._start_time = time.monotonic()

        # Initialize run in status DB
        self.db.create_run(self.run_id, len(self.synset_ids), self.workers, self.model)
        self.db.init_synsets(self.run_id, self.synset_ids)

        # Build work queue: (synset_id, start_attempt)
        work_queue = self._build_work_queue()

        total = len(self.synset_ids)
        skipped = total - len(work_queue)
        logger.info(
            f"Run {self.run_id}: {len(work_queue)} to process, {skipped} skipped, "
            f"{self.workers} workers, model={self.model}"
        )

        if not work_queue:
            logger.info("Nothing to do — all synsets already reviewed.")
            self.db.finish_run(self.run_id, "completed")
            return 0

        # Progress reporter (background task)
        progress_task = asyncio.create_task(self._progress_reporter())

        # Launch all reviews — semaphore limits actual concurrency
        tasks = [
            asyncio.create_task(self._process_synset(sid, start_attempt))
            for sid, start_attempt in work_queue
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass

        # Finalize
        if self.circuit_breaker.tripped:
            status = "circuit_breaker"
        elif self.shutdown_event.is_set():
            status = "interrupted"
        else:
            status = "completed"
        self.db.finish_run(self.run_id, status)
        self._print_summary()

        # Structured summary for orchestrator parsing
        stats = self.db.get_stats(self.run_id)
        total = stats["success"] + stats["failed"]
        summary = {
            "success": stats["success"],
            "failed": stats["failed"],
            "failure_rate": round(stats["failed"] / total, 4) if total > 0 else 0.0,
            "circuit_breaker_tripped": self.circuit_breaker.tripped,
            "circuit_breaker_reason": self.circuit_breaker.trip_reason,
        }
        print(f"BATCH_EXIT_SUMMARY:{json.dumps(summary)}")

        return 0 if stats["failed"] == 0 else 1

    def _build_work_queue(self) -> list[tuple[str, int]]:
        """Determine which synsets need processing and at what attempt number."""
        # Resume mode: use the resume_items directly
        if self.resume_items is not None:
            for sid, _ in self.resume_items:
                # Reset status to pending for re-processing
                self.db.conn.execute(
                    "UPDATE synset_status SET status = 'pending' "
                    "WHERE synset_id = ? AND run_id = ? AND status IN ('failed', 'running')",
                    (sid, self.run_id),
                )
            self.db.conn.commit()
            return self.resume_items

        queue = []
        for sid in self.synset_ids:
            review_path = self.output_dir / f"{sid}.review.yaml"
            if review_path.exists():
                self.db.mark_skipped(sid, self.run_id)
                continue
            queue.append((sid, 0))
        return queue

    async def _process_synset(self, synset_id: str, start_attempt: int) -> None:
        """Process one synset with retry logic."""
        for attempt in range(start_attempt, self.max_retries + 1):
            if self.shutdown_event.is_set():
                return

            # Backoff on retries
            if attempt > start_attempt:
                delay = BACKOFF_DELAYS[min(attempt - 1, len(BACKOFF_DELAYS) - 1)]
                logger.info(f"[{synset_id}] Retry {attempt}/{self.max_retries} in {delay}s")
                await asyncio.sleep(delay)
                if self.shutdown_event.is_set():
                    return

            # Wait for global cooldown BEFORE acquiring semaphore slot
            await self.cooldown.wait_if_active()
            async with self.semaphore:
                if self.shutdown_event.is_set():
                    return
                # Re-check after acquiring (another worker may have set cooldown)
                await self.cooldown.wait_if_active()
                ok = await self._run_single(synset_id, attempt)
                if ok:
                    return

        logger.error(f"[{synset_id}] Exhausted {self.max_retries + 1} attempts")

    async def _run_single(self, synset_id: str, attempt: int) -> bool:
        """Execute run_review.sh for one synset. Returns True on success."""
        self.db.mark_running(synset_id, self.run_id, attempt)
        t0 = time.monotonic()

        env = {**os.environ, "MODEL": self.model}
        # Let run_review.sh inherit OUTPUT_DIR, PREPARED_DIR, etc. from our env

        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", str(self.run_review_sh), synset_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            self.active_procs[synset_id] = proc

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_s
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{synset_id}] Timeout ({self.timeout_s}s), killing")
                proc.kill()
                await proc.wait()
                dur = time.monotonic() - t0
                self.db.mark_failed(synset_id, self.run_id, -9, f"Timeout after {self.timeout_s}s", dur)
                return False
            finally:
                self.active_procs.pop(synset_id, None)

            dur = time.monotonic() - t0
            rc = proc.returncode

            review_path = self.output_dir / f"{synset_id}.review.yaml"
            if rc == 0 and review_path.exists():
                traj_info = self._parse_trajectory(synset_id)
                self.db.mark_success(synset_id, self.run_id, traj_info.cost, dur)
                logger.info(f"[{synset_id}] OK {dur:.0f}s ${traj_info.cost:.2f}")
                # Warn if approaching rate limit (proactive early warning)
                if traj_info.utilization and traj_info.utilization > 0.95:
                    logger.warning(
                        f"[{synset_id}] Rate limit utilization {traj_info.utilization:.0%} "
                        f"— approaching limit (type={traj_info.rate_limit_type})"
                    )
                await self.circuit_breaker.record_success()
                if self.controller:
                    self.controller.on_success()
                return True

            # Capture error from both stdout and stderr (run_review.sh prints
            # errors to stdout via echo, not stderr)
            out_text = stdout.decode("utf-8", errors="replace")[-1000:] if stdout else ""
            err_text = stderr.decode("utf-8", errors="replace")[-500:] if stderr else ""
            combined = out_text + err_text

            if rc == 0 and not review_path.exists():
                err_msg = "Claude completed but no review file written"
            else:
                # Prefer stdout (where run_review.sh echo errors go), fall back to stderr
                err_msg = out_text.strip() or err_text.strip() or f"exit code {rc}"
            self.db.mark_failed(synset_id, self.run_id, rc or 2, err_msg, dur)
            logger.warning(f"[{synset_id}] FAIL exit={rc} {dur:.0f}s | {err_msg[:200]}")

            # Rate limit detection: prefer trajectory, fall back to text matching
            traj_info = self._parse_trajectory(synset_id)
            is_rl = traj_info.rate_limited or ConcurrencyController.is_rate_limited(combined)

            # Circuit breaker: classify and record
            error_class = ErrorClassifier.classify(combined, is_rl, rc)
            tripped = await self.circuit_breaker.record_failure(error_class)
            if tripped:
                logger.error(f"[{synset_id}] Circuit breaker tripped: {self.circuit_breaker.trip_reason}")
                return False

            if is_rl:
                if traj_info.rate_limited:
                    logger.warning(
                        f"[{synset_id}] Rate limit from trajectory: "
                        f"type={traj_info.rate_limit_type}, resets_at={traj_info.resets_at}"
                    )
                # Global cooldown: always active (not gated by --adaptive)
                await self.cooldown.set_cooldown(
                    resets_at=traj_info.resets_at,
                    fallback_seconds=60.0,
                )
                if self.controller:
                    self.controller.on_rate_limit()
            elif self.controller:
                self.controller.on_failure()
            return False

        except Exception as e:
            dur = time.monotonic() - t0
            self.db.mark_failed(synset_id, self.run_id, -1, str(e), dur)
            logger.error(f"[{synset_id}] Exception: {e}")
            if self.controller:
                self.controller.on_failure()
            return False

    def _parse_trajectory(self, synset_id: str) -> TrajectoryInfo:
        """Parse trajectory JSONL for cost, rate-limit events, and errors.

        Claude CLI stream-json emits:
        - rate_limit_event: {rate_limit_info: {status, resetsAt, rateLimitType, utilization}}
        - result: {total_cost_usd, is_error, subtype, stop_reason}
        """
        info = TrajectoryInfo()
        traj = self.output_dir / f"{synset_id}.trajectory.jsonl"
        if not traj.exists():
            return info
        try:
            with open(traj) as f:
                for line in f:
                    try:
                        if '"rate_limit_event"' in line:
                            obj = json.loads(line)
                            if obj.get("type") != "rate_limit_event":
                                continue
                            rli = obj.get("rate_limit_info", {})
                            status = rli.get("status")
                            if status == "rejected":
                                info.rate_limited = True
                                info.resets_at = rli.get("resetsAt")
                                info.rate_limit_type = rli.get("rateLimitType")
                            elif status == "allowed_warning":
                                info.utilization = rli.get("utilization")
                                info.rate_limit_type = rli.get("rateLimitType")
                                info.resets_at = rli.get("resetsAt")
                        elif '"type":"result"' in line or '"type": "result"' in line:
                            obj = json.loads(line)
                            info.cost = float(obj.get("total_cost_usd", 0))
                            if obj.get("is_error"):
                                info.error_message = obj.get("result", "")[:500]
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            pass
        return info

    def _extract_cost(self, synset_id: str) -> float:
        """Parse total_cost_usd from the trajectory JSONL's result event."""
        return self._parse_trajectory(synset_id).cost

    # ── Signal handling ──

    def _setup_signals(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._on_signal, sig)

    def _on_signal(self, sig):
        name = signal.Signals(sig).name
        n = len(self.active_procs)
        logger.warning(f"{name} received — stopping new launches, {n} reviews still active")
        self.shutdown_event.set()
        # Restore default handler so second signal force-exits
        asyncio.get_running_loop().remove_signal_handler(sig)

    # ── Progress ──

    async def _progress_reporter(self):
        try:
            while True:
                await asyncio.sleep(30)
                stats = self.db.get_stats(self.run_id)
                active = sorted(self.active_procs.keys())
                names = ", ".join(active[:3])
                if len(active) > 3:
                    names += f" +{len(active) - 3}"

                done = stats["success"] + stats["skipped"]
                total = len(self.synset_ids)
                batch_pct = done / total * 100 if total else 0

                # Throughput and ETA
                elapsed_s = time.monotonic() - self._start_time if self._start_time else 0
                elapsed_h = elapsed_s / 3600
                rate_hr = stats["success"] / elapsed_h if elapsed_h > 0.01 else 0
                remaining = stats["pending"] + len(active)
                eta_h = remaining / rate_hr if rate_hr > 0 else 0

                # Tree coverage (if tree_size known from batch file header)
                tree_str = ""
                if self.tree_size:
                    tree_pct = done / self.tree_size * 100
                    tree_str = f" tree={tree_pct:.2f}% |"

                # Adaptive concurrency state
                if self.controller:
                    sem = self.semaphore
                    workers_str = f"workers={sem.active}/{sem.limit}"
                else:
                    workers_str = f"workers={len(active)}/{self.workers}"

                # Cooldown status
                cd_str = ""
                cd_remaining = self.cooldown.remaining
                if cd_remaining > 0:
                    cd_str = f" | cooldown={cd_remaining:.0f}s"

                logger.info(
                    f"Progress: {done}/{total} ({batch_pct:.1f}%) |{tree_str} "
                    f"ok={stats['success']} fail={stats['failed']} pend={stats['pending']} | "
                    f"{workers_str}{cd_str} | {rate_hr:.0f}/hr | "
                    f"ETA: {eta_h:.1f}h | [{names}]"
                )
        except asyncio.CancelledError:
            pass

    def _print_summary(self):
        stats = self.db.get_stats(self.run_id)
        done = stats["success"] + stats["skipped"]
        elapsed_s = time.monotonic() - self._start_time if self._start_time else 0
        elapsed_h = elapsed_s / 3600

        logger.info("=" * 60)
        logger.info(f"Run {self.run_id} — {'INTERRUPTED' if self.shutdown_event.is_set() else 'COMPLETE'}")
        logger.info(f"  Success:  {stats['success']}")
        logger.info(f"  Failed:   {stats['failed']}")
        logger.info(f"  Skipped:  {stats['skipped']}")
        logger.info(f"  Pending:  {stats['pending']}")
        logger.info(f"  Cost:     ${stats['total_cost']:.2f}")
        logger.info(f"  Duration: {elapsed_h:.1f}h")
        if self.tree_size:
            tree_pct = done / self.tree_size * 100
            logger.info(f"  Tree:     {done}/{self.tree_size} ({tree_pct:.2f}%)")
        logger.info(f"  Status DB: {self.db.db_path}")
        if stats["failed"] > 0:
            resume_flags = "--adaptive " if self.controller else ""
            logger.info(f"  Resume:   python3 {__file__} --resume {resume_flags}--workers {self.workers}")
        logger.info("=" * 60)


# ── CLI ──

def collect_synsets(args, prepared_dir: Path) -> list[str]:
    """Resolve synset IDs from CLI arguments."""
    if args.batch:
        return [
            line.strip()
            for line in args.batch.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    if args.all:
        if not prepared_dir.is_dir():
            logger.error(f"Prepared dir not found: {prepared_dir}")
            sys.exit(1)
        return sorted(d.name for d in prepared_dir.iterdir() if d.is_dir())
    if args.synset_ids:
        return args.synset_ids
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Concurrent batch runner for AWN4 linguistic review.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s awn4-02592253-n --workers 1           Single synset
  %(prog)s --all --workers 8                      All prepared synsets
  %(prog)s --batch synset_list.txt --workers 10   From file
  %(prog)s --resume --workers 4                   Resume interrupted run
  %(prog)s --all --dry-run                        Preview without processing
""",
    )
    parser.add_argument("synset_ids", nargs="*", help="Synset ID(s) to process")
    parser.add_argument("--all", action="store_true", help="Process all prepared synsets")
    parser.add_argument("--batch", type=Path, help="File with synset IDs (one per line)")
    parser.add_argument("--workers", type=int, default=4, help="Max concurrent workers (default: 4, max: 50)")
    parser.add_argument("--max-retries", type=int, default=2, help="Max retries per synset (default: 2)")
    parser.add_argument("--timeout", type=int, default=30, help="Per-synset timeout in minutes (default: 30)")
    parser.add_argument("--resume", action="store_true", help="Resume most recent interrupted run")
    parser.add_argument("--run-id", type=str, help="Resume a specific run by ID")
    parser.add_argument("--dry-run", action="store_true", help="List synsets that would be processed")
    parser.add_argument("--model", type=str, default=None, help="Claude model override")
    parser.add_argument("--adaptive", action="store_true", help="Enable AIMD adaptive concurrency scaling")
    parser.add_argument("--tree-size", type=int, default=None, help="Total tree size for progress %% display")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DATEFMT)

    script_dir = Path(__file__).resolve().parent
    guide_dir = script_dir.parent
    prepared_dir = Path(os.environ.get("PREPARED_DIR", str(script_dir / "prepared")))
    output_dir = Path(os.environ.get("OUTPUT_DIR", str(guide_dir / "output" / "reviews_pipeline_v2")))

    # Handle --resume
    run_id = args.run_id
    resume_items = None
    if args.resume or args.run_id:
        output_dir.mkdir(parents=True, exist_ok=True)
        db = BatchStatusDB(output_dir / ".batch_status.db")
        rid = args.run_id or db.get_latest_run_id()
        if not rid:
            logger.error("No previous run found. Start a new run without --resume.")
            sys.exit(1)
        items = db.get_resumable_synsets(rid)
        if not items:
            logger.info(f"Run {rid}: nothing to resume — all synsets completed or skipped.")
            sys.exit(0)
        run_id = rid
        resume_items = items
        synset_ids = [sid for sid, _ in items]
        logger.info(f"Resuming run {rid}: {len(items)} synsets to retry")
        db.close()
    else:
        synset_ids = collect_synsets(args, prepared_dir)
        if not synset_ids:
            parser.print_help()
            sys.exit(1)

    # Dry run
    if args.dry_run:
        print(f"Would process {len(synset_ids)} synsets with {args.workers} workers:")
        for sid in synset_ids:
            review = output_dir / f"{sid}.review.yaml"
            status = "SKIP (exists)" if review.exists() else "PROCESS"
            print(f"  {status}: {sid}")
        already = sum(1 for s in synset_ids if (output_dir / f"{s}.review.yaml").exists())
        print(f"\nTotal: {len(synset_ids)} | To process: {len(synset_ids) - already} | Already done: {already}")
        sys.exit(0)

    # Auto-detect tree size from batch file header if not explicitly provided
    tree_size = args.tree_size
    if tree_size is None and args.batch:
        tree_size = _parse_tree_size(args.batch)

    runner = BatchRunner(
        synset_ids=synset_ids,
        workers=args.workers,
        max_retries=args.max_retries,
        timeout_minutes=args.timeout,
        run_id=run_id,
        model=args.model,
        resume_items=resume_items,
        adaptive=args.adaptive,
        tree_size=tree_size,
    )
    sys.exit(asyncio.run(runner.run()))


if __name__ == "__main__":
    main()
