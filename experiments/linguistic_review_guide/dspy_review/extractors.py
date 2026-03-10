#!/usr/bin/env python3
"""Section and data extraction helpers for the Level 4 step-decomposed pipeline.

Provides two categories of functions:

1. **Section extractors**: Slice the monolithic algorithm (draft_api.md)
   and schema (output_step0.yaml) into per-step sections, so each
   pipeline module receives only the instructions relevant to its task.

2. **Inter-step data extractors**: Parse YAML outputs from completed steps and
   extract the specific data needed by downstream steps (e.g., confirmed lemma
   list from Step 1 → Steps 3-5).

All functions are pure Python — no LLM calls, no DSPy dependencies.
"""
from __future__ import annotations

import re

import yaml


# ═══════════════════════════════════════════════════════════════
# Algorithm section extraction (draft_api.md → per-step slices)
# ═══════════════════════════════════════════════════════════════

# Line ranges (1-indexed, inclusive) — verified against draft_api.md (1078 lines)
_ALGORITHM_CONVENTIONS_END = 107  # Lines 1–107: conventions + execution model

_ALGORITHM_STEP_RANGES = {
    0: (108, 157),       # الخطوة ٠: Evidence Extraction
    "0.5": None,         # الخطوة ٠٫٥: Lemma Generation — marker-based extraction
    1: (159, 326),       # الخطوة ١: Lemma Validation
    3: (331, 363),       # الخطوة ٣: Definition Processing
    4: (366, 410),       # الخطوة ٤: Relations Check
    5: (413, 513),       # الخطوة ٥: Enrichment & Culture
}

# Sub-routines referenced by specific steps
_SUBROUTINE_RANGES = {
    1: [(780, 861)],  # substitution_test + all authoring sub-routines
    3: [(782, 834)],  # author_terminological_def, author_linguistic_def, quality_check
}


def extract_algorithm_section(algorithm_text: str, step: int | str) -> str:
    """Extract the algorithm section for a given step (0, 0.5, 1-5).

    Returns the conventions block (lines 1-107) + the step's pseudocode block
    + any referenced sub-routines.

    Args:
        algorithm_text: Full content of draft_api.md
        step: Step number (0-5) or "0.5" for Step 0.5

    Returns:
        The relevant algorithm excerpt as a string.

    Raises:
        ValueError: If step is not a valid step identifier.
    """
    if step not in _ALGORITHM_STEP_RANGES:
        raise ValueError(f"Invalid step {step}; must be 0, '0.5', 1, or 3-5")

    lines = algorithm_text.splitlines()

    # Step 0.5 is appended at the end of draft_api.md — find it by marker
    if step == "0.5":
        marker = "// الخطوة ٠٫٥"
        section = lines[0:_ALGORITHM_CONVENTIONS_END]
        section.append("")
        found = False
        for i, line in enumerate(lines):
            if marker in line:
                section.extend(lines[i:])
                found = True
                break
        if not found:
            raise ValueError("Step 0.5 section not found in algorithm text")
        return "\n".join(section)

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
    3: (525, 620, 903, 930),     # field summary at file end
    4: (622, 730, 931, 964),     # field summary at file end
    5: (732, 901, 966, 1029),    # field summary at file end
}


