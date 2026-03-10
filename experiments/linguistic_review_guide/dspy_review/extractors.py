#!/usr/bin/env python3
"""Section and data extraction helpers for the Level 4 step-decomposed pipeline.

Provides two categories of functions:

1. **Section extractors**: Slice the monolithic algorithm (draft_api.md, 1078 lines)
   and schema (output_step0.yaml, 1361 lines) into per-step sections, so each
   pipeline module receives only the instructions relevant to its task.

2. **Inter-step data extractors**: Parse YAML outputs from completed steps and
   extract the specific data needed by downstream steps (e.g., confirmed lemma
   list from Step 1 → Step 2).

All functions are pure Python — no LLM calls, no DSPy dependencies.
"""
from __future__ import annotations

import yaml


# ═══════════════════════════════════════════════════════════════
# Algorithm section extraction (draft_api.md → per-step slices)
# ═══════════════════════════════════════════════════════════════

# Line ranges (1-indexed, inclusive) — verified against draft_api.md (1078 lines)
_ALGORITHM_CONVENTIONS_END = 107  # Lines 1–107: conventions + execution model

_ALGORITHM_STEP_RANGES = {
    0: (108, 157),   # الخطوة ٠: Evidence Extraction
    1: (159, 326),   # الخطوة ١: Lemma Validation
    2: (329, 405),   # الخطوة ٢: Missing Lemmas
    3: (408, 440),   # الخطوة ٣: Definition Processing
    4: (443, 487),   # الخطوة ٤: Relations Check
    5: (490, 590),   # الخطوة ٥: Enrichment & Culture
}

# Sub-routines referenced by specific steps
_SUBROUTINE_RANGES = {
    1: [(857, 938)],  # substitution_test + all authoring sub-routines
    2: [(913, 938)],  # substitution_test only
    3: [(859, 911)],  # author_terminological_def, author_linguistic_def, quality_check
}


def extract_algorithm_section(algorithm_text: str, step: int) -> str:
    """Extract the algorithm section for a given step (0-5).

    Returns the conventions block (lines 1-107) + the step's pseudocode block
    + any referenced sub-routines.

    Args:
        algorithm_text: Full content of draft_api.md
        step: Step number (0-5)

    Returns:
        The relevant algorithm excerpt as a string.

    Raises:
        ValueError: If step is not in 0-5.
    """
    if step not in _ALGORITHM_STEP_RANGES:
        raise ValueError(f"Invalid step {step}; must be 0-5")

    lines = algorithm_text.splitlines()
    start, end = _ALGORITHM_STEP_RANGES[step]

    # Always include conventions (lines 1-107) as context
    section = lines[0:_ALGORITHM_CONVENTIONS_END]
    section.append("")
    section.extend(lines[start - 1:end])

    # Append relevant sub-routines
    for sr_start, sr_end in _SUBROUTINE_RANGES.get(step, []):
        section.append("")
        section.extend(lines[sr_start - 1:sr_end])

    return "\n".join(section)


# ═══════════════════════════════════════════════════════════════
# Schema section extraction (output_step0.yaml → per-step slices)
# ═══════════════════════════════════════════════════════════════

_SCHEMA_DRY_END = 23  # Lines 1–23: DRY conventions

_SCHEMA_STEP_SECTIONS = {
    # (header+example_start, header+example_end, field_summary_start, field_summary_end)
    0: (26, 81, 456, 476),
    1: (83, 454, 477, 522),
    2: (524, 808, 810, 855),
    3: (857, 952, 1235, 1262),    # field summary at file end
    4: (954, 1062, 1263, 1296),   # field summary at file end
    5: (1064, 1233, 1298, 1361),  # field summary at file end
}


def extract_schema_section(schema_text: str, step: int) -> str:
    """Extract the schema section for a given step (0-5).

    Returns DRY conventions (lines 1-23) + the step's annotated example
    + the step's field summary.

    Args:
        schema_text: Full content of output_step0.yaml
        step: Step number (0-5)

    Returns:
        The relevant schema excerpt as a string.

    Raises:
        ValueError: If step is not in 0-5.
    """
    if step not in _SCHEMA_STEP_SECTIONS:
        raise ValueError(f"Invalid step {step}; must be 0-5")

    lines = schema_text.splitlines()

    # Always include DRY conventions
    section = lines[0:_SCHEMA_DRY_END]

    ex_start, ex_end, fs_start, fs_end = _SCHEMA_STEP_SECTIONS[step]

    section.append("")
    section.extend(lines[ex_start - 1:ex_end])
    section.append("")
    section.extend(lines[fs_start - 1:fs_end])

    return "\n".join(section)


# ═══════════════════════════════════════════════════════════════
# Inter-step data extraction
# ═══════════════════════════════════════════════════════════════

