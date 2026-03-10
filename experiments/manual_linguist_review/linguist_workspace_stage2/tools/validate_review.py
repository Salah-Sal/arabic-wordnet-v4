#!/usr/bin/env python3
"""
validate_review.py — Validate review YAML files (v2 schema).

Checks structural completeness, mandatory fields, enum values,
and cross-field consistency for the simplified evidence-first schema.

Usage:
    python3 tools/validate_review.py output/awn4-01572394-v/review.yaml
    python3 tools/validate_review.py output/*/review.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


# ═══════════════════════════════════════════════════════════════════════════════
# Valid enum values
# ═══════════════════════════════════════════════════════════════════════════════

VALID_VERDICT = {"excellent", "good", "acceptable", "poor"}
VALID_DEFINITION_VERDICT = {"retain", "revise", "reject"}
VALID_LEMMA_STATUS = {"confirmed", "rejected", "modified"}
VALID_USAGE = {"archaic", "modern", "common"}
VALID_ELOQUENCE = {"eloquent", "neologism", "colloquial"}
VALID_CONNOTATION = {"positive", "negative", "neutral"}
VALID_REGISTER_PREFIX = {"literal", "figurative"}
VALID_MISSING_VERDICT = {"add", "new_synset", "reject"}
VALID_EXAMPLE_TYPE = {"quran", "hadith", "poetry", "prose", "authored"}
VALID_HYPERNYM_VERDICT = {"ok", "flag"}

SYNONYMY_TEST_FIELDS = {"substitution", "collocation", "antonymy", "componential"}

VALID_FLAG_CODES = {
    # Per-lemma flags
    "WEAK_EVIDENCE", "MEANING_MISMATCH", "LEMMA_NOT_FOUND",
    "HOMONYMY_RISK", "SYNONYM_REJECTED", "DEF_CONTRADICTS",
    "CALQUE_WARNING",
    # Synset-level flags
    "SPLIT_NEEDED", "LEXICAL_GAP", "NEEDS_ESCALATION",
    "POS_MISMATCH",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Validation logic
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewValidator:
    """Validates a v2 review YAML dict, collecting errors and warnings."""

    def __init__(self, data: dict, filepath: str = ""):
        self.data = data
        self.filepath = filepath
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def _check_enum(self, value, valid: set, field: str, required: bool = False):
        if not value:
            if required:
                self.error(f"{field}: required but empty")
            return
        if value not in valid:
            self.error(f"{field}: invalid value '{value}' — must be one of {sorted(valid)}")

    def _nonempty(self, value, field: str):
        if not value or (isinstance(value, str) and not value.strip()):
            self.error(f"{field}: required but empty")

    def validate(self) -> bool:
        """Run all checks. Returns True if valid (0 errors)."""
        d = self.data
        if not isinstance(d, dict):
            self.error("Root element must be a YAML mapping")
            return False

        self._check_header()
        self._check_lemmas()
        self._check_missing()
        self._check_definition()
        self._check_examples()
        self._check_hypernym()
        self._check_flags()

        return len(self.errors) == 0

    def _check_header(self):
        d = self.data
        sid = d.get("synset_id", "")
        if not sid:
            self.error("synset_id: required")
        elif not sid.startswith("awn4-"):
            self.warn(f"synset_id: '{sid}' does not start with 'awn4-'")

        self._check_enum(d.get("verdict"), VALID_VERDICT, "verdict", required=True)

        if not d.get("reviewer"):
            self.warn("reviewer: empty")
        if not d.get("review_date"):
            self.warn("review_date: empty")

    def _check_lemmas(self):
        lemmas = self.data.get("lemmas")
        if not lemmas:
            self.error("lemmas: at least one lemma required")
            return
        if not isinstance(lemmas, list):
            self.error("lemmas: must be a list")
            return

        for i, lem in enumerate(lemmas):
            p = f"lemmas[{i}]"
            if not isinstance(lem, dict):
                self.error(f"{p}: must be a mapping")
                continue

            # Required fields
            if not lem.get("lemma"):
                self.error(f"{p}.lemma: required")
            self._check_enum(lem.get("status"), VALID_LEMMA_STATUS, f"{p}.status", required=True)

            # Evidence — mandatory for all lemmas
            self._nonempty(lem.get("evidence"), f"{p}.evidence")

            status = lem.get("status", "")
            is_active = status in ("confirmed", "modified")

            # Nuance — mandatory for confirmed/modified only
            if is_active:
                self._nonempty(lem.get("nuance"), f"{p}.nuance")

            # Synonymy tests — mandatory for confirmed/modified, skipped for rejected
            if is_active:
                st = lem.get("synonymy_tests")
                if not st:
                    self.error(f"{p}.synonymy_tests: required for {status} lemmas")
                elif not isinstance(st, dict):
                    self.error(f"{p}.synonymy_tests: must be a mapping")
                else:
                    for field in SYNONYMY_TEST_FIELDS:
                        self._nonempty(st.get(field), f"{p}.synonymy_tests.{field}")

            # Enum fields
            self._check_enum(lem.get("usage"), VALID_USAGE, f"{p}.usage")
            self._check_enum(lem.get("eloquence"), VALID_ELOQUENCE, f"{p}.eloquence")
            self._check_enum(lem.get("connotation"), VALID_CONNOTATION, f"{p}.connotation")

            # Register: "literal" or "figurative (...)"
            reg = lem.get("register", "")
            if reg:
                prefix = reg.split()[0].split("(")[0].strip()
                if prefix not in VALID_REGISTER_PREFIX:
                    self.error(f"{p}.register: must start with 'literal' or 'figurative', got '{reg}'")

            # Per-lemma flags
            lem_flags = lem.get("flags")
            if lem_flags and isinstance(lem_flags, list):
                for j, f in enumerate(lem_flags):
                    if isinstance(f, str) and f not in VALID_FLAG_CODES:
                        self.warn(f"{p}.flags[{j}]: unknown flag '{f}'")

    def _check_missing(self):
        missing = self.data.get("missing")
        if not missing or not isinstance(missing, list):
            return
        for i, item in enumerate(missing):
            p = f"missing[{i}]"
            if not isinstance(item, dict):
                self.error(f"{p}: must be a mapping")
                continue
            if not item.get("candidate"):
                self.error(f"{p}.candidate: required")
            self._check_enum(item.get("verdict"), VALID_MISSING_VERDICT, f"{p}.verdict", required=True)
            self._nonempty(item.get("evidence"), f"{p}.evidence")

    def _check_definition(self):
        defn = self.data.get("definition")
        if not defn:
            self.warn("definition: section missing")
            return
        self._check_enum(defn.get("verdict"), VALID_DEFINITION_VERDICT, "definition.verdict", required=True)
        if defn.get("verdict") in ("revise", "reject") and not defn.get("revised"):
            self.error("definition.revised: required when verdict is revise or reject")

    def _check_examples(self):
        exs = self.data.get("examples")
        if not exs or not isinstance(exs, list):
            return
        for i, ex in enumerate(exs):
            p = f"examples[{i}]"
            if not isinstance(ex, dict):
                self.error(f"{p}: must be a mapping")
                continue
            self._check_enum(ex.get("type"), VALID_EXAMPLE_TYPE, f"{p}.type")
            if not ex.get("text"):
                self.error(f"{p}.text: required")

    def _check_hypernym(self):
        hyp = self.data.get("hypernym")
        if not hyp:
            return
        if not isinstance(hyp, dict):
            self.error("hypernym: must be a mapping")
            return
        self._check_enum(hyp.get("verdict"), VALID_HYPERNYM_VERDICT, "hypernym.verdict")
        if hyp.get("verdict") == "flag" and not hyp.get("note"):
            self.warn("hypernym.note: should be set when verdict=flag")

    def _check_flags(self):
        flags = self.data.get("flags")
        if not flags or not isinstance(flags, list):
            return
        for i, flag in enumerate(flags):
            if isinstance(flag, str) and flag not in VALID_FLAG_CODES:
                self.warn(f"flags[{i}]: unknown flag '{flag}'")

    def report(self) -> str:
        lines = []
        name = self.filepath or "review.yaml"
        if self.errors:
            lines.append(f"FAIL — {name}")
            lines.append(f"  {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
            lines.append("")
            for e in self.errors:
                lines.append(f"  ERROR: {e}")
        else:
            lines.append(f"OK — {name}")
            lines.append(f"  0 errors, {len(self.warnings)} warning(s)")

        if self.warnings:
            lines.append("")
            for w in self.warnings:
                lines.append(f"  WARN:  {w}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Validate review YAML files (v2 schema).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s output/awn4-01572394-v/review.yaml
  %(prog)s output/*/review.yaml
  %(prog)s --strict output/awn4-01572394-v/review.yaml
""",
    )
    parser.add_argument("files", nargs="+", metavar="FILE",
                        help="Review YAML files to validate")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    args = parser.parse_args()

    total_errors = 0
    total_warnings = 0

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"SKIP — {filepath}: file not found", file=sys.stderr)
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"FAIL — {filepath}: YAML parse error: {e}", file=sys.stderr)
            total_errors += 1
            continue

        if not data:
            print(f"FAIL — {filepath}: empty file", file=sys.stderr)
            total_errors += 1
            continue

        validator = ReviewValidator(data, filepath=str(path))
        validator.validate()
        print(validator.report())
        print()

        total_errors += len(validator.errors)
        total_warnings += len(validator.warnings)
        if args.strict:
            total_errors += len(validator.warnings)

    file_count = len(args.files)
    if file_count > 1:
        print(f"{'═' * 40}")
        print(f"Total: {file_count} files, {total_errors} errors, {total_warnings} warnings")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
