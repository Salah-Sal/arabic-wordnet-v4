#!/usr/bin/env python3
"""
assemble_prompts_v2.py — Slim evidence files and assemble review prompts.

Applies slim_evidence.py's gentle stripping plus additional redundancy rules
from the content-level analysis, then injects into the prompt template.

Processing pipeline per file:
  1. slim_artifact()     — drop step7, debug keys, _meta, empty/null values
  2. drop step2          — always ⊆ step1 (Rule 2)
  3. dedup step3         — across same-root lemmas (Rule 3)
  4. drop empty step9    — filters with 0 results (Rule 4)
  5. dedup definitions   — drop definitions list when == definitions_text (Rule 7)
  6. drop result_count   — derivable from len(entries) (Rule 15)
  7. simplify identity   — keep only lemma + is_multiword + components (Rule 17)
  8. assemble prompt     — inject into template with algorithm + output schema

Usage:
    python3 assemble_prompts_v2.py
    python3 assemble_prompts_v2.py --evidence-dir path/to/evidence
    python3 assemble_prompts_v2.py --output-dir path/to/output
    python3 assemble_prompts_v2.py --stats  # print before/after line counts
"""
from __future__ import annotations

import argparse
import gzip
import os
import sys
from pathlib import Path

import yaml

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_EVIDENCE_DIR = SCRIPT_DIR / "sample synsets with  dictionary evidenc"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "generated_prompts_v2"
TEMPLATE_PATH = SCRIPT_DIR / "prompt_template.md"
ALGORITHM_PATH = SCRIPT_DIR / "draft_api.md"
OUTPUT_SCHEMA_PATH = SCRIPT_DIR / "output_step0.yaml"

# ═══════════════════════════════════════════════════════════════════════════════
# From slim_evidence.py — debug keys to strip
# ═══════════════════════════════════════════════════════════════════════════════

STEP_DEBUG_KEYS = frozenset({
    "sql_template", "query_params", "excluded_entry_ids", "al_variants_searched",
})

_EMPTY_VALUES = (None, [], {}, "")

# Fields to keep per dictionary entry — linguistically relevant for the reviewer.
# Improves on v1's ENTRY_KEEP_FIELDS by adding type/attribution (for examples)
# and domain (for arabterm terminology entries).
ENTRY_KEEP_FIELDS = {
    "headword",
    "root",
    "definitions_text",
    "definitions",
    "examples",
    "plurals",
    "derived_forms",
    "cross_refs",
    "translation_en",
    "domain",
    "dict_name_ar",
    "dict_period",
    "dict_death_year",
}

# Step6 example objects have a different shape — keep these fields.
EXAMPLE_KEEP_FIELDS = {
    "headword",
    "text",
    "example_text",
    "type",
    "attribution",
    "dict_name_ar",
    "dict_key",
}


# ═══════════════════════════════════════════════════════════════════════════════
# YAML dumper with proper Arabic handling
# ═══════════════════════════════════════════════════════════════════════════════

class ArabicDumper(yaml.Dumper):
    pass


def _str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


ArabicDumper.add_representer(str, _str_representer)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_debug(d: dict) -> None:
    """Remove debug/plumbing keys (mutating)."""
    for k in STEP_DEBUG_KEYS:
        d.pop(k, None)


def _compact_entry(entry: dict) -> dict:
    """Keep only linguistically relevant fields, drop empty/null values."""
    out = {}
    for k in ENTRY_KEEP_FIELDS:
        if k not in entry:
            continue
        v = entry[k]
        if v in _EMPTY_VALUES:
            continue
        out[k] = v
    return out


def _compact_example(example: dict) -> dict:
    """Keep only relevant fields from a step6 example object."""
    out = {}
    for k in EXAMPLE_KEEP_FIELDS:
        if k not in example:
            continue
        v = example[k]
        if v in _EMPTY_VALUES:
            continue
        out[k] = v
    return out


def _compact_entries_in(container: dict, key: str = "entries") -> None:
    """Compact each entry in a list within a container."""
    items = container.get(key)
    if items and isinstance(items, list):
        container[key] = [e for e in (_compact_entry(i) for i in items) if e]


def _drop_result_count(d: dict) -> None:
    """Remove result_count — it's always == len(entries). (Rule 15)"""
    d.pop("result_count", None)


def _dedup_definitions(entry: dict) -> dict:
    """Drop definitions list when it duplicates definitions_text. (Rule 7)

    Keep definitions only for multi-sense entries where it adds information.
    """
    defs = entry.get("definitions")
    dtext = entry.get("definitions_text")

    if not defs or not isinstance(defs, list):
        return entry

    # Single sense: definitions[0].text == definitions_text → drop definitions
    if len(defs) == 1:
        sense = defs[0]
        if isinstance(sense, dict) and sense.get("text") == dtext:
            entry.pop("definitions", None)
    return entry


# ═══════════════════════════════════════════════════════════════════════════════
# Core processing — slim + additional rules
# ═══════════════════════════════════════════════════════════════════════════════

