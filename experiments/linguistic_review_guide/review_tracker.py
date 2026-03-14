#!/usr/bin/env python3
"""Unified review tracker & validator for AWN4 linguistic reviews.

Discovers all reviewer output directories (output/reviews_*_db/), validates
review YAML files against the spec schema at three levels (L1 structural,
L2 completeness, L3 semantic), and stores results in a unified SQLite DB
for coverage reporting and quality gating.

Usage:
    python review_tracker.py                          # Scan all, print summary
    python review_tracker.py --validate               # Full L1+L2+L3 validation
    python review_tracker.py --reviewer claude        # Filter by reviewer
    python review_tracker.py --synset awn4-00001740-n # Check specific synset
    python review_tracker.py --missing                # Prepared synsets with no valid review
    python review_tracker.py --coverage               # Coverage matrix
    python review_tracker.py --failures               # List validation failures
    python review_tracker.py --json                   # Machine-readable JSON output
    python review_tracker.py --refresh                # Force re-validation of all files
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
DB_PATH = OUTPUT_DIR / "review_registry.db"

REQUIRED_TOP_KEYS = [
    "step0_evidence",
    "step05_lemma_generation",
    "step1_lemma_validation",
    "step3_definition",
    "step4_relations",
    "step5_enrichment",
]

REVIEWER_DIR_PATTERN = "reviews_*_db"

# Valid enum values per spec
DECISION_VALUES = {"confirmed", "removed", "escalated"}
DEF_DECISION_VALUES = {"retain", "revise"}
HYPERNYMY_VALUES = {"correct", "needs_closer", "wrong"}
CULTURAL_FIT_VALUES = {"native", "phraset", "lexical_gap", "omission"}
EXAMPLE_TYPE_VALUES = {"quran", "hadith", "poetry", "usage"}

# ═══════════════════════════════════════════════════════════════════════════════
# DB Schema
# ═══════════════════════════════════════════════════════════════════════════════

SCHEMA = """\
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS reviewers (
    reviewer_id   TEXT PRIMARY KEY,
    output_dir    TEXT NOT NULL,
    first_seen    TEXT NOT NULL,
    last_scan     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    synset_id        TEXT NOT NULL,
    reviewer_id      TEXT NOT NULL REFERENCES reviewers(reviewer_id),
    file_path        TEXT NOT NULL,
    file_size        INTEGER NOT NULL,
    file_mtime       REAL NOT NULL,
    file_sha256      TEXT NOT NULL,
    scan_timestamp   TEXT NOT NULL,
    l1_valid         INTEGER NOT NULL DEFAULT 0,
    l2_valid         INTEGER NOT NULL DEFAULT 0,
    l3_valid         INTEGER NOT NULL DEFAULT 0,
    overall_valid    INTEGER NOT NULL DEFAULT 0,
    lemma_count      INTEGER,
    decisions_json   TEXT,
    def_decision     TEXT,
    hypernymy_result TEXT,
    cultural_fit     TEXT,
    UNIQUE(synset_id, reviewer_id)
);

CREATE TABLE IF NOT EXISTS validation_issues (
    issue_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id    INTEGER NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    level        TEXT NOT NULL,
    step         TEXT,
    field_path   TEXT,
    issue_type   TEXT NOT NULL,
    message      TEXT NOT NULL,
    severity     TEXT NOT NULL DEFAULT 'error'
);

CREATE TABLE IF NOT EXISTS synset_inventory (
    synset_id    TEXT PRIMARY KEY,
    pos          TEXT,
    depth        INTEGER,
    prepared     INTEGER NOT NULL DEFAULT 0,
    source       TEXT NOT NULL DEFAULT 'prepared'
);

CREATE INDEX IF NOT EXISTS idx_reviews_synset ON reviews(synset_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_valid ON reviews(overall_valid);
CREATE INDEX IF NOT EXISTS idx_issues_review ON validation_issues(review_id);
CREATE INDEX IF NOT EXISTS idx_inventory_prepared ON synset_inventory(prepared);
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_reviewer_name(dirname: str) -> str:
    """reviews_claude_db → claude, reviews_gemini_db → gemini."""
    m = re.match(r"reviews_(.+)_db$", dirname)
    return m.group(1) if m else dirname


def _synset_id_from_filename(filename: str) -> str | None:
    """awn4-00001740-n.review.yaml → awn4-00001740-n."""
    m = re.match(r"(awn4-\d{8}-[nvarsp])\.review\.yaml$", filename)
    return m.group(1) if m else None


def _get_nested(data: dict, dotted_path: str, default=None):
    """Traverse dotted path like 'step3_definition.assessment.decision'."""
    parts = dotted_path.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p, default)
        else:
            return default
    return cur


# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationIssue:
    level: str          # "L1", "L2", "L3"
    step: str | None    # "step0_evidence", etc.
    field_path: str | None
    issue_type: str     # "missing_key", "empty_list", "invalid_enum", etc.
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    l1_valid: bool = False
    l2_valid: bool = False
    l3_valid: bool = False
    overall_valid: bool = False
    issues: list[ValidationIssue] = field(default_factory=list)
    data: dict | None = None  # parsed YAML if L1 passes

    def add(self, issue: ValidationIssue):
        self.issues.append(issue)


