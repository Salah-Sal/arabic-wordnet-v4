#!/usr/bin/env python3
"""Extract a structured SQL query dataset from Claude Code worker trajectory files.

Each trajectory records a Claude Code session that autonomously reviewed an AWN4
synset by querying an Arabic dictionary SQLite database. This script parses those
JSONL trajectory files and extracts:
  - Synset metadata (from prepared/ directory)
  - Session metadata (cost, duration, turns, tokens)
  - Every SQL query issued (command, extracted SQL, classified type)
  - The result of each query (parsed JSON rows or raw text)

Output:
  - sql_query_dataset.jsonl  — one JSON record per synset
  - summary_stats.json       — aggregate statistics

Usage:
    python extract_trajectory_dataset.py                          # all successful
    python extract_trajectory_dataset.py --synset awn4-00023953-n # single synset
    python extract_trajectory_dataset.py --include-failed         # include rate-limited
    python extract_trajectory_dataset.py --backfill --db /path/to/arabic_dict.db  # re-run truncated queries
    python extract_trajectory_dataset.py --verbose                # debug output
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml


# ── TrajectoryParser ─────────────────────────────────────────────────────────

class TrajectoryParser:
    """Parse a Claude Code stream-json trajectory JSONL file."""

    def __init__(self, path: Path):
        self.path = path
        self.lines: list[dict] = []

    def parse(self) -> dict:
        """Parse the trajectory file and return structured data."""
        with open(self.path, encoding="utf-8") as f:
            self.lines = [json.loads(line) for line in f if line.strip()]

        if not self.lines:
            return {"error": "empty_file"}

        system_meta = self._parse_system()
        result_meta = self._parse_result()
        tool_pairs = self._build_tool_pairs()

        return {
            "system": system_meta,
            "result": result_meta,
            "tool_pairs": tool_pairs,
            "total_tool_calls": len(tool_pairs),
        }

    def _parse_system(self) -> dict:
        """Extract metadata from the system init line (line 0)."""
        line = self.lines[0] if self.lines else {}
        if line.get("type") != "system":
            return {}
        return {
            "session_id": line.get("session_id", ""),
            "model": line.get("model", ""),
            "claude_code_version": line.get("claude_code_version", ""),
        }

    def _parse_result(self) -> dict:
        """Extract session results from the final line."""
        line = self.lines[-1] if self.lines else {}
        if line.get("type") != "result":
            return {}

        model_usage = line.get("modelUsage", {})
        # Get the first (usually only) model's usage
        usage = next(iter(model_usage.values()), {}) if model_usage else {}

        return {
            "subtype": line.get("subtype", ""),
            "is_error": line.get("is_error", False),
            "total_cost_usd": line.get("total_cost_usd", 0),
            "duration_ms": line.get("duration_ms", 0),
            "num_turns": line.get("num_turns", 0),
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
            "cache_read_tokens": usage.get("cacheReadInputTokens", 0),
            "cache_creation_tokens": usage.get("cacheCreationInputTokens", 0),
        }

    def _build_tool_pairs(self) -> list[dict]:
        """Match tool_use blocks with their tool_result responses.

        Returns a list of dicts, each with:
          - tool_use: the tool_use content block (name, id, input)
          - tool_result: the matching user line's tool_use_result
          - tool_result_content: the content sent back to the LLM
          - is_error: whether the tool result was an error
        """
        # Collect all tool_use blocks keyed by id
        tool_uses: dict[str, dict] = {}
        for line in self.lines:
            if line.get("type") != "assistant":
                continue
            for block in line.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_uses[block["id"]] = block

        # Match with tool_result lines
        pairs = []
        for line in self.lines:
            if line.get("type") != "user":
                continue
            content_blocks = line.get("message", {}).get("content", [])
            for block in content_blocks:
                if block.get("type") != "tool_result":
                    continue
                tool_use_id = block.get("tool_use_id", "")
                if tool_use_id not in tool_uses:
                    continue

                tu = tool_uses[tool_use_id]
                pairs.append({
                    "tool_use": tu,
                    "tool_result": line.get("tool_use_result", {}),
                    "tool_result_content": block.get("content", ""),
                    "is_error": block.get("is_error", False),
                })

        return pairs


# ── SqlQueryExtractor ────────────────────────────────────────────────────────

class SqlQueryExtractor:
    """Extract and classify SQL queries from trajectory tool-call pairs."""

    # Pattern to capture SQL from: sqlite3 [-json] "db_path" "SQL" [2>/dev/null]
    _SQL_RE = re.compile(
        r'sqlite3\s+'
        r'(?:-json\s+)?'
        r'(?:"[^"]*"|\S+)\s+'       # DB path (quoted or bare)
        r'"((?:[^"\\]|\\.)*)"',      # SQL in double quotes
        re.DOTALL,
    )

    # Fallback: single-quoted SQL
    _SQL_RE_SINGLE = re.compile(
        r"sqlite3\s+"
        r"(?:-json\s+)?"
        r"""(?:'[^']*'|\S+)\s+"""
        r"'((?:[^'\\]|\\.)*)'",
        re.DOTALL,
    )

    @classmethod
    def extract(cls, tool_pairs: list[dict]) -> list[dict]:
        """Filter tool_pairs to sqlite3 Bash calls and extract query data."""
        queries = []
        idx = 0
        for pair in tool_pairs:
            tu = pair["tool_use"]
            if tu.get("name") != "Bash":
                continue
            command = tu.get("input", {}).get("command", "")
            if "sqlite3" not in command:
                continue

            sql = cls._extract_sql(command)
            pipe_suffix = cls._extract_pipe_suffix(command)
            is_piped = pipe_suffix is not None
            output_format = cls._detect_output_format(command, pipe_suffix)

            # tool_use_result can be a dict (normal) or a string (error)
            tr = pair["tool_result"]
            if isinstance(tr, dict):
                stdout = tr.get("stdout", "") or ""
            else:
                stdout = str(tr) if tr else ""

            result_parsed, row_count, error = cls._parse_result(
                stdout, output_format, is_piped
            )
            # Override error if the tool itself reported an error
            if pair.get("is_error") and not error:
                error = f"tool_error: {stdout[:200]}"

            queries.append({
                "query_index": idx,
                "tool_use_id": tu.get("id", ""),
                "command": command,
                "sql": sql,
                "query_type": cls._classify(sql),
                "output_format": output_format,
                "is_piped": is_piped,
                "pipe_suffix": pipe_suffix,
                "result_raw": stdout,
                "result_parsed": result_parsed,
                "result_row_count": row_count,
                "error": error,
            })
            idx += 1

        return queries

    @classmethod
    def _extract_sql(cls, command: str) -> str:
        """Extract the SQL statement from the sqlite3 bash command."""
        # Isolate the sqlite3 portion (before unquoted pipe)
        sqlite_part = cls._split_at_unquoted_pipe(command)

        m = cls._SQL_RE.search(sqlite_part)
        if m:
            return m.group(1).replace('\\"', '"').strip()

        m = cls._SQL_RE_SINGLE.search(sqlite_part)
        if m:
            return m.group(1).replace("\\'", "'").strip()

        return ""

    @classmethod
    def _split_at_unquoted_pipe(cls, command: str) -> str:
        """Return the portion of command before the first unquoted pipe."""
        in_double = False
        in_single = False
        escape = False
        for i, ch in enumerate(command):
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '|' and not in_double and not in_single:
                return command[:i]
        return command

    @classmethod
    def _extract_pipe_suffix(cls, command: str) -> Optional[str]:
        """Return the pipe suffix (after |) or None if no pipe."""
        sqlite_part = cls._split_at_unquoted_pipe(command)
        if len(sqlite_part) < len(command):
            return command[len(sqlite_part) + 1:].strip()
        return None

    @classmethod
    def _detect_output_format(
        cls, command: str, pipe_suffix: Optional[str]
    ) -> str:
        """Detect whether the output is JSON, formatted text, or plain text."""
        if pipe_suffix and "python" in pipe_suffix:
            return "formatted_text"
        if "-json" in command.split("|")[0]:
            return "json"
        return "text"

    @classmethod
    def _classify(cls, sql: str) -> str:
        """Classify the SQL query type based on its content."""
        upper = sql.upper()

        if "HEADWORD_NORM IN" in upper or "HEADWORD_NORM=" in upper:
            return "headword_lookup"
        if "ENTRIES_TRANSLATIONS_FTS" in upper:
            return "english_bridge"
        if "ENTRIES_FTS" in upper:
            return "fts_keyword"
        if "UNION ALL" in upper:
            return "enrichment"
        if "EXAMPLES" in upper and "ENTRY_ID" in upper:
            return "examples"
        if re.search(r"ROOT\s*=\s*'", sql, re.IGNORECASE):
            return "root_family"
        if re.search(r"ROOT\s+IN\s*\(", sql, re.IGNORECASE):
            return "root_family"
        if "ENTRY_ID IN" in upper and "HEADWORD_NORM" not in upper:
            return "enrichment"
        if "LIKE" in upper:
            return "headword_like"
        if "PRAGMA" in upper:
            return "pragma"
        return "other"

    @classmethod
    def _parse_result(
        cls, stdout: str, output_format: str, is_piped: bool
    ) -> tuple[Optional[list], int, Optional[str]]:
        """Parse stdout into structured data.

        Returns (result_parsed, row_count, error).
        """
        if not stdout or not stdout.strip():
            return ([], 0, None)

        if output_format == "formatted_text":
            # Python-formatted output — can't parse as JSON
            lines = [l for l in stdout.strip().split("\n")
                     if l.strip() and l.strip() != "---"]
            return (None, len(lines), None)

        if output_format == "text":
            lines = [l for l in stdout.strip().split("\n") if l.strip()]
            return (None, len(lines), None)

        # JSON format — attempt parse
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return (data, len(data), None)
            return ([data], 1, None)
        except json.JSONDecodeError as e:
            # Attempt recovery — truncation can happen from head pipes
            # or from system-level tool output limits
            recovered = cls._recover_truncated_json(stdout)
            if recovered is not None:
                return (recovered, len(recovered),
                        f"truncated_recovered:{len(recovered)}_rows")
            return (None, 0, f"json_parse_error: {str(e)[:200]}")

    @classmethod
    def _recover_truncated_json(cls, text: str) -> Optional[list]:
        """Try to recover a truncated JSON array by finding the last complete object."""
        text = text.strip()
        if not text.startswith("["):
            return None

        # Find the last complete JSON object (ending with })
        last_brace = text.rfind("}")
        if last_brace <= 0:
            return None

        candidate = text[:last_brace + 1] + "]"
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return None


