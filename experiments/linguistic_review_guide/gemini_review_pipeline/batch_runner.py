#!/usr/bin/env python3
"""Concurrent batch runner for AWN4 linguistic review pipeline (Gemini CLI).

Orchestrates parallel run_review.sh invocations with:
- Adaptive concurrency (AIMD) or fixed semaphore limiting (up to 50 workers)
- SQLite WAL-mode status DB for resumption
- Exponential backoff retries
- SIGINT/SIGTERM graceful shutdown
- Progress reporting with tree %, throughput, ETA
- Model fallback chain (flash → pro → stop)
- JIT dedup (skips synsets completed by parallel containers)
- Per-model DB/summary isolation via BATCH_DB_NAME/BATCH_SUMMARY_NAME env vars
- BATCH_EXIT_SUMMARY stdout line for orchestrator integration

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
    "quota exceeded", "RESOURCE_EXHAUSTED", "quotaExceeded",
]

# Max cooldown cap to avoid blocking on stale/incorrect timestamps
MAX_COOLDOWN_SECONDS = 3600  # 1 hour

# Gemini model fallback chain: flash → pro → stop
MODEL_FALLBACK_CHAIN = [
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
]

# Aliases for CLI convenience
MODEL_ALIASES = {
    "flash": "gemini-3-flash-preview",
    "pro": "gemini-3.1-pro-preview",
}


@dataclasses.dataclass
class TrajectoryInfo:
    """Structured info extracted from a trajectory JSONL file."""
    rate_limited: bool = False
    resets_at: float | None = None        # Unix epoch (if available)
    rate_limit_type: str | None = None
    utilization: float | None = None
    error_message: str | None = None
    cost: float = 0.0


class ModelFallbackChain:
    """Manages per-model cooldowns and automatic fallback across Gemini models.

    When the current model is rate-limited, workers automatically switch to
    the next model in the chain. When all models are exhausted, signals
    a shutdown event so the batch stops cleanly.

    Also acts as a global cooldown — workers wait for the current model's
    cooldown before acquiring semaphore slots.
    """

    def __init__(self, primary_model: str, chain: list[str],
                 shutdown_event: asyncio.Event):
        # Reorder chain so primary_model is tried first
        if primary_model in chain:
            reordered = [primary_model] + [m for m in chain if m != primary_model]
            self._chain = reordered
        else:
            self._chain = [primary_model] + chain
        self._cooldowns: dict[str, float] = {}  # model → resets_at epoch
        self._lock = asyncio.Lock()
        self._shutdown_event = shutdown_event

    @property
    def active_model(self) -> str | None:
        """Return the first model whose cooldown has expired, or None if all exhausted."""
        now = time.time()
        for model in self._chain:
            if self._cooldowns.get(model, 0) <= now:
                return model
        return None

    @property
    def all_rate_limited(self) -> bool:
        now = time.time()
        return all(self._cooldowns.get(m, 0) > now for m in self._chain)

    def cooldown_remaining(self, model: str | None = None) -> float:
        """Remaining cooldown seconds for a model (default: active or first)."""
        target = model or self.active_model or self._chain[0]
        return max(0.0, self._cooldowns.get(target, 0) - time.time())

    def status_str(self) -> str:
        """Short status string for progress reporter."""
        now = time.time()
        parts = []
        for m in self._chain:
            short = m.replace("gemini-", "").replace("-preview", "")
            cd = self._cooldowns.get(m, 0) - now
            if cd > 0:
                parts.append(f"{short}:limited({cd:.0f}s)")
            elif m == self.active_model:
                parts.append(f"{short}:active")
            else:
                parts.append(f"{short}:ready")
        return " ".join(parts)

    async def mark_rate_limited(self, model: str,
                                resets_at: float | None,
                                fallback_seconds: float = 60.0):
        """Mark a model as rate-limited and potentially fall back to the next."""
        async with self._lock:
            if resets_at is not None:
                new_reset = min(resets_at, time.time() + MAX_COOLDOWN_SECONDS)
            else:
                new_reset = time.time() + fallback_seconds

            old_reset = self._cooldowns.get(model, 0)
            if new_reset > old_reset:
                self._cooldowns[model] = new_reset
                remaining = new_reset - time.time()
                short = model.replace("gemini-", "").replace("-preview", "")
                logger.warning(
                    f"[fallback] {short} rate-limited for {remaining:.0f}s "
                    f"until {time.strftime('%H:%M:%S', time.localtime(new_reset))}"
                )

            # Check if there's a fallback model available
            fallback = self.active_model
            if fallback and fallback != model:
                short_fb = fallback.replace("gemini-", "").replace("-preview", "")
                logger.warning(f"[fallback] Switching to {short_fb}")
            elif self.all_rate_limited:
                # Find the earliest cooldown expiry across all models
                earliest = min(self._cooldowns.get(m, 0) for m in self._chain)
                wait_s = earliest - time.time()
                if wait_s > 300:  # > 5 minutes: stop the batch
                    logger.error(
                        f"[fallback] All models rate-limited, earliest reset in "
                        f"{wait_s:.0f}s — stopping batch"
                    )
                    self._shutdown_event.set()
                else:
                    logger.warning(
                        f"[fallback] All models rate-limited, waiting {wait_s:.0f}s "
                        f"for earliest reset"
                    )

    async def wait_if_limited(self):
        """Block until the active model is available. No-op if one is ready."""
        while True:
            model = self.active_model
            if model is not None:
                return
            if self._shutdown_event.is_set():
                return
            # Wait for the earliest cooldown to expire
            now = time.time()
            earliest = min(self._cooldowns.get(m, 0) for m in self._chain)
            wait_s = max(0.1, earliest - now)
            logger.info(f"[fallback] All models limited, waiting {wait_s:.0f}s...")
            await asyncio.sleep(min(wait_s, 30))  # re-check every 30s max


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
    ):
        """Initialize the batch runner.

        Environment variable overrides (set by the orchestrator when running
        inside Docker, ignored in standalone mode):
            OUTPUT_DIR: Review output directory. Default for standalone use
                is ``output/reviews_gemini_pipeline_v2``; the orchestrator
                overrides this per-wave (e.g., ``output/reviews/W2``).
            BATCH_DB_NAME: SQLite status DB filename (default: ``.batch_status.db``).
                The orchestrator sets a per-model name to avoid contention.
            BATCH_SUMMARY_NAME: JSON summary filename (default:
                ``.batch_summary.json``). Per-model when orchestrated.
        """
        self.synset_ids = synset_ids
        self.workers = min(workers, MAX_WORKERS)
        self.max_retries = max_retries
        self.timeout_s = timeout_minutes * 60
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.model = model or os.environ.get("MODEL", "gemini-3-flash-preview")
        self.resume_items = resume_items  # [(synset_id, last_attempt)] from --resume
        self.tree_size = tree_size  # total noun synsets for % display

        # Paths (same env vars as run_review.sh)
        self.script_dir = Path(__file__).resolve().parent
        self.run_review_sh = self.script_dir / "run_review.sh"
        guide_dir = self.script_dir.parent
        # Standalone default; the orchestrator overrides OUTPUT_DIR per-wave
        self.output_dir = Path(
            os.environ.get("OUTPUT_DIR", str(guide_dir / "output" / "reviews_gemini_pipeline_v2"))
        )
        self.prepared_dir = Path(
            os.environ.get("PREPARED_DIR", str(self.script_dir / "prepared"))
        )

        # Status DB
        self.output_dir.mkdir(parents=True, exist_ok=True)
        db_name = os.environ.get("BATCH_DB_NAME", ".batch_status.db")
        self.db = BatchStatusDB(self.output_dir / db_name)

        # Concurrency control (adaptive AIMD or static semaphore)
        if adaptive:
            self.semaphore = AdaptiveSemaphore(self.workers)
            self.controller = ConcurrencyController(self.semaphore)
        else:
            self.semaphore = asyncio.Semaphore(self.workers)
            self.controller = None
        self.shutdown_event = asyncio.Event()
        self.fallback = ModelFallbackChain(
            primary_model=self.model,
            chain=MODEL_FALLBACK_CHAIN,
            shutdown_event=self.shutdown_event,
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
        chain_str = " → ".join(
            m.replace("gemini-", "").replace("-preview", "")
            for m in self.fallback._chain
        )
        logger.info(
            f"Run {self.run_id}: {len(work_queue)} to process, {skipped} skipped, "
            f"{self.workers} workers, model chain: {chain_str}"
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
        status = "interrupted" if self.shutdown_event.is_set() else "completed"
        self.db.finish_run(self.run_id, status)
        self._print_summary()
        self._export_summary_json()

        # Structured summary for orchestrator parsing
        stats = self.db.get_stats(self.run_id)
        total = stats["success"] + stats["failed"]
        summary = {
            "success": stats["success"],
            "failed": stats["failed"],
            "failure_rate": round(stats["failed"] / total, 4) if total > 0 else 0.0,
            "circuit_breaker_tripped": False,
            "circuit_breaker_reason": None,
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

            # Wait for a model to be available BEFORE acquiring semaphore slot
            await self.fallback.wait_if_limited()
            async with self.semaphore:
                if self.shutdown_event.is_set():
                    return
                # Re-check after acquiring (another worker may have triggered fallback)
                await self.fallback.wait_if_limited()
                ok = await self._run_single(synset_id, attempt)
                if ok:
                    return

        logger.error(f"[{synset_id}] Exhausted {self.max_retries + 1} attempts")

    async def _run_single(self, synset_id: str, attempt: int) -> bool:
        """Execute run_review.sh for one synset. Returns True on success."""
        # JIT dedup: another container may have completed this synset
        review_path = self.output_dir / f"{synset_id}.review.yaml"
        if review_path.exists():
            self.db.mark_skipped(synset_id, self.run_id)
            logger.info(f"[{synset_id}] Already reviewed (JIT dedup), skipping")
            return True
        self.db.mark_running(synset_id, self.run_id, attempt)
        t0 = time.monotonic()

        # Pick the active model from the fallback chain
        active_model = self.fallback.active_model or self.model
        env = {**os.environ, "MODEL": active_model}
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
            model_short = active_model.replace("gemini-", "").replace("-preview", "")
            if rc == 0 and review_path.exists():
                traj_info = self._parse_trajectory(synset_id)
                self.db.mark_success(synset_id, self.run_id, traj_info.cost, dur)
                logger.info(f"[{synset_id}] OK {dur:.0f}s ~${traj_info.cost:.4f} ({model_short})")
                if self.controller:
                    self.controller.on_success()
                return True

            # Capture error from both stdout and stderr (run_review.sh prints
            # errors to stdout via echo, not stderr)
            out_text = stdout.decode("utf-8", errors="replace")[-1000:] if stdout else ""
            err_text = stderr.decode("utf-8", errors="replace")[-500:] if stderr else ""
            combined = out_text + err_text

            if rc == 0 and not review_path.exists():
                err_msg = "Gemini completed but no review file written"
            else:
                # Prefer stdout (where run_review.sh echo errors go), fall back to stderr
                err_msg = out_text.strip() or err_text.strip() or f"exit code {rc}"
            self.db.mark_failed(synset_id, self.run_id, rc or 2, err_msg, dur)
            logger.warning(f"[{synset_id}] FAIL exit={rc} {dur:.0f}s ({model_short}) | {err_msg[:200]}")

            # Rate limit detection: prefer trajectory, fall back to text matching
            traj_info = self._parse_trajectory(synset_id)
            is_rl = traj_info.rate_limited or ConcurrencyController.is_rate_limited(combined)

            if is_rl:
                if traj_info.rate_limited:
                    logger.warning(
                        f"[{synset_id}] Rate limit on {model_short}: {traj_info.error_message}"
                    )
                # Mark THIS model as rate-limited; chain handles fallback/stop
                await self.fallback.mark_rate_limited(
                    model=active_model,
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
        """Parse trajectory JSONL for cost and rate-limit errors.

        Gemini CLI stream-json emits result events with:
        - status: "success" | "error"
        - stats: {input_tokens, output_tokens}
        Rate limit errors appear as status="error" with RESOURCE_EXHAUSTED
        or quota-related messages in the result or error fields.
        """
        info = TrajectoryInfo()
        traj = self.output_dir / f"{synset_id}.trajectory.jsonl"
        if not traj.exists():
            return info
        try:
            with open(traj) as f:
                for line in f:
                    try:
                        if '"type":"result"' not in line and '"type": "result"' not in line:
                            continue
                        obj = json.loads(line)
                        # Cost extraction from token counts
                        stats = obj.get("stats", {})
                        input_t = stats.get("input_tokens", 0)
                        output_t = stats.get("output_tokens", 0)
                        input_price = float(os.environ.get("INPUT_PRICE_PER_M", "1.25"))
                        output_price = float(os.environ.get("OUTPUT_PRICE_PER_M", "10.00"))
                        info.cost = (input_t * input_price + output_t * output_price) / 1_000_000
                        # Error / rate-limit detection
                        status = obj.get("status", "")
                        if status == "error":
                            error_text = str(obj.get("error", obj.get("result", "")))
                            info.error_message = error_text[:500]
                            if ConcurrencyController.is_rate_limited(error_text):
                                info.rate_limited = True
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            pass
        return info

    def _extract_cost(self, synset_id: str) -> float:
        """Estimate cost from Gemini trajectory token counts."""
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

                # Model fallback status
                model_str = f" | {self.fallback.status_str()}"

                logger.info(
                    f"Progress: {done}/{total} ({batch_pct:.1f}%) |{tree_str} "
                    f"ok={stats['success']} fail={stats['failed']} pend={stats['pending']} | "
                    f"{workers_str}{model_str} | {rate_hr:.0f}/hr | "
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
        logger.info(f"  Cost:     ~${stats['total_cost']:.4f} (estimated)")
        logger.info(f"  Duration: {elapsed_h:.1f}h")
        if self.tree_size:
            tree_pct = done / self.tree_size * 100
            logger.info(f"  Tree:     {done}/{self.tree_size} ({tree_pct:.2f}%)")
        logger.info(f"  Status DB: {self.db.db_path}")
        if stats["failed"] > 0:
            resume_flags = "--adaptive " if self.controller else ""
            logger.info(f"  Resume:   python3 {__file__} --resume {resume_flags}--workers {self.workers}")
        logger.info("=" * 60)

    def _export_summary_json(self):
        """Write .batch_summary.json for host-side tools to read safely."""
        stats = self.db.get_stats(self.run_id)
        from datetime import datetime, timezone
        summary_data = {
            "run_id": self.run_id,
            "model": self.model,
            "success": stats["success"],
            "failed": stats["failed"],
            "skipped": stats["skipped"],
            "pending": stats["pending"],
            "total_cost": stats["total_cost"],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        summary_name = os.environ.get("BATCH_SUMMARY_NAME", ".batch_summary.json")
        summary_path = self.output_dir / summary_name
        tmp = summary_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(summary_data, indent=2))
            tmp.rename(summary_path)
        except OSError as e:
            logger.warning(f"Failed to write batch summary JSON: {e}")


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
        description="Concurrent batch runner for AWN4 linguistic review (Gemini CLI).",
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
    parser.add_argument(
        "--model", type=str, default=None,
        help="Gemini model override (default: gemini-3-flash-preview, aliases: flash/pro)"
    )
    parser.add_argument("--adaptive", action="store_true", help="Enable AIMD adaptive concurrency scaling")
    parser.add_argument("--tree-size", type=int, default=None, help="Total tree size for progress %% display")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DATEFMT)

    script_dir = Path(__file__).resolve().parent
    guide_dir = script_dir.parent
    prepared_dir = Path(os.environ.get("PREPARED_DIR", str(script_dir / "prepared")))
    output_dir = Path(os.environ.get("OUTPUT_DIR", str(guide_dir / "output" / "reviews_gemini_pipeline_v2")))

    # Handle --resume
    run_id = args.run_id
    resume_items = None
    if args.resume or args.run_id:
        output_dir.mkdir(parents=True, exist_ok=True)
        db_name = os.environ.get("BATCH_DB_NAME", ".batch_status.db")
        db = BatchStatusDB(output_dir / db_name)
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

    # Resolve model aliases (flash → gemini-3-flash-preview, etc.)
    model = args.model
    if model and model in MODEL_ALIASES:
        model = MODEL_ALIASES[model]

    runner = BatchRunner(
        synset_ids=synset_ids,
        workers=args.workers,
        max_retries=args.max_retries,
        timeout_minutes=args.timeout,
        run_id=run_id,
        model=model,
        resume_items=resume_items,
        adaptive=args.adaptive,
        tree_size=tree_size,
    )
    sys.exit(asyncio.run(runner.run()))


if __name__ == "__main__":
    main()