def _validate_l1(file_path: Path) -> ValidationResult:
    """L1: Structural — file exists, non-empty, YAML parseable, dict, 6 top keys."""
    result = ValidationResult()

    # 1. Non-empty
    try:
        size = file_path.stat().st_size
    except OSError as e:
        result.add(ValidationIssue("L1", None, None, "file_error", str(e)))
        return result

    if size == 0:
        result.add(ValidationIssue("L1", None, None, "empty_file", "File is empty (0 bytes)"))
        return result

    # 2. YAML parses
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.add(ValidationIssue("L1", None, None, "yaml_parse_error", f"YAML parse error: {e}"))
        return result

    # 3. Is dict
    if not isinstance(data, dict):
        result.add(ValidationIssue(
            "L1", None, None, "not_dict",
            f"Top-level is {type(data).__name__}, expected dict"
        ))
        return result

    # 4. All 6 required keys
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            result.add(ValidationIssue(
                "L1", key, key, "missing_key",
                f"Missing required top-level key: {key}"
            ))

    # 5. Each top-level value is dict
    for key in REQUIRED_TOP_KEYS:
        if key in data and not isinstance(data[key], dict):
            result.add(ValidationIssue(
                "L1", key, key, "not_dict",
                f"{key} is {type(data[key]).__name__}, expected dict"
            ))

    l1_errors = [i for i in result.issues if i.level == "L1" and i.severity == "error"]
    result.l1_valid = len(l1_errors) == 0
    if result.l1_valid:
        result.data = data
    return result


def _check_list_field(data: dict, step: str, field_path: str,
                      required_subkeys: list[str],
                      result: ValidationResult, min_items: int = 1):
    """Check that a list field exists, has ≥min_items entries, each with required subkeys."""
    val = _get_nested(data.get(step, {}), field_path.split(".", 1)[-1] if "." in field_path else field_path)
    full_path = f"{step}.{field_path}" if not field_path.startswith(step) else field_path

    if val is None:
        result.add(ValidationIssue(
            "L2", step, full_path, "missing_key",
            f"Missing required field: {full_path}"
        ))
        return
    if not isinstance(val, list):
        result.add(ValidationIssue(
            "L2", step, full_path, "wrong_type",
            f"{full_path} is {type(val).__name__}, expected list"
        ))
        return
    if len(val) < min_items:
        result.add(ValidationIssue(
            "L2", step, full_path, "empty_list",
            f"{full_path} has {len(val)} items, expected ≥{min_items}"
        ))
        return

    for i, item in enumerate(val):
        if not isinstance(item, dict):
            result.add(ValidationIssue(
                "L2", step, f"{full_path}[{i}]", "wrong_type",
                f"{full_path}[{i}] is {type(item).__name__}, expected dict"
            ))
            continue
        for subkey in required_subkeys:
            if subkey not in item:
                result.add(ValidationIssue(
                    "L2", step, f"{full_path}[{i}]", "missing_key",
                    f"Missing '{subkey}' in {full_path}[{i}]"
                ))


def _validate_l2(data: dict, result: ValidationResult):
    """L2: Completeness — required sub-fields per step."""

    # step0_evidence.per_lemma: list, ≥1, each has .lemma
    _check_list_field(data, "step0_evidence", "per_lemma", ["lemma"], result)

    # step05_lemma_generation.evidence_candidates
    _check_list_field(data, "step05_lemma_generation", "evidence_candidates", ["lemma"], result)

    # step05_lemma_generation.knowledge_candidates
    _check_list_field(data, "step05_lemma_generation", "knowledge_candidates", ["lemma"], result)

    # step1_lemma_validation.per_lemma
    _check_list_field(
        data, "step1_lemma_validation", "per_lemma",
        ["lemma", "decision", "decision_reason"], result
    )

    # step3_definition.current_definition: non-empty string
    cur_def = _get_nested(data, "step3_definition.current_definition")
    if not cur_def or not isinstance(cur_def, str) or not cur_def.strip():
        result.add(ValidationIssue(
            "L2", "step3_definition", "step3_definition.current_definition",
            "missing_key" if cur_def is None else "empty_string",
            "step3_definition.current_definition must be a non-empty string"
        ))

    # step3_definition.assessment: dict with .decision
    assessment = _get_nested(data, "step3_definition.assessment")
    if not isinstance(assessment, dict):
        result.add(ValidationIssue(
            "L2", "step3_definition", "step3_definition.assessment",
            "missing_key" if assessment is None else "wrong_type",
            "step3_definition.assessment must be a dict"
        ))
    elif "decision" not in assessment:
        result.add(ValidationIssue(
            "L2", "step3_definition", "step3_definition.assessment.decision",
            "missing_key", "Missing 'decision' in step3_definition.assessment"
        ))

    # step4_relations.hypernymy: dict with .test_result
    hypernymy = _get_nested(data, "step4_relations.hypernymy")
    if not isinstance(hypernymy, dict):
        result.add(ValidationIssue(
            "L2", "step4_relations", "step4_relations.hypernymy",
            "missing_key" if hypernymy is None else "wrong_type",
            "step4_relations.hypernymy must be a dict"
        ))
    elif "test_result" not in hypernymy:
        result.add(ValidationIssue(
            "L2", "step4_relations", "step4_relations.hypernymy.test_result",
            "missing_key", "Missing 'test_result' in step4_relations.hypernymy"
        ))

    # step5_enrichment.per_lemma: list, ≥1, each has .lemma and .enrichment (dict)
    s5_per = _get_nested(data, "step5_enrichment.per_lemma")
    if s5_per is None:
        result.add(ValidationIssue(
            "L2", "step5_enrichment", "step5_enrichment.per_lemma",
            "missing_key", "Missing required field: step5_enrichment.per_lemma"
        ))
    elif not isinstance(s5_per, list):
        result.add(ValidationIssue(
            "L2", "step5_enrichment", "step5_enrichment.per_lemma",
            "wrong_type", f"step5_enrichment.per_lemma is {type(s5_per).__name__}, expected list"
        ))
    elif len(s5_per) < 1:
        result.add(ValidationIssue(
            "L2", "step5_enrichment", "step5_enrichment.per_lemma",
            "empty_list", "step5_enrichment.per_lemma is empty"
        ))
    else:
        for i, item in enumerate(s5_per):
            if not isinstance(item, dict):
                result.add(ValidationIssue(
                    "L2", "step5_enrichment", f"step5_enrichment.per_lemma[{i}]",
                    "wrong_type", f"step5_enrichment.per_lemma[{i}] is not a dict"
                ))
                continue
            if "lemma" not in item:
                result.add(ValidationIssue(
                    "L2", "step5_enrichment", f"step5_enrichment.per_lemma[{i}]",
                    "missing_key", f"Missing 'lemma' in step5_enrichment.per_lemma[{i}]"
                ))
            if "enrichment" not in item:
                result.add(ValidationIssue(
                    "L2", "step5_enrichment", f"step5_enrichment.per_lemma[{i}]",
                    "missing_key", f"Missing 'enrichment' in step5_enrichment.per_lemma[{i}]"
                ))
            elif not isinstance(item.get("enrichment"), dict):
                result.add(ValidationIssue(
                    "L2", "step5_enrichment", f"step5_enrichment.per_lemma[{i}].enrichment",
                    "wrong_type", f"step5_enrichment.per_lemma[{i}].enrichment must be a dict"
                ))

    l2_errors = [i for i in result.issues if i.level == "L2" and i.severity == "error"]
    result.l2_valid = len(l2_errors) == 0