def _process_step(step: dict, entries_key: str = "entries") -> dict:
    """Apply debug strip, compact entries, dedup definitions, drop result_count."""
    _strip_debug(step)
    _drop_result_count(step)
    items = step.get(entries_key)
    if items and isinstance(items, list):
        step[entries_key] = [
            e for e in (_dedup_definitions(_compact_entry(i)) for i in items) if e
        ]
    return step


def _simplify_identity(identity: dict) -> dict:
    """Keep only lemma, is_multiword, and components (when multiword). (Rule 17)"""
    out = {"lemma": identity.get("lemma")}
    is_mw = identity.get("is_multiword", False)
    if is_mw:
        out["is_multiword"] = True
        comps = identity.get("components")
        if comps:
            out["components"] = comps
    return out


def _collect_roots(lemma_data: dict) -> set[str]:
    """Get the set of root keys from a lemma's step3_root_family."""
    s3 = lemma_data.get("step3_root_family", {})
    by_root = s3.get("by_root", {})
    return set(by_root.keys())


def process_evidence(art: dict) -> dict:
    """Full processing pipeline: slim + additional rules."""
    out = {}

    # ── synset: keep as-is ────────────────────────────────────────────────
    out["synset"] = art.get("synset", {})

    # ── per_lemma ─────────────────────────────────────────────────────────
    per_lemma_in = art.get("per_lemma", {})
    per_lemma_out = {}

    # Track which roots have already been emitted (for Rule 3 dedup)
    roots_emitted: set[str] = set()

    for lemma_key, ld in per_lemma_in.items():
        slim_ld = {}

        # Identity — simplify (Rule 17)
        if "identity" in ld:
            slim_ld["identity"] = _simplify_identity(ld["identity"])

        # step1_headword — keep, strip debug/empty
        s1 = ld.get("step1_headword")
        if s1:
            s1 = dict(s1)
            _process_step(s1)
            # by_component sub-entries
            by_comp = s1.get("by_component")
            if by_comp and isinstance(by_comp, dict):
                for comp_data in by_comp.values():
                    _process_step(comp_data)
                    # proclitic_stripped
                    ps = comp_data.get("proclitic_stripped")
                    if ps and isinstance(ps, dict):
                        _process_step(ps)
            if s1:
                slim_ld["step1_headword"] = s1

        # step2_definitions — DROP entirely (Rule 2: always ⊆ step1)
        # (not included)

        # step3_root_family — deduplicate across same-root lemmas (Rule 3)
        s3 = ld.get("step3_root_family")
        if s3:
            s3 = dict(s3)
            by_root_in = s3.get("by_root", {})
            by_root_out = {}
            deduped_roots = []

            for root_key, root_data in by_root_in.items():
                if root_key in roots_emitted:
                    # This root was already emitted under a previous lemma
                    deduped_roots.append(root_key)
                    continue
                roots_emitted.add(root_key)
                root_data = dict(root_data)
                _process_step(root_data)
                if root_data:
                    by_root_out[root_key] = root_data

            cs3 = {}
            if "roots_found" in s3:
                cs3["roots_found"] = s3["roots_found"]
            if by_root_out:
                cs3["by_root"] = by_root_out
            if deduped_roots:
                cs3["shared_roots"] = deduped_roots
            if cs3:
                slim_ld["step3_root_family"] = cs3

        # step6_examples — keep, compact with example-specific fields
        s6 = ld.get("step6_examples")
        if s6:
            s6 = dict(s6)
            _strip_debug(s6)
            _drop_result_count(s6)
            exs = s6.get("examples")
            if exs and isinstance(exs, list):
                s6["examples"] = [e for e in (_compact_example(i) for i in exs) if e]
            if s6.get("examples"):
                slim_ld["step6_examples"] = s6

        # step7_chronological — DROP (Rule 1: == step1)
        # (not included)

        # step8_reverse_lookup — keep, strip debug/empty
        s8 = ld.get("step8_reverse_lookup")
        if s8:
            s8 = dict(s8)
            _process_step(s8)
            if s8:
                slim_ld["step8_reverse_lookup"] = s8

        per_lemma_out[lemma_key] = slim_ld
    out["per_lemma"] = per_lemma_out

    # ── per_synset ────────────────────────────────────────────────────────
    ps_in = art.get("per_synset", {})
    ps_out = {}

    # step4_fts_keyword
    s4 = ps_in.get("step4_fts_keyword")
    if s4:
        s4 = dict(s4)
        _process_step(s4)
        if "keywords_extracted" in ps_in.get("step4_fts_keyword", {}):
            s4["keywords_extracted"] = ps_in["step4_fts_keyword"]["keywords_extracted"]
        if s4:
            ps_out["step4_fts_keyword"] = s4

    # step5_english_bridge
    s5 = ps_in.get("step5_english_bridge")
    if s5:
        s5 = dict(s5)
        _process_step(s5)
        if "english_terms_used" in ps_in.get("step5_english_bridge", {}):
            s5["english_terms_used"] = ps_in["step5_english_bridge"]["english_terms_used"]
        if s5:
            ps_out["step5_english_bridge"] = s5

    # step9_specialized — keep non-empty filters only (Rule 4)
    s9 = ps_in.get("step9_specialized")
    if s9:
        filters_in = s9.get("filters_applied", [])
        filters_out = []
        for filt in filters_in:
            filt = dict(filt)
            _strip_debug(filt)
            rc = filt.get("result_count", 0)
            entries = filt.get("entries", [])
            if rc == 0 and not entries:
                continue  # Rule 4: drop zero-result filters
            _drop_result_count(filt)
            _compact_entries_in(filt)
            filters_out.append(filt)
        if filters_out:
            ps_out["step9_specialized"] = {"filters_applied": filters_out}

    if ps_out:
        out["per_synset"] = ps_out

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# I/O and assembly
# ═══════════════════════════════════════════════════════════════════════════════