def extract_schema_section(schema_text: str, step: int | str) -> str:
    """Extract the schema section for a given step (0, 0.5, 1-5).

    Returns DRY conventions (lines 1-23) + the step's annotated example
    + the step's field summary.

    Args:
        schema_text: Full content of output_step0.yaml
        step: Step number (0-5) or "0.5" for Step 0.5

    Returns:
        The relevant schema excerpt as a string.

    Raises:
        ValueError: If step is not a valid step identifier.
    """
    lines = schema_text.splitlines()

    # Step 0.5 is appended at the end of output_step0.yaml — find it by marker
    if step == "0.5":
        marker = "# الخطوة ٠٫٥"
        section = lines[0:_SCHEMA_DRY_END]
        section.append("")
        found = False
        for i, line in enumerate(lines):
            if marker in line:
                section.extend(lines[i:])
                found = True
                break
        if not found:
            raise ValueError("Step 0.5 section not found in schema text")
        return "\n".join(section)

    if step not in _SCHEMA_STEP_SECTIONS:
        raise ValueError(f"Invalid step {step}; must be 0, '0.5', 1, or 3-5")

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

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)```\s*$", re.DOTALL)


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences (```yaml ... ```) that some models wrap around output."""
    m = _FENCE_RE.match(text.strip())
    return m.group(1) if m else text


def _safe_yaml_load(yaml_text: str, context: str) -> dict:
    """Parse YAML with an informative error message on failure."""
    yaml_text = _strip_markdown_fences(yaml_text)
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


def extract_step1_added_lemmas(step1_yaml: str) -> list[str]:
    """Extract lemma names from Step 1's added_lemmas list.

    These are Step 0.5 candidates that passed Step 1 validation.
    Returns list of lemma strings.
    """
    data = _safe_yaml_load(step1_yaml, "Step 1 output")
    s1 = data.get("step1_lemma_validation", {})
    added = []
    for entry in s1.get("added_lemmas", []):
        if isinstance(entry, dict):
            lemma = entry.get("lemma", "")
            if lemma:
                added.append(lemma)
    return added


def extract_removed_escalated_lemmas(step1_yaml: str) -> dict[str, list[str]]:
    """Extract lemmas decided as 'removed' or 'escalated' from Step 1 output.

    Returns {"removed": [...], "escalated": [...]}.
    Handles both dict-style and list-style per_lemma formats.
    """
    data = _safe_yaml_load(step1_yaml, "Step 1 output")
    s1 = data.get("step1_lemma_validation", {})

    removed = []
    escalated = []

    per_lemma = s1.get("per_lemma", [])
    if isinstance(per_lemma, list):
        for entry in per_lemma:
            if not isinstance(entry, dict):
                continue
            lemma = entry.get("lemma", "")
            if not lemma:
                continue
            decision = entry.get("decision", "")
            if decision == "removed":
                removed.append(lemma)
            elif decision == "escalated":
                escalated.append(lemma)
    elif isinstance(per_lemma, dict):
        for lemma, info in per_lemma.items():
            if not isinstance(info, dict):
                continue
            decision = info.get("decision", "")
            if decision == "removed":
                removed.append(lemma)
            elif decision == "escalated":
                escalated.append(lemma)

    # Fallback: check top-level "lemmas" dict
    if not removed and not escalated:
        lemmas_dict = s1.get("lemmas", {})
        if isinstance(lemmas_dict, dict):
            for lemma, info in lemmas_dict.items():
                if not isinstance(info, dict):
                    continue
                decision = info.get("decision", "")
                if decision == "removed":
                    removed.append(lemma)
                elif decision == "escalated":
                    escalated.append(lemma)

    return {"removed": removed, "escalated": escalated}


def filter_synset_info(synset_info_yaml: str, active_lemmas: list[str]) -> str:
    """Filter synset_info to include only active (confirmed+added) lemmas.

    Parses the YAML, replaces the 'lemmas' list with only those in
    active_lemmas, re-serializes. This prevents the LLM from seeing
    removed/escalated lemmas in Steps 3-5.
    """
    data = yaml.safe_load(synset_info_yaml)
    if not isinstance(data, dict):
        return synset_info_yaml
    active_set = set(active_lemmas)
    original = data.get("lemmas", [])
    data["lemmas"] = [l for l in original if l in active_set]
    return yaml.dump(data, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=200)


def mask_synset_info(synset_info_yaml: str) -> str:
    """Remove lemma lists from synset_info for unbiased lemma generation (Step 0.5).

    Keeps: id, pos, definition_ar, definition_en, direct_hypernym (definition only).
    Removes: lemmas (Arabic), lemmas_en (English), hypernym lemmas.
    """
    data = yaml.safe_load(synset_info_yaml)
    if not isinstance(data, dict):
        return synset_info_yaml
    data.pop("lemmas", None)
    data.pop("lemmas_en", None)
    hyp = data.get("direct_hypernym", {})
    if isinstance(hyp, dict):
        hyp.pop("lemmas", None)
    return yaml.dump(data, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=200)


def extract_synset_level_evidence(evidence_yaml: str) -> str:
    """Extract synset-level evidence for Step 0.5 (no per-lemma data).

    Returns only per_synset sections (step4_fts_keyword, step5_english_bridge,
    step9_specialized). Excludes all per_lemma data to avoid revealing existing
    lemma names to Step 0.5.
    """
    data = _safe_yaml_load(evidence_yaml, "evidence YAML")
    subset = {}
    if "per_synset" in data:
        subset["per_synset"] = data["per_synset"]
    return yaml.dump(subset, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=200)


def extract_step05_candidates(step05_yaml: str) -> list[dict]:
    """Extract generated candidates from Step 0.5 output.

    Returns list of dicts: [{lemma, source, reasoning}, ...]
    where source is "evidence" or "knowledge".

    Handles both the expected format (step05_lemma_generation key) and
    fallback formats (lemmas key, flat list) that small models may produce.
    """
    data = _safe_yaml_load(step05_yaml, "Step 0.5 output")
    s05 = data.get("step05_lemma_generation", {})
    if not isinstance(s05, dict) or not s05:
        # Fallback: try to find candidates in alternative formats
        # Some models produce {lemmas: [{lemma: ..., evidence: [{source, reason}]}]}
        lemmas_list = data.get("lemmas", [])
        if isinstance(lemmas_list, list):
            candidates = []
            for item in lemmas_list:
                if isinstance(item, dict) and item.get("lemma"):
                    # Determine source: check nested evidence list or direct field
                    src = item.get("source", "") or ""
                    reason = item.get("reason", item.get("reasoning", ""))
                    ev_list = item.get("evidence", [])
                    if isinstance(ev_list, list) and ev_list:
                        ev0 = ev_list[0] if isinstance(ev_list[0], dict) else {}
                        src = src or ev0.get("source", "")
                        reason = reason or ev0.get("reason", ev0.get("reasoning", ""))
                    source = "knowledge" if "knowledge" in (src or "").lower() else "evidence"
                    candidates.append({
                        "lemma": item["lemma"],
                        "source": source,
                        "reasoning": reason,
                    })
            return candidates
        return []
    candidates = []
    for c in s05.get("evidence_candidates", []):
        if isinstance(c, dict) and c.get("lemma"):
            candidates.append({
                "lemma": c["lemma"],
                "source": "evidence",
                "reasoning": c.get("reasoning", ""),
            })
    for c in s05.get("knowledge_candidates", []):
        if isinstance(c, dict) and c.get("lemma"):
            candidates.append({
                "lemma": c["lemma"],
                "source": "knowledge",
                "reasoning": c.get("reasoning", ""),
            })
    return candidates


def extract_definition_review_flag(step1_yaml: str) -> bool:
    """Check if Step 1 flagged the definition for review."""
    data = _safe_yaml_load(step1_yaml, "Step 1 output (definition flag)")
    s1 = data.get("step1_lemma_validation", {})
    flags = s1.get("synset_flags", {})
    if isinstance(flags, dict):
        return bool(flags.get("definition_review_needed", False))
    return False


def extract_step0_evidence_summary(
    step0_yaml: str,
    active_lemmas: list[str] | None = None,
) -> str:
    """Extract a compact summary of Step 0 evidence for Steps 3 and 5.

    Returns YAML string with just confirm/expands texts per lemma
    (omitting full source details to keep input compact for CoT modules).

    Args:
        step0_yaml: Raw Step 0 YAML output.
        active_lemmas: If provided, only include evidence for these lemmas.
            Used to filter out removed/escalated lemmas from Step 1.
    """
    data = _safe_yaml_load(step0_yaml, "Step 0 output")
    s0 = data.get("step0_evidence", {})
    summary = {"evidence_summary": []}
    active_set = set(active_lemmas) if active_lemmas is not None else None

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
        lemma_name = entry.get("lemma", "?")
        if active_set is not None and lemma_name not in active_set:
            continue
        lemma_summary = {"lemma": lemma_name}

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


def extract_examples_evidence(
    evidence_yaml: str,
    active_lemmas: list[str] | None = None,
) -> str:
    """Extract step6_examples from evidence for Step 5 citation extraction.

    Args:
        evidence_yaml: Raw evidence YAML.
        active_lemmas: If provided, only include examples for these lemmas.
            Used to filter out removed/escalated lemmas from Step 1.
    """
    data = _safe_yaml_load(evidence_yaml, "evidence YAML (examples)")
    active_set = set(active_lemmas) if active_lemmas is not None else None
    examples = {}
    if "per_lemma" in data:
        for lemma_name, lemma_data in data["per_lemma"].items():
            if active_set is not None and lemma_name not in active_set:
                continue
            if isinstance(lemma_data, dict) and "step6_examples" in lemma_data:
                examples[lemma_name] = lemma_data["step6_examples"]

    return yaml.dump(
        {"examples_evidence": examples},
        allow_unicode=True, default_flow_style=False,
        sort_keys=False, width=200,
    )