def _validate_l3(data: dict, result: ValidationResult):
    """L3: Semantic — enum values, cross-references, minimums.

    All L3 issues are advisory warnings. LLMs naturally produce slight
    variations in enum values and field names, so L3 never blocks validity.
    """

    # step1.per_lemma[].decision ∈ {confirmed, removed, escalated}
    s1_per = _get_nested(data, "step1_lemma_validation.per_lemma") or []
    for i, item in enumerate(s1_per):
        if not isinstance(item, dict):
            continue
        dec = item.get("decision")
        if dec is not None and str(dec) not in DECISION_VALUES:
            result.add(ValidationIssue(
                "L3", "step1_lemma_validation",
                f"step1_lemma_validation.per_lemma[{i}].decision",
                "invalid_enum",
                f"decision='{dec}' not in {DECISION_VALUES}",
                severity="warning"
            ))

    # step3.assessment.decision ∈ {retain, revise}
    def_dec = _get_nested(data, "step3_definition.assessment.decision")
    if def_dec is not None and str(def_dec) not in DEF_DECISION_VALUES:
        result.add(ValidationIssue(
            "L3", "step3_definition",
            "step3_definition.assessment.decision",
            "invalid_enum",
            f"definition decision='{def_dec}' not in {DEF_DECISION_VALUES}",
            severity="warning"
        ))

    # step4.hypernymy.test_result ∈ {correct, needs_closer, wrong}
    hyp_result = _get_nested(data, "step4_relations.hypernymy.test_result")
    if hyp_result is not None and str(hyp_result) not in HYPERNYMY_VALUES:
        result.add(ValidationIssue(
            "L3", "step4_relations",
            "step4_relations.hypernymy.test_result",
            "invalid_enum",
            f"hypernymy test_result='{hyp_result}' not in {HYPERNYMY_VALUES}",
            severity="warning"
        ))

    # step5.per_lemma[].examples: list, ≥1 entry per lemma
    s5_per = _get_nested(data, "step5_enrichment.per_lemma") or []
    for i, item in enumerate(s5_per):
        if not isinstance(item, dict):
            continue
        lemma = item.get("lemma", f"[{i}]")
        examples = item.get("examples")
        if examples is None or not isinstance(examples, list) or len(examples) < 1:
            result.add(ValidationIssue(
                "L3", "step5_enrichment",
                f"step5_enrichment.per_lemma[{i}].examples",
                "missing_examples",
                f"No examples for lemma '{lemma}' (expected ≥1)",
                severity="warning"
            ))
            continue

        for j, ex in enumerate(examples):
            if not isinstance(ex, dict):
                continue
            # examples[].text: non-empty string
            ex_text = ex.get("text")
            if not ex_text or not isinstance(ex_text, str) or not ex_text.strip():
                result.add(ValidationIssue(
                    "L3", "step5_enrichment",
                    f"step5_enrichment.per_lemma[{i}].examples[{j}].text",
                    "empty_string",
                    f"Empty example text for lemma '{lemma}'",
                    severity="warning"
                ))
            # examples[].type ∈ {quran, hadith, poetry, usage} (warning)
            ex_type = ex.get("type")
            if ex_type is not None and str(ex_type) not in EXAMPLE_TYPE_VALUES:
                result.add(ValidationIssue(
                    "L3", "step5_enrichment",
                    f"step5_enrichment.per_lemma[{i}].examples[{j}].type",
                    "invalid_enum",
                    f"example type='{ex_type}' not in {EXAMPLE_TYPE_VALUES}",
                    severity="warning"
                ))

    # step0.per_lemma[].evidence_status if present: warn if not "no_material_found"
    s0_per = _get_nested(data, "step0_evidence.per_lemma") or []
    for i, item in enumerate(s0_per):
        if not isinstance(item, dict):
            continue
        ev_status = item.get("evidence_status")
        if ev_status is not None and ev_status != "no_material_found":
            result.add(ValidationIssue(
                "L3", "step0_evidence",
                f"step0_evidence.per_lemma[{i}].evidence_status",
                "unexpected_value",
                f"evidence_status='{ev_status}', expected 'no_material_found'",
                severity="warning"
            ))

    # step3: if decision == "revise", authored_definitions should be non-empty (warning)
    if str(def_dec) == "revise":
        authored = _get_nested(data, "step3_definition.authored_definitions")
        if not authored or not isinstance(authored, list) or len(authored) < 1:
            result.add(ValidationIssue(
                "L3", "step3_definition",
                "step3_definition.authored_definitions",
                "missing_authored",
                "decision='revise' but no authored_definitions provided",
                severity="warning"
            ))

    # step05 field naming: accept both reasoning and justification (warn if neither)
    s05 = data.get("step05_lemma_generation", {})
    for list_key in ("evidence_candidates", "knowledge_candidates"):
        candidates = s05.get(list_key) or []
        for i, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                continue
            if "justification" not in cand and "reasoning" not in cand:
                result.add(ValidationIssue(
                    "L3", "step05_lemma_generation",
                    f"step05_lemma_generation.{list_key}[{i}]",
                    "missing_justification",
                    f"Neither 'justification' nor 'reasoning' in {list_key}[{i}]",
                    severity="warning"
                ))

    # cultural_fit check
    cf = _get_nested(data, "step5_enrichment.cultural_fit.assessment")
    if cf is not None and str(cf) not in CULTURAL_FIT_VALUES:
        result.add(ValidationIssue(
            "L3", "step5_enrichment",
            "step5_enrichment.cultural_fit.assessment",
            "invalid_enum",
            f"cultural_fit='{cf}' not in {CULTURAL_FIT_VALUES}",
            severity="warning"
        ))

    l3_errors = [i for i in result.issues if i.level == "L3" and i.severity == "error"]
    result.l3_valid = len(l3_errors) == 0