def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_evidence(path: Path) -> dict:
    """Read evidence file — handles both .yaml and .yaml.gz."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return yaml.load(f, Loader=_Loader)
    else:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.load(f, Loader=_Loader)


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        Dumper=ArabicDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=200,
    )


def extract_synset_id(filename: str) -> str:
    """Extract synset ID from filename."""
    return filename.replace(".evidence.yaml.gz", "").replace(".evidence.yaml", "")


def extract_synset_info(data: dict) -> str:
    """Extract synset summary from evidence data as a readable YAML block."""
    synset = data.get("synset", {})
    info = {
        "id": synset.get("id", ""),
        "ili": synset.get("ili", ""),
        "pos": synset.get("pos", ""),
        "lemmas": synset.get("lemmas", []),
        "definition_ar": synset.get("definition_ar", ""),
    }
    oewn = synset.get("oewn", {})
    if oewn:
        info["definition_en"] = oewn.get("definition_en", "")
        info["lemmas_en"] = oewn.get("lemmas_en", [])
    chain = synset.get("hypernym_chain", {})
    if chain and chain.get("path"):
        parent = chain["path"][0]
        info["direct_hypernym"] = {
            "id": parent.get("id", ""),
            "lemmas": parent.get("lemmas", []),
            "definition_ar": parent.get("definition_ar", ""),
        }
    return dump_yaml(info)


def assemble_prompt(template: str, algorithm: str, output_schema: str, synset_info: str, evidence: str) -> str:
    result = template.replace("{{SYNSET_INFO}}", synset_info)
    result = result.replace("{{ALGORITHM}}", algorithm)
    result = result.replace("{{OUTPUT_SCHEMA}}", output_schema)
    result = result.replace("{{EVIDENCE_DATA}}", evidence)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Slim evidence files and assemble review prompts (v2).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR,
        help="Directory with .evidence.yaml[.gz] files",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Directory for assembled prompts",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print detailed before/after stats",
    )
    args = parser.parse_args()

    # Load static components
    template = load_text(TEMPLATE_PATH)
    algorithm = load_text(ALGORITHM_PATH)
    output_schema = load_text(OUTPUT_SCHEMA_PATH)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find evidence files (plain or gzipped)
    evidence_files = sorted(
        f for f in args.evidence_dir.iterdir()
        if f.name.endswith(".evidence.yaml") or f.name.endswith(".evidence.yaml.gz")
    )

    if not evidence_files:
        print(f"No evidence files found in {args.evidence_dir}")
        sys.exit(1)

    print(f"Found {len(evidence_files)} evidence files")
    print(f"Output directory: {args.output_dir}")
    print()

    total_evidence_lines_before = 0
    total_evidence_lines_after = 0

    for filepath in evidence_files:
        synset_id = extract_synset_id(filepath.name)
        output_path = args.output_dir / f"{synset_id}.prompt.md"

        # Load raw evidence
        raw = read_evidence(filepath)

        # Stats: before
        if args.stats:
            raw_yaml = dump_yaml(raw)
            lines_before = raw_yaml.count("\n")
            total_evidence_lines_before += lines_before

        # Extract synset info + process evidence
        synset_info = extract_synset_info(raw)
        processed = process_evidence(raw)
        evidence_yaml = dump_yaml(processed)
        lines_after = evidence_yaml.count("\n")
        total_evidence_lines_after += lines_after

        # Assemble prompt
        prompt = assemble_prompt(template, algorithm, output_schema, synset_info, evidence_yaml)
        prompt_lines = prompt.count("\n")

        # Write
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        if args.stats:
            reduction = (1 - lines_after / lines_before) * 100 if lines_before else 0
            print(f"  {synset_id}: {lines_before:,} → {lines_after:,} lines "
                  f"({reduction:.0f}% reduction) → prompt {prompt_lines:,} lines")
        else:
            print(f"  {synset_id}: evidence {lines_after:,} lines → prompt {prompt_lines:,} lines")

    print(f"\nDone. {len(evidence_files)} prompts written to {args.output_dir}/")

    if args.stats:
        total_reduction = (
            (1 - total_evidence_lines_after / total_evidence_lines_before) * 100
            if total_evidence_lines_before else 0
        )
        print(f"\nTotal evidence: {total_evidence_lines_before:,} → "
              f"{total_evidence_lines_after:,} lines ({total_reduction:.0f}% reduction)")


if __name__ == "__main__":
    main()