# ── SynsetInfoLoader ─────────────────────────────────────────────────────────

class SynsetInfoLoader:
    """Load synset metadata from prepared/ directory."""

    def __init__(self, prepared_dir: Path):
        self.prepared_dir = prepared_dir

    def load(self, synset_id: str) -> Optional[dict]:
        """Load synset_info.yaml for the given synset."""
        synset_dir = self.prepared_dir / synset_id

        # Prefer full version (has lemmas), fall back to masked
        for fname in ("synset_info.yaml", "synset_info_masked.yaml"):
            path = synset_dir / fname
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f)
        return None


# ── DatasetBuilder ───────────────────────────────────────────────────────────

class DatasetBuilder:
    """Orchestrate extraction from all trajectories."""

    def __init__(
        self,
        trajectory_dir: Path,
        prepared_dir: Path,
        output_dir: Path,
        verbose: bool = False,
    ):
        self.trajectory_dir = trajectory_dir
        self.prepared_dir = prepared_dir
        self.output_dir = output_dir
        self.verbose = verbose
        self.loader = SynsetInfoLoader(prepared_dir)

    def build_record(self, synset_id: str) -> Optional[dict]:
        """Build a dataset record for one synset."""
        traj_path = self.trajectory_dir / f"{synset_id}.trajectory.jsonl"
        if not traj_path.exists():
            if self.verbose:
                print(f"  SKIP: no trajectory file for {synset_id}", file=sys.stderr)
            return None

        # Parse trajectory
        parser = TrajectoryParser(traj_path)
        parsed = parser.parse()
        if "error" in parsed:
            if self.verbose:
                print(f"  SKIP: parse error for {synset_id}: {parsed['error']}",
                      file=sys.stderr)
            return None

        # Extract SQL queries
        sql_queries = SqlQueryExtractor.extract(parsed["tool_pairs"])

        # Load synset info
        synset_info = self.loader.load(synset_id)

        # Build session metadata
        result = parsed.get("result", {})
        system = parsed.get("system", {})
        session_metadata = {
            "session_id": system.get("session_id", ""),
            "model": system.get("model", ""),
            "total_cost_usd": result.get("total_cost_usd", 0),
            "duration_ms": result.get("duration_ms", 0),
            "num_turns": result.get("num_turns", 0),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cache_read_tokens": result.get("cache_read_tokens", 0),
            "cache_creation_tokens": result.get("cache_creation_tokens", 0),
        }

        review_path = self.trajectory_dir / f"{synset_id}.review.yaml"

        return {
            "synset_id": synset_id,
            "synset_info": synset_info,
            "session_metadata": session_metadata,
            "sql_queries": sql_queries,
            "total_sql_queries": len(sql_queries),
            "total_tool_calls": parsed["total_tool_calls"],
            "review_yaml_path": str(review_path) if review_path.exists() else None,
        }

    def build_all(
        self,
        include_failed: bool = False,
        single_synset: Optional[str] = None,
    ) -> list[dict]:
        """Process all trajectories and write output files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Discover synsets
        if single_synset:
            synset_ids = [single_synset]
        else:
            synset_ids = sorted(
                p.stem.replace(".trajectory", "")
                for p in self.trajectory_dir.glob("*.trajectory.jsonl")
            )

        records = []
        skipped_rate_limited = 0
        skipped_no_review = 0
        errors = 0

        for i, synset_id in enumerate(synset_ids, 1):
            review_path = self.trajectory_dir / f"{synset_id}.review.yaml"
            has_review = review_path.exists()

            if not has_review and not include_failed:
                # Check if it's a rate-limited stub
                traj_path = self.trajectory_dir / f"{synset_id}.trajectory.jsonl"
                if traj_path.stat().st_size < 5000:
                    skipped_rate_limited += 1
                else:
                    skipped_no_review += 1
                if self.verbose:
                    print(f"[{i}/{len(synset_ids)}] SKIP: {synset_id} "
                          f"(no review, {'rate-limited' if traj_path.stat().st_size < 5000 else 'partial'})",
                          file=sys.stderr)
                continue

            if self.verbose:
                print(f"[{i}/{len(synset_ids)}] Processing {synset_id}...",
                      file=sys.stderr)

            record = self.build_record(synset_id)
            if record:
                records.append(record)
            else:
                errors += 1

        # Write dataset JSONL
        dataset_path = self.output_dir / "sql_query_dataset.jsonl"
        with open(dataset_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Write summary stats
        summary = self._compute_summary(
            records, len(synset_ids), skipped_rate_limited, skipped_no_review, errors
        )
        summary_path = self.output_dir / "summary_stats.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\nDataset written to {dataset_path} ({len(records)} records)")
        print(f"Summary written to {summary_path}")

        return records

    def _compute_summary(
        self,
        records: list[dict],
        total_files: int,
        skipped_rate_limited: int,
        skipped_no_review: int,
        errors: int,
    ) -> dict:
        """Compute aggregate statistics."""
        query_counts = [r["total_sql_queries"] for r in records]
        costs = [r["session_metadata"]["total_cost_usd"] for r in records]
        durations = [r["session_metadata"]["duration_ms"] / 1000 for r in records]

        # Query type distribution
        type_counter: Counter = Counter()
        piped_count = 0
        empty_results = 0
        parse_errors = 0
        for r in records:
            for q in r["sql_queries"]:
                type_counter[q["query_type"]] += 1
                if q["is_piped"]:
                    piped_count += 1
                if q["result_row_count"] == 0 and q["error"] is None:
                    empty_results += 1
                if q["error"] and "json_parse_error" in (q["error"] or ""):
                    parse_errors += 1

        total_queries = sum(query_counts) if query_counts else 0

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_trajectory_files": total_files,
            "records_extracted": len(records),
            "skipped_rate_limited": skipped_rate_limited,
            "skipped_no_review": skipped_no_review,
            "extraction_errors": errors,
            "total_sql_queries": total_queries,
            "queries_per_synset": {
                "mean": round(statistics.mean(query_counts), 1) if query_counts else 0,
                "median": statistics.median(query_counts) if query_counts else 0,
                "min": min(query_counts) if query_counts else 0,
                "max": max(query_counts) if query_counts else 0,
            },
            "query_type_distribution": dict(type_counter.most_common()),
            "piped_queries": piped_count,
            "empty_results": empty_results,
            "parse_errors": parse_errors,
            "cost": {
                "total_usd": round(sum(costs), 2) if costs else 0,
                "mean_usd": round(statistics.mean(costs), 2) if costs else 0,
                "median_usd": round(statistics.median(costs), 2) if costs else 0,
            },
            "duration": {
                "mean_seconds": round(statistics.mean(durations), 1) if durations else 0,
                "median_seconds": round(statistics.median(durations), 1) if durations else 0,
            },
        }


# ── Backfill ─────────────────────────────────────────────────────────────────

def backfill_truncated(dataset_path: Path, db_path: Path, verbose: bool = False) -> Path:
    """Re-execute truncated/failed JSON queries against the live database.

    Reads the existing dataset JSONL, finds queries with truncated_recovered or
    json_parse_error errors, re-runs the extracted SQL against the database, and
    writes a new backfilled dataset file alongside the original.

    Returns the path to the backfilled dataset.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    output_path = dataset_path.with_name(
        dataset_path.stem.replace("sql_query_dataset", "sql_query_dataset_backfilled") + ".jsonl"
    )

    total_backfilled = 0
    total_failed = 0
    total_already_ok = 0
    rows_before = 0
    rows_after = 0

    records = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    for rec in records:
        for q in rec["sql_queries"]:
            err = q.get("error") or ""
            needs_backfill = (
                "truncated_recovered" in err
                or "json_parse_error" in err
            )
            if not needs_backfill:
                total_already_ok += 1
                continue

            sql = q.get("sql", "").strip()
            if not sql:
                total_failed += 1
                continue

            rows_before += q.get("result_row_count", 0)

            try:
                cursor = conn.execute(sql)
                rows = [dict(row) for row in cursor.fetchall()]
                q["result_parsed"] = rows
                q["result_row_count"] = len(rows)
                q["result_raw"] = json.dumps(rows, ensure_ascii=False)
                q["error"] = None
                q["backfilled"] = True
                rows_after += len(rows)
                total_backfilled += 1
                if verbose:
                    print(f"  {rec['synset_id']} Q{q['query_index']}: "
                          f"backfilled {len(rows)} rows", file=sys.stderr)
            except Exception as e:
                total_failed += 1
                q["backfilled"] = False
                q["error"] = f"backfill_error: {str(e)[:200]}"
                if verbose:
                    print(f"  {rec['synset_id']} Q{q['query_index']}: "
                          f"FAILED: {e}", file=sys.stderr)

    conn.close()

    # Write backfilled dataset
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nBackfill complete:")
    print(f"  Queries backfilled: {total_backfilled}")
    print(f"  Queries failed:     {total_failed}")
    print(f"  Queries unchanged:  {total_already_ok}")
    print(f"  Rows before:        {rows_before} (from truncated recovery)")
    print(f"  Rows after:         {rows_after} (from live DB)")
    print(f"  Rows recovered:     {rows_after - rows_before}")
    print(f"\nBackfilled dataset: {output_path}")

    return output_path


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    script_dir = Path(__file__).resolve().parent
    default_traj = script_dir.parent / "linguistic_review_guide" / "output" / "reviews_claude_db"
    default_prepared = script_dir.parent / "linguistic_review_guide" / "claude_code_db" / "prepared"
    default_output = script_dir / "output"

    parser = argparse.ArgumentParser(
        description="Extract SQL query dataset from Claude Code trajectory files."
    )
    parser.add_argument(
        "--trajectory-dir", type=Path, default=default_traj,
        help=f"Directory containing .trajectory.jsonl files (default: {default_traj})",
    )
    parser.add_argument(
        "--prepared-dir", type=Path, default=default_prepared,
        help=f"Directory containing prepared/{{synset_id}}/ dirs (default: {default_prepared})",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=default_output,
        help=f"Output directory for dataset files (default: {default_output})",
    )
    parser.add_argument(
        "--synset", type=str, default=None,
        help="Process a single synset ID (e.g., awn4-00023953-n)",
    )
    parser.add_argument(
        "--include-failed", action="store_true",
        help="Include failed/rate-limited trajectories (default: skip)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print progress and debug information",
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help="Re-execute truncated queries against the live DB to recover full results",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="Path to arabic_dict.db (required for --backfill)",
    )
    args = parser.parse_args()

    # Handle backfill mode
    if args.backfill:
        db_path = args.db
        if db_path is None:
            # Try default location
            db_path = (script_dir.parent.parent / "arabic-dictionaries" / "db" / "arabic_dict.db")
        if not db_path.exists():
            print(f"Error: database not found at {db_path}", file=sys.stderr)
            print("Use --db to specify the path to arabic_dict.db", file=sys.stderr)
            sys.exit(1)
        dataset_path = args.output_dir / "sql_query_dataset.jsonl"
        if not dataset_path.exists():
            print(f"Error: dataset not found at {dataset_path}", file=sys.stderr)
            print("Run without --backfill first to extract the dataset.", file=sys.stderr)
            sys.exit(1)
        backfill_truncated(dataset_path, db_path, verbose=args.verbose)
        sys.exit(0)

    # Validate paths
    if not args.trajectory_dir.is_dir():
        print(f"Error: trajectory directory not found: {args.trajectory_dir}",
              file=sys.stderr)
        sys.exit(1)
    if not args.prepared_dir.is_dir():
        print(f"Error: prepared directory not found: {args.prepared_dir}",
              file=sys.stderr)
        sys.exit(1)

    builder = DatasetBuilder(
        trajectory_dir=args.trajectory_dir,
        prepared_dir=args.prepared_dir,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )
    records = builder.build_all(
        include_failed=args.include_failed,
        single_synset=args.synset,
    )

    if args.verbose:
        print(f"\nTotal records: {len(records)}", file=sys.stderr)
        total_q = sum(r["total_sql_queries"] for r in records)
        print(f"Total SQL queries: {total_q}", file=sys.stderr)


if __name__ == "__main__":
    main()