def validate_review_file(file_path: Path) -> ValidationResult:
    """Full L1+L2+L3 validation of a review YAML file.

    overall_valid depends only on L1 (structural) + L2 (completeness).
    L3 (semantic) issues are advisory warnings — LLMs naturally produce
    slight variations in enum values, field names, etc.
    """
    result = _validate_l1(file_path)
    if not result.l1_valid:
        return result
    _validate_l2(result.data, result)
    if not result.l2_valid:
        result.overall_valid = False
        return result
    _validate_l3(result.data, result)
    result.overall_valid = result.l1_valid and result.l2_valid
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Summary Extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_summary(data: dict) -> dict:
    """Extract quick-access summary fields from parsed review data."""
    summary: dict[str, Any] = {}

    # Lemma count from step1
    s1_per = _get_nested(data, "step1_lemma_validation.per_lemma")
    if isinstance(s1_per, list):
        summary["lemma_count"] = len(s1_per)
        decisions: dict[str, int] = {"confirmed": 0, "removed": 0, "escalated": 0}
        for item in s1_per:
            if isinstance(item, dict):
                dec = str(item.get("decision", ""))
                if dec in decisions:
                    decisions[dec] += 1
        summary["decisions_json"] = json.dumps(decisions)

    # Definition decision
    summary["def_decision"] = str(_get_nested(data, "step3_definition.assessment.decision") or "")

    # Hypernymy result
    summary["hypernymy_result"] = str(_get_nested(data, "step4_relations.hypernymy.test_result") or "")

    # Cultural fit
    summary["cultural_fit"] = str(_get_nested(data, "step5_enrichment.cultural_fit.assessment") or "")

    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewDB:
    """SQLite-backed registry of review files, validation results, and inventory."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        # WAL + busy_timeout set via PRAGMA in schema
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── Reviewers ──

    def upsert_reviewer(self, reviewer_id: str, output_dir: str):
        now = _now()
        self.conn.execute(
            "INSERT INTO reviewers (reviewer_id, output_dir, first_seen, last_scan) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(reviewer_id) DO UPDATE SET last_scan = ?, output_dir = ?",
            (reviewer_id, output_dir, now, now, now, output_dir),
        )
        self.conn.commit()

    def get_reviewers(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM reviewers ORDER BY reviewer_id").fetchall()
        return [dict(r) for r in rows]

    # ── Reviews ──

    def get_review(self, synset_id: str, reviewer_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM reviews WHERE synset_id = ? AND reviewer_id = ?",
            (synset_id, reviewer_id),
        ).fetchone()
        return dict(row) if row else None

    def needs_rescan(self, synset_id: str, reviewer_id: str,
                     file_size: int, file_mtime: float) -> bool:
        """Return True if file has changed since last scan."""
        existing = self.get_review(synset_id, reviewer_id)
        if existing is None:
            return True
        return existing["file_size"] != file_size or existing["file_mtime"] != file_mtime

    def upsert_review(self, synset_id: str, reviewer_id: str,
                      file_path: str, file_size: int, file_mtime: float,
                      file_sha256: str, vr: ValidationResult,
                      summary: dict):
        now = _now()
        # Delete old issues for this review if it exists
        existing = self.get_review(synset_id, reviewer_id)
        if existing:
            self.conn.execute(
                "DELETE FROM validation_issues WHERE review_id = ?",
                (existing["review_id"],),
            )

        self.conn.execute(
            "INSERT INTO reviews "
            "(synset_id, reviewer_id, file_path, file_size, file_mtime, file_sha256, "
            " scan_timestamp, l1_valid, l2_valid, l3_valid, overall_valid, "
            " lemma_count, decisions_json, def_decision, hypernymy_result, cultural_fit) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(synset_id, reviewer_id) DO UPDATE SET "
            " file_path=excluded.file_path, file_size=excluded.file_size, "
            " file_mtime=excluded.file_mtime, file_sha256=excluded.file_sha256, "
            " scan_timestamp=excluded.scan_timestamp, "
            " l1_valid=excluded.l1_valid, l2_valid=excluded.l2_valid, "
            " l3_valid=excluded.l3_valid, overall_valid=excluded.overall_valid, "
            " lemma_count=excluded.lemma_count, decisions_json=excluded.decisions_json, "
            " def_decision=excluded.def_decision, hypernymy_result=excluded.hypernymy_result, "
            " cultural_fit=excluded.cultural_fit",
            (
                synset_id, reviewer_id, file_path, file_size, file_mtime,
                file_sha256, now,
                int(vr.l1_valid), int(vr.l2_valid), int(vr.l3_valid), int(vr.overall_valid),
                summary.get("lemma_count"),
                summary.get("decisions_json"),
                summary.get("def_decision"),
                summary.get("hypernymy_result"),
                summary.get("cultural_fit"),
            ),
        )

        # Get review_id for issues
        row = self.conn.execute(
            "SELECT review_id FROM reviews WHERE synset_id = ? AND reviewer_id = ?",
            (synset_id, reviewer_id),
        ).fetchone()
        review_id = row["review_id"]

        # Insert issues
        for issue in vr.issues:
            self.conn.execute(
                "INSERT INTO validation_issues "
                "(review_id, level, step, field_path, issue_type, message, severity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (review_id, issue.level, issue.step, issue.field_path,
                 issue.issue_type, issue.message, issue.severity),
            )

        self.conn.commit()

    # ── Inventory ──

    def populate_inventory(self, prepared_dirs: list[Path], batch_files: list[Path]):
        """Scan prepared dirs and batch files to build synset inventory."""
        # Build depth map from batch files
        depth_map: dict[str, int] = {}
        for bf in batch_files:
            depth_range = None
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("# Depth:"):
                            m = re.search(r"(\d+)-(\d+)", line)
                            if m:
                                depth_range = (int(m.group(1)), int(m.group(2)))
                        elif line.startswith("# L") and ":" in line:
                            # Parse "# L0:1 L1:3 L2:27" for per-depth counts
                            pass
                        elif line.startswith("awn4-"):
                            sid = line.strip()
                            if depth_range and sid not in depth_map:
                                # Assign max depth of range as approximation
                                depth_map[sid] = depth_range[1]
                        elif line.startswith("#") or not line:
                            continue
            except OSError:
                continue

        # More precise: parse the per-depth comment line for exact assignment
        for bf in batch_files:
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except OSError:
                continue
            depth_counts: dict[int, int] = {}
            synset_lines: list[str] = []
            for line in lines:
                line = line.strip()
                if line.startswith("# L") and ":" in line and not line.startswith("# Depth"):
                    # "# L0:1 L1:3 L2:27"
                    for m in re.finditer(r"L(\d+):(\d+)", line):
                        depth_counts[int(m.group(1))] = int(m.group(2))
                elif line.startswith("awn4-"):
                    synset_lines.append(line)

            if depth_counts and synset_lines:
                idx = 0
                for depth in sorted(depth_counts):
                    count = depth_counts[depth]
                    for sid in synset_lines[idx:idx + count]:
                        depth_map[sid] = depth
                    idx += count

        # Insert from prepared dirs
        for pdir in prepared_dirs:
            resolved = pdir.resolve()
            if not resolved.is_dir():
                continue
            sid = resolved.name
            pos_match = re.search(r"-([nvarsp])$", sid)
            pos = pos_match.group(1) if pos_match else None
            depth = depth_map.get(sid)
            self.conn.execute(
                "INSERT INTO synset_inventory (synset_id, pos, depth, prepared, source) "
                "VALUES (?, ?, ?, 1, 'prepared') "
                "ON CONFLICT(synset_id) DO UPDATE SET "
                "pos = COALESCE(excluded.pos, synset_inventory.pos), "
                "depth = COALESCE(excluded.depth, synset_inventory.depth), "
                "prepared = 1",
                (sid, pos, depth),
            )
        self.conn.commit()

    # ── Queries ──

    def get_review_stats(self, reviewer_id: str | None = None) -> list[dict]:
        """Per-reviewer counts of total, l1_valid, l2_valid, l3_valid, overall_valid."""
        where = ""
        params: tuple = ()
        if reviewer_id:
            where = "WHERE reviewer_id = ?"
            params = (reviewer_id,)
        rows = self.conn.execute(
            f"SELECT reviewer_id, COUNT(*) as total, "
            f"SUM(l1_valid) as l1, SUM(l2_valid) as l2, SUM(l3_valid) as l3, "
            f"SUM(overall_valid) as valid "
            f"FROM reviews {where} GROUP BY reviewer_id ORDER BY reviewer_id",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_coverage(self) -> dict:
        """Coverage of prepared synsets across all reviewers."""
        total_prepared = self.conn.execute(
            "SELECT COUNT(*) FROM synset_inventory WHERE prepared = 1"
        ).fetchone()[0]

        with_valid = self.conn.execute(
            "SELECT COUNT(DISTINCT si.synset_id) FROM synset_inventory si "
            "JOIN reviews r ON si.synset_id = r.synset_id "
            "WHERE si.prepared = 1 AND r.overall_valid = 1"
        ).fetchone()[0]

        multi_reviewer = self.conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT si.synset_id FROM synset_inventory si "
            "  JOIN reviews r ON si.synset_id = r.synset_id "
            "  WHERE si.prepared = 1 AND r.overall_valid = 1 "
            "  GROUP BY si.synset_id HAVING COUNT(DISTINCT r.reviewer_id) > 1"
            ")"
        ).fetchone()[0]

        return {
            "total_prepared": total_prepared,
            "with_valid_review": with_valid,
            "multi_reviewer": multi_reviewer,
            "not_reviewed": total_prepared - with_valid,
        }

    def get_missing_synsets(self, reviewer_id: str | None = None) -> list[str]:
        """Prepared synsets with no valid review (optionally filtered by reviewer)."""
        if reviewer_id:
            rows = self.conn.execute(
                "SELECT si.synset_id FROM synset_inventory si "
                "WHERE si.prepared = 1 AND si.synset_id NOT IN ("
                "  SELECT synset_id FROM reviews "
                "  WHERE reviewer_id = ? AND overall_valid = 1"
                ") ORDER BY si.synset_id",
                (reviewer_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT si.synset_id FROM synset_inventory si "
                "WHERE si.prepared = 1 AND si.synset_id NOT IN ("
                "  SELECT synset_id FROM reviews WHERE overall_valid = 1"
                ") ORDER BY si.synset_id",
            ).fetchall()
        return [r[0] for r in rows]

    def get_failures(self, reviewer_id: str | None = None,
                     synset_id: str | None = None) -> list[dict]:
        """Return reviews with issues, grouped by synset+reviewer."""
        where_parts = ["1=1"]
        params: list = []
        if reviewer_id:
            where_parts.append("r.reviewer_id = ?")
            params.append(reviewer_id)
        if synset_id:
            where_parts.append("r.synset_id = ?")
            params.append(synset_id)

        where = " AND ".join(where_parts)
        rows = self.conn.execute(
            f"SELECT r.review_id, r.synset_id, r.reviewer_id, r.overall_valid, "
            f"r.l1_valid, r.l2_valid, r.l3_valid "
            f"FROM reviews r WHERE {where} AND r.overall_valid = 0 "
            f"ORDER BY r.synset_id, r.reviewer_id",
            params,
        ).fetchall()

        results = []
        for r in rows:
            issues = self.conn.execute(
                "SELECT level, step, field_path, issue_type, message, severity "
                "FROM validation_issues WHERE review_id = ? ORDER BY level, issue_id",
                (r["review_id"],),
            ).fetchall()
            results.append({
                "synset_id": r["synset_id"],
                "reviewer_id": r["reviewer_id"],
                "l1_valid": bool(r["l1_valid"]),
                "l2_valid": bool(r["l2_valid"]),
                "l3_valid": bool(r["l3_valid"]),
                "issues": [dict(i) for i in issues],
            })
        return results

    def get_synset_reviews(self, synset_id: str) -> list[dict]:
        """All reviews for a specific synset across all reviewers."""
        rows = self.conn.execute(
            "SELECT * FROM reviews WHERE synset_id = ? ORDER BY reviewer_id",
            (synset_id,),
        ).fetchall()
        results = []
        for r in rows:
            rd = dict(r)
            issues = self.conn.execute(
                "SELECT level, step, field_path, issue_type, message, severity "
                "FROM validation_issues WHERE review_id = ? ORDER BY level",
                (r["review_id"],),
            ).fetchall()
            rd["issues"] = [dict(i) for i in issues]
            results.append(rd)
        return results


# ═══════════════════════════════════════════════════════════════════════════════
# Scanner
# ═══════════════════════════════════════════════════════════════════════════════

def discover_reviewers(output_dir: Path) -> list[tuple[str, Path]]:
    """Find all output/reviews_*_db/ directories and extract reviewer names."""
    reviewers = []
    for d in sorted(output_dir.glob(REVIEWER_DIR_PATTERN)):
        if d.is_dir():
            name = _extract_reviewer_name(d.name)
            reviewers.append((name, d))
    return reviewers


def scan_reviewer(db: ReviewDB, reviewer_id: str, reviewer_dir: Path,
                  force_refresh: bool = False, do_validate: bool = True) -> dict:
    """Scan a reviewer directory for review files, validate, and store results."""
    stats = {"total": 0, "scanned": 0, "cached": 0, "valid": 0, "invalid": 0}

    # Only glob *.review.yaml at top level (no subdirs)
    review_files = sorted(reviewer_dir.glob("*.review.yaml"))
    stats["total"] = len(review_files)

    for fpath in review_files:
        synset_id = _synset_id_from_filename(fpath.name)
        if not synset_id:
            continue

        st = fpath.stat()
        file_size = st.st_size
        file_mtime = st.st_mtime

        if not force_refresh and not db.needs_rescan(synset_id, reviewer_id, file_size, file_mtime):
            stats["cached"] += 1
            existing = db.get_review(synset_id, reviewer_id)
            if existing and existing["overall_valid"]:
                stats["valid"] += 1
            else:
                stats["invalid"] += 1
            continue

        stats["scanned"] += 1
        sha = _sha256(fpath)

        if do_validate:
            vr = validate_review_file(fpath)
        else:
            # Quick scan: just L1
            vr = _validate_l1(fpath)
            vr.overall_valid = vr.l1_valid

        summary = _extract_summary(vr.data) if vr.data else {}

        db.upsert_review(
            synset_id, reviewer_id, str(fpath), file_size, file_mtime,
            sha, vr, summary
        )

        if vr.overall_valid:
            stats["valid"] += 1
        else:
            stats["invalid"] += 1

    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(db: ReviewDB):
    """Print human-readable summary report."""
    reviewers = db.get_reviewers()
    review_stats = db.get_review_stats()
    coverage = db.get_coverage()

    print("AWN4 Review Tracker")
    print("===================")

    # Reviewers line
    rev_parts = []
    for rs in review_stats:
        n = rs['total']
        rev_parts.append(f"{rs['reviewer_id']} ({n} {'file' if n == 1 else 'files'})")
    if rev_parts:
        print(f"Reviewers: {', '.join(rev_parts)}")
    else:
        print("Reviewers: (none found)")
    print(f"Inventory: {coverage['total_prepared']} prepared")

    print()
    print("Validation:")
    for rs in review_stats:
        valid = rs["valid"] or 0
        total = rs["total"] or 0
        pct = (valid / total * 100) if total > 0 else 0
        l1 = rs["l1"] or 0
        l2 = rs["l2"] or 0
        l3 = rs["l3"] or 0
        print(f"  {rs['reviewer_id']:8s}: {valid}/{total} valid ({pct:.1f}%)  "
              f"|  L1: {l1}  L2: {l2}  L3: {l3}")

    print()
    print("Coverage (prepared synsets):")
    wv = coverage["with_valid_review"]
    tp = coverage["total_prepared"]
    pct = (wv / tp * 100) if tp > 0 else 0
    print(f"  With >=1 valid review: {wv}/{tp} ({pct:.1f}%)")
    print(f"  Reviewed by multiple:  {coverage['multi_reviewer']}")
    print(f"  Not yet reviewed:      {coverage['not_reviewed']}")


def print_failures(db: ReviewDB, reviewer_id: str | None = None,
                   synset_id: str | None = None):
    """Print detailed validation failures."""
    failures = db.get_failures(reviewer_id=reviewer_id, synset_id=synset_id)
    if not failures:
        print("No validation failures found.")
        return

    for f in failures:
        print(f"\n{f['synset_id']} ({f['reviewer_id']}):")
        for issue in f["issues"]:
            sev = "WARN" if issue["severity"] == "warning" else issue["level"]
            path = issue.get("field_path") or issue.get("step") or ""
            print(f"  [{sev}] {path}: {issue['message']}")


def print_missing(db: ReviewDB, reviewer_id: str | None = None):
    """Print prepared synsets with no valid review."""
    missing = db.get_missing_synsets(reviewer_id=reviewer_id)
    if not missing:
        print("All prepared synsets have at least one valid review.")
        return

    label = f" (reviewer: {reviewer_id})" if reviewer_id else ""
    print(f"Prepared synsets with no valid review{label}: {len(missing)}")
    for sid in missing:
        print(f"  {sid}")


def print_coverage_matrix(db: ReviewDB):
    """Print coverage matrix: synsets x reviewers."""
    reviewers = db.get_reviewers()
    if not reviewers:
        print("No reviewers found.")
        return

    rev_ids = [r["reviewer_id"] for r in reviewers]

    # Header
    header = f"{'synset_id':22s}"
    for rid in rev_ids:
        header += f"  {rid:>8s}"
    print(header)
    print("-" * len(header))

    # Get all prepared synsets
    rows = db.conn.execute(
        "SELECT synset_id FROM synset_inventory WHERE prepared = 1 ORDER BY synset_id"
    ).fetchall()

    for row in rows:
        sid = row[0]
        line = f"{sid:22s}"
        for rid in rev_ids:
            rev = db.get_review(sid, rid)
            if rev is None:
                line += f"  {'--':>8s}"
            elif rev["overall_valid"]:
                line += f"  {'valid':>8s}"
            else:
                line += f"  {'FAIL':>8s}"
        print(line)


def print_synset_detail(db: ReviewDB, synset_id: str):
    """Print detailed info for a specific synset across all reviewers."""
    reviews = db.get_synset_reviews(synset_id)
    if not reviews:
        print(f"No reviews found for {synset_id}")
        return

    print(f"Reviews for {synset_id}:")
    for r in reviews:
        status = "VALID" if r["overall_valid"] else "INVALID"
        print(f"\n  [{r['reviewer_id']}] {status}")
        print(f"    L1: {'pass' if r['l1_valid'] else 'FAIL'}  "
              f"L2: {'pass' if r['l2_valid'] else 'FAIL'}  "
              f"L3: {'pass' if r['l3_valid'] else 'FAIL'}")
        if r.get("lemma_count") is not None:
            print(f"    Lemmas: {r['lemma_count']}")
        if r.get("decisions_json"):
            print(f"    Decisions: {r['decisions_json']}")
        if r.get("def_decision"):
            print(f"    Definition: {r['def_decision']}")
        if r.get("hypernymy_result"):
            print(f"    Hypernymy: {r['hypernymy_result']}")
        if r.get("cultural_fit"):
            print(f"    Cultural fit: {r['cultural_fit']}")

        if r.get("issues"):
            print("    Issues:")
            for issue in r["issues"]:
                sev = "WARN" if issue["severity"] == "warning" else issue["level"]
                path = issue.get("field_path") or issue.get("step") or ""
                print(f"      [{sev}] {path}: {issue['message']}")


def build_json_output(db: ReviewDB, reviewer_id: str | None = None,
                      synset_id: str | None = None) -> dict:
    """Build complete JSON output."""
    output: dict[str, Any] = {"timestamp": _now()}

    output["reviewers"] = db.get_reviewers()
    output["stats"] = db.get_review_stats(reviewer_id)
    output["coverage"] = db.get_coverage()

    # Failures
    failures = db.get_failures(reviewer_id=reviewer_id, synset_id=synset_id)
    output["failures"] = failures

    # Missing
    output["missing"] = db.get_missing_synsets(reviewer_id=reviewer_id)

    # Synset detail if requested
    if synset_id:
        output["synset_reviews"] = db.get_synset_reviews(synset_id)

    return output


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AWN4 Unified Review Tracker & Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--validate", action="store_true",
                        help="Full L1+L2+L3 validation (default: L1-only quick scan)")
    parser.add_argument("--reviewer", type=str, default=None,
                        help="Filter by reviewer name (e.g., 'claude')")
    parser.add_argument("--synset", type=str, default=None,
                        help="Check a specific synset ID")
    parser.add_argument("--missing", action="store_true",
                        help="List prepared synsets with no valid review")
    parser.add_argument("--coverage", action="store_true",
                        help="Print coverage matrix (synsets x reviewers)")
    parser.add_argument("--failures", action="store_true",
                        help="List validation failures with details")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-validation of all files")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Override output directory path")
    parser.add_argument("--db", type=str, default=None,
                        help="Override database path")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    db_path = Path(args.db) if args.db else DB_PATH

    # ── Initialize DB ──
    db = ReviewDB(db_path)

    # ── Discover reviewers ──
    reviewers = discover_reviewers(output_dir)
    if not reviewers and not args.json:
        print(f"No reviewer directories found matching {output_dir}/{REVIEWER_DIR_PATTERN}")
        db.close()
        sys.exit(1)

    # ── Populate inventory ──
    # Find prepared dirs: look in each reviews_X_db's sibling agent dirs
    prepared_dirs: list[Path] = []
    batch_files: list[Path] = []

    # Standard locations for prepared data
    for agent_dir_name in ("claude_code_db", "gemini_code_db"):
        agent_dir = SCRIPT_DIR / agent_dir_name
        prep = agent_dir / "prepared"
        if prep.exists():
            resolved = prep.resolve()
            if resolved.is_dir():
                for child in sorted(resolved.iterdir()):
                    if child.is_dir() and child.name.startswith("awn4-"):
                        prepared_dirs.append(child)
        batches = agent_dir / "batches"
        if batches.exists():
            for bf in sorted(batches.glob("*.txt")):
                batch_files.append(bf)

    # Deduplicate by resolved path (gemini_code_db/prepared symlinks to claude_code_db/prepared)
    seen_resolved: set[str] = set()
    deduped_prepared: list[Path] = []
    for p in prepared_dirs:
        rp = str(p.resolve())
        if rp not in seen_resolved:
            seen_resolved.add(rp)
            deduped_prepared.append(p)
    prepared_dirs = deduped_prepared

    db.populate_inventory(prepared_dirs, batch_files)

    # ── Scan reviewers ──
    # Default to full validation if --validate, --failures, or --json is given
    do_validate = args.validate or args.failures or args.json or args.synset is not None

    all_scan_stats: dict[str, dict] = {}
    for reviewer_id, reviewer_dir in reviewers:
        if args.reviewer and reviewer_id != args.reviewer:
            continue
        db.upsert_reviewer(reviewer_id, str(reviewer_dir))
        stats = scan_reviewer(
            db, reviewer_id, reviewer_dir,
            force_refresh=args.refresh,
            do_validate=do_validate,
        )
        all_scan_stats[reviewer_id] = stats

    # ── Output ──
    if args.json:
        result = build_json_output(db, reviewer_id=args.reviewer, synset_id=args.synset)
        result["scan_stats"] = all_scan_stats
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.synset:
        print_synset_detail(db, args.synset)
    elif args.failures:
        print_failures(db, reviewer_id=args.reviewer, synset_id=args.synset)
    elif args.missing:
        print_missing(db, reviewer_id=args.reviewer)
    elif args.coverage:
        print_coverage_matrix(db)
    else:
        print_summary(db)

    db.close()


if __name__ == "__main__":
    main()
