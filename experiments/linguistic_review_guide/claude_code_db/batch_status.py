#!/usr/bin/env python3
"""SQLite WAL-mode status database for batch review tracking.

Tracks per-synset review status across concurrent workers and batch runs,
enabling resumption of interrupted runs and progress monitoring.

Usage:
    from batch_status import BatchStatusDB
    db = BatchStatusDB(Path("output/.batch_status.db"))
    db.create_run("abc123", total_synsets=50, workers=4, model="sonnet")
    db.init_synsets("abc123", ["awn4-001-n", "awn4-002-n", ...])
    db.mark_running("awn4-001-n", "abc123", attempt=0)
    db.mark_success("awn4-001-n", "abc123", cost_usd=1.53, duration_s=703.0)
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """\
CREATE TABLE IF NOT EXISTS batch_runs (
    run_id         TEXT PRIMARY KEY,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    total_synsets  INTEGER NOT NULL,
    workers        INTEGER NOT NULL,
    model          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'running',
    total_cost_usd REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS synset_status (
    synset_id      TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    attempt        INTEGER NOT NULL DEFAULT 0,
    started_at     TEXT,
    finished_at    TEXT,
    cost_usd       REAL,
    exit_code      INTEGER,
    error_message  TEXT,
    duration_s     REAL,
    PRIMARY KEY (synset_id, run_id),
    FOREIGN KEY (run_id) REFERENCES batch_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_synset_status ON synset_status(status);
CREATE INDEX IF NOT EXISTS idx_synset_run ON synset_status(run_id);

CREATE TABLE IF NOT EXISTS attempt_log (
    synset_id      TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    attempt        INTEGER NOT NULL,
    status         TEXT NOT NULL,
    started_at     TEXT,
    finished_at    TEXT,
    exit_code      INTEGER,
    error_message  TEXT,
    duration_s     REAL,
    PRIMARY KEY (synset_id, run_id, attempt)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BatchStatusDB:
    """Persistent status tracker backed by SQLite with WAL mode."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── Batch runs ──

    def create_run(self, run_id: str, total_synsets: int, workers: int, model: str) -> None:
        self.conn.execute(
            "INSERT INTO batch_runs (run_id, started_at, total_synsets, workers, model) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, _now(), total_synsets, workers, model),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, status: str = "completed") -> None:
        # Compute total cost from synset_status
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM synset_status WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        total_cost = row[0] if row else 0.0
        self.conn.execute(
            "UPDATE batch_runs SET finished_at = ?, status = ?, total_cost_usd = ? "
            "WHERE run_id = ?",
            (_now(), status, total_cost, run_id),
        )
        self.conn.commit()

    def get_latest_run_id(self) -> str | None:
        row = self.conn.execute(
            "SELECT run_id FROM batch_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    # ── Synset status ──

    def init_synsets(self, run_id: str, synset_ids: list[str]) -> None:
        """Insert pending rows for synsets. Ignores if already present (for resume)."""
        self.conn.executemany(
            "INSERT OR IGNORE INTO synset_status (synset_id, run_id) VALUES (?, ?)",
            [(sid, run_id) for sid in synset_ids],
        )
        self.conn.commit()

    def mark_skipped(self, synset_id: str, run_id: str) -> None:
        self.conn.execute(
            "UPDATE synset_status SET status = 'skipped', finished_at = ? "
            "WHERE synset_id = ? AND run_id = ?",
            (_now(), synset_id, run_id),
        )
        self.conn.commit()

    def mark_running(self, synset_id: str, run_id: str, attempt: int) -> None:
        self.conn.execute(
            "UPDATE synset_status SET status = 'running', attempt = ?, started_at = ?, "
            "finished_at = NULL, cost_usd = NULL, exit_code = NULL, "
            "error_message = NULL, duration_s = NULL "
            "WHERE synset_id = ? AND run_id = ?",
            (attempt, _now(), synset_id, run_id),
        )
        self.conn.commit()

    def mark_success(self, synset_id: str, run_id: str, cost_usd: float, duration_s: float) -> None:
        self.conn.execute(
            "UPDATE synset_status SET status = 'success', cost_usd = ?, duration_s = ?, "
            "finished_at = ? WHERE synset_id = ? AND run_id = ?",
            (cost_usd, duration_s, _now(), synset_id, run_id),
        )
        self.conn.commit()

    def mark_failed(
        self, synset_id: str, run_id: str, exit_code: int, error: str, duration_s: float
    ) -> None:
        now = _now()
        # Get current attempt number for the log
        row = self.conn.execute(
            "SELECT attempt, started_at FROM synset_status WHERE synset_id = ? AND run_id = ?",
            (synset_id, run_id),
        ).fetchone()
        attempt = row[0] if row else 0
        started = row[1] if row else now
        # Persist per-attempt forensics (survives retry overwrites)
        self.conn.execute(
            "INSERT OR REPLACE INTO attempt_log "
            "(synset_id, run_id, attempt, status, started_at, finished_at, exit_code, error_message, duration_s) "
            "VALUES (?, ?, ?, 'failed', ?, ?, ?, ?, ?)",
            (synset_id, run_id, attempt, started, now, exit_code, error[:2000], duration_s),
        )
        # Update main status row
        self.conn.execute(
            "UPDATE synset_status SET status = 'failed', exit_code = ?, error_message = ?, "
            "duration_s = ?, finished_at = ? WHERE synset_id = ? AND run_id = ?",
            (exit_code, error[:1000], duration_s, now, synset_id, run_id),
        )
        self.conn.commit()

    # ── Queries ──

    def get_stats(self, run_id: str) -> dict:
        """Return counts by status and total cost for a run."""
        rows = self.conn.execute(
            "SELECT status, COUNT(*), COALESCE(SUM(cost_usd), 0) "
            "FROM synset_status WHERE run_id = ? GROUP BY status",
            (run_id,),
        ).fetchall()
        stats = {"pending": 0, "running": 0, "success": 0, "failed": 0, "skipped": 0, "total_cost": 0.0}
        for status, count, cost in rows:
            stats[status] = count
            stats["total_cost"] += cost
        return stats

    def get_resumable_synsets(self, run_id: str) -> list[tuple[str, int]]:
        """Return [(synset_id, attempt)] for pending or failed synsets."""
        rows = self.conn.execute(
            "SELECT synset_id, attempt FROM synset_status "
            "WHERE run_id = ? AND status IN ('pending', 'failed', 'running') "
            "ORDER BY synset_id",
            (run_id,),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]