def _safe_yaml_load(yaml_text: str, context: str) -> dict:
    """Parse YAML with an informative error message on failure."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML from {context}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict from {context}, got {type(data).__name__}")
    return data


def extract_confirmed_lemmas(step1_yaml: str) -> list[str]:
    """Extract confirmed lemma names from Step 1 output.

    Returns list of lemma strings where decision == "confirmed".
    Handles both dict-style and list-style per_lemma formats.
    """
    data = _safe_yaml_load(step1_yaml, "Step 1 output")
    s1 = data.get("step1_lemma_validation", {})

    confirmed = []

    # List style: per_lemma is a list of dicts with "lemma" key
    per_lemma = s1.get("per_lemma", [])
    if isinstance(per_lemma, list):
        for entry in per_lemma:
            if isinstance(entry, dict) and entry.get("decision") == "confirmed":
                lemma = entry.get("lemma", "")
                if lemma:
                    confirmed.append(lemma)
    # Dict style: per_lemma is a dict keyed by lemma name
    elif isinstance(per_lemma, dict):
        for lemma, info in per_lemma.items():
            if isinstance(info, dict) and info.get("decision") == "confirmed":
                confirmed.append(lemma)

    # Also check top-level "lemmas" dict (alternative format)
    if not confirmed:
        lemmas_dict = s1.get("lemmas", {})
        if isinstance(lemmas_dict, dict):
            for lemma, info in lemmas_dict.items():
                if isinstance(info, dict) and info.get("decision") == "confirmed":
                    confirmed.append(lemma)

    return confirmed


def extract_added_lemmas(step2_yaml: str) -> list[str]:
    """Extract added lemma names from Step 2 output.

    Returns list of candidate strings where decision == "added".
    """
    data = _safe_yaml_load(step2_yaml, "Step 2 output")
    s2 = data.get("step2_missing_lemmas", {})
    added = []

    per_candidate = s2.get("per_candidate", [])
    if isinstance(per_candidate, list):
        for entry in per_candidate:
            if isinstance(entry, dict) and entry.get("decision") == "added":
                candidate = entry.get("candidate", "")
                if candidate:
                    added.append(candidate)

    return added


def merge_lemma_lists(confirmed: list[str], added: list[str]) -> list[str]:
    """Merge confirmed (Step 1) and added (Step 2) lemmas, preserving order."""
    seen = set(confirmed)
    merged = list(confirmed)
    for lemma in added:
        if lemma not in seen:
            merged.append(lemma)
            seen.add(lemma)
    return merged


def extract_definition_review_flag(step1_yaml: str) -> bool:
    """Check if Step 1 flagged the definition for review."""
    data = _safe_yaml_load(step1_yaml, "Step 1 output (definition flag)")
    s1 = data.get("step1_lemma_validation", {})
    flags = s1.get("synset_flags", {})
    if isinstance(flags, dict):
        return bool(flags.get("definition_review_needed", False))
    return False


def extract_step0_evidence_summary(step0_yaml: str) -> str:
    """Extract a compact summary of Step 0 evidence for Steps 3 and 5.

    Returns YAML string with just confirm/expands texts per lemma
    (omitting full source details to keep input compact for CoT modules).
    """
    data = _safe_yaml_load(step0_yaml, "Step 0 output")
    s0 = data.get("step0_evidence", {})
    summary = {"evidence_summary": []}

    per_lemma = s0.get("per_lemma", [])
    if isinstance(per_lemma, list):
        entries = per_lemma
    elif isinstance(per_lemma, dict):
        # Convert dict format to list format
        entries = [{"lemma": k, **v} for k, v in per_lemma.items()]
    else:
        entries = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        lemma_summary = {"lemma": entry.get("lemma", "?")}

        if entry.get("confirm"):
            lemma_summary["confirm"] = [
                {"text": e.get("text", ""), "source": e.get("source", "")}
                for e in entry["confirm"]
                if isinstance(e, dict)
            ]
        if entry.get("contradicts"):
            lemma_summary["contradicts"] = [
                {"text": e.get("text", ""), "conflict": e.get("conflict", "")}
                for e in entry["contradicts"]
                if isinstance(e, dict)
            ]
        if entry.get("expands"):
            lemma_summary["expands"] = [
                {"text": e.get("text", ""), "addition": e.get("addition", "")}
                for e in entry["expands"]
                if isinstance(e, dict)
            ]
        if entry.get("evidence_status"):
            lemma_summary["evidence_status"] = entry["evidence_status"]

        summary["evidence_summary"].append(lemma_summary)

    return yaml.dump(summary, allow_unicode=True, default_flow_style=False)


def extract_candidate_evidence(evidence_yaml: str) -> str:
    """Extract evidence subset relevant to Step 2 (missing lemma discovery).

    Returns YAML string containing:
    - per_synset (step4_fts_keyword, step5_english_bridge, step9_specialized)
    - per_lemma.*.step8_reverse_lookup (reverse FTS — synonym candidate source)
    """
    data = _safe_yaml_load(evidence_yaml, "evidence YAML")
    subset = {}

    # Per-synset evidence (full)
    if "per_synset" in data:
        subset["per_synset"] = data["per_synset"]

    # Reverse lookup per lemma (synonym candidates)
    if "per_lemma" in data:
        reverse_lookups = {}
        for lemma_name, lemma_data in data["per_lemma"].items():
            if isinstance(lemma_data, dict) and "step8_reverse_lookup" in lemma_data:
                reverse_lookups[lemma_name] = {
                    "step8_reverse_lookup": lemma_data["step8_reverse_lookup"]
                }
        if reverse_lookups:
            subset["per_lemma_reverse"] = reverse_lookups

    return yaml.dump(subset, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=200)


def extract_examples_evidence(evidence_yaml: str) -> str:
    """Extract step6_examples from evidence for Step 5 citation extraction."""
    data = _safe_yaml_load(evidence_yaml, "evidence YAML (examples)")
    examples = {}
    if "per_lemma" in data:
        for lemma_name, lemma_data in data["per_lemma"].items():
            if isinstance(lemma_data, dict) and "step6_examples" in lemma_data:
                examples[lemma_name] = lemma_data["step6_examples"]

    return yaml.dump(
        {"examples_evidence": examples},
        allow_unicode=True, default_flow_style=False,
        sort_keys=False, width=200,
    )
