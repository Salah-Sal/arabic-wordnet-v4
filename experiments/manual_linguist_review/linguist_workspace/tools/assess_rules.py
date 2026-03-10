#!/usr/bin/env python3
"""
assess_rules.py — Validate 17 content-level redundancy rules against random evidence files.

Reads N random .evidence.yaml.gz files and checks each rule's empirical claims,
reporting per-rule verdicts with statistics.

Usage:
    python3 tools/assess_rules.py output/evidence/              # default 40 files
    python3 tools/assess_rules.py output/evidence/ --sample 100
    python3 tools/assess_rules.py output/evidence/ --files f1.gz f2.gz  # specific files
"""
from __future__ import annotations

import argparse
import gzip
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator

import yaml

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader

# ═══════════════════════════════════════════════════════════════════════════════
# Arabic text utilities (mirror collect_evidence.py for Rule 17 verification)
# ═══════════════════════════════════════════════════════════════════════════════

_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7-\u06E8\u06EA-\u06ED]")

def strip_diacritics(text: str) -> str:
    return _DIACRITICS.sub("", text)

_NORM_TABLE = str.maketrans({
    "\u0629": "\u0647",  # ة → ه
    "\u0649": "\u064A",  # ى → ي
    "\u0623": "\u0627",  # أ → ا
    "\u0625": "\u0627",  # إ → ا
    "\u0622": "\u0627",  # آ → ا
    "\u0671": "\u0627",  # ٱ → ا
})

def normalize_arabic(text: str) -> str:
    return strip_diacritics(text).translate(_NORM_TABLE)


# ═══════════════════════════════════════════════════════════════════════════════
# Entry iteration helpers
# ═══════════════════════════════════════════════════════════════════════════════

def iter_full_entries(art: dict) -> Iterator[tuple[str, dict]]:
    """Yield (step_name, entry_dict) for every full entry object in the artifact.

    Skips step2 (different shape) and step6 (example objects, not entries).
    """
    for lemma_key, ld in art.get("per_lemma", {}).items():
        for e in ld.get("step1_headword", {}).get("entries", []):
            yield ("step1", e)
        # step1 by_component entries
        by_comp = ld.get("step1_headword", {}).get("by_component")
        if by_comp and isinstance(by_comp, dict):
            for comp_key, comp_data in by_comp.items():
                for e in comp_data.get("entries", []):
                    yield ("step1_comp", e)
        for root_key, rd in ld.get("step3_root_family", {}).get("by_root", {}).items():
            for e in rd.get("entries", []):
                yield ("step3", e)
        for e in ld.get("step7_chronological", {}).get("entries", []):
            yield ("step7", e)
        for e in ld.get("step8_reverse_lookup", {}).get("entries", []):
            yield ("step8", e)
    ps = art.get("per_synset", {})
    for e in ps.get("step4_fts_keyword", {}).get("entries", []):
        yield ("step4", e)
    for e in ps.get("step5_english_bridge", {}).get("entries", []):
        yield ("step5", e)
    # step9
    s9 = ps.get("step9_specialized", {})
    for filt in s9.get("filters_applied", []):
        for e in filt.get("entries", []):
            yield ("step9", e)


def iter_step6_examples(art: dict) -> Iterator[dict]:
    """Yield step6 example objects (different shape from entries)."""
    for lemma_key, ld in art.get("per_lemma", {}).items():
        for ex in ld.get("step6_examples", {}).get("examples", []):
            yield ex


# ═══════════════════════════════════════════════════════════════════════════════
# Statistics accumulators
# ═══════════════════════════════════════════════════════════════════════════════

class Stats:
    """Simple counter/accumulator for a rule."""
    def __init__(self):
        self.counters: dict[str, int] = Counter()
        self.details: list[str] = []
        self.per_file: list[dict] = []


# ═══════════════════════════════════════════════════════════════════════════════
# Rule assessment functions
# ═══════════════════════════════════════════════════════════════════════════════

def assess_rule1(art: dict, s: Stats) -> None:
    """Rule 1: step7 entry_ids == step1 entry_ids for every lemma."""
    for lemma_key, ld in art.get("per_lemma", {}).items():
        s1_ids = {e.get("entry_id") for e in ld.get("step1_headword", {}).get("entries", [])}
        s7_ids = {e.get("entry_id") for e in ld.get("step7_chronological", {}).get("entries", [])}
        s.counters["lemmas_checked"] += 1
        if s1_ids == s7_ids:
            s.counters["lemmas_match"] += 1
        else:
            s.counters["lemmas_mismatch"] += 1
            diff = s7_ids - s1_ids
            s.details.append(f"  {lemma_key}: step7 has {len(diff)} extra IDs not in step1")


def assess_rule2(art: dict, s: Stats) -> None:
    """Rule 2: step2 entry_ids ⊆ step1 entry_ids for every lemma."""
    for lemma_key, ld in art.get("per_lemma", {}).items():
        s1_ids = {e.get("entry_id") for e in ld.get("step1_headword", {}).get("entries", [])}
        s2_ids = {e.get("entry_id") for e in ld.get("step2_definitions", {}).get("entries_with_senses", [])}
        s.counters["lemmas_checked"] += 1
        if s2_ids <= s1_ids:
            s.counters["lemmas_subset"] += 1
        else:
            s.counters["lemmas_not_subset"] += 1
            extra = s2_ids - s1_ids
            s.details.append(f"  {lemma_key}: step2 has {len(extra)} IDs not in step1")
        # Also track: how many step1 entries lack definitions (would not appear in step2)?
        s1_with_defs = sum(1 for e in ld.get("step1_headword", {}).get("entries", [])
                          if e.get("definitions_text", "").strip())
        s.counters["step1_total"] += len(s1_ids)
        s.counters["step1_with_defs"] += s1_with_defs
        s.counters["step2_total"] += len(s2_ids)


def assess_rule3(art: dict, s: Stats) -> None:
    """Rule 3: step3 root families overlap across lemmas sharing a root."""
    per_lemma = art.get("per_lemma", {})
    lemma_keys = list(per_lemma.keys())
    if len(lemma_keys) < 2:
        s.counters["single_lemma_files"] += 1
        return
    s.counters["multi_lemma_files"] += 1

    # Collect root → {lemma → set(entry_ids)} mapping
    root_to_lemma_ids: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for lemma_key in lemma_keys:
        ld = per_lemma[lemma_key]
        by_root = ld.get("step3_root_family", {}).get("by_root", {})
        for root_key, rd in by_root.items():
            ids = {e.get("entry_id") for e in rd.get("entries", [])}
            root_to_lemma_ids[root_key][lemma_key] = ids

    # For roots shared across 2+ lemmas, compute overlap
    for root_key, lemma_map in root_to_lemma_ids.items():
        if len(lemma_map) < 2:
            continue
        s.counters["shared_roots"] += 1
        all_id_sets = list(lemma_map.values())
        union = set().union(*all_id_sets)
        intersection = set.intersection(*all_id_sets)
        if union:
            overlap_pct = len(intersection) / len(union) * 100
            s.counters["overlap_sum"] += overlap_pct
            s.counters["overlap_count"] += 1
            s.counters["union_entries"] += len(union)
            s.counters["intersection_entries"] += len(intersection)


def assess_rule4(art: dict, s: Stats) -> None:
    """Rule 4: step9 almost never finds anything."""
    ps = art.get("per_synset", {})
    s9 = ps.get("step9_specialized", {})
    filters = s9.get("filters_applied", [])
    s.counters["files_checked"] += 1

    if not filters:
        s.counters["files_no_filters"] += 1
        return

    s.counters["total_filters"] += len(filters)
    all_empty = True
    for filt in filters:
        rc = filt.get("result_count", 0)
        if rc > 0:
            all_empty = False
            s.counters["filters_with_results"] += 1
            s.counters["filter_result_entries"] += rc
        else:
            s.counters["filters_empty"] += 1

    if all_empty:
        s.counters["files_all_empty"] += 1
    else:
        s.counters["files_with_results"] += 1


def assess_rule5(art: dict, s: Stats) -> None:
    """Rule 5: Arabterm entries carry no Arabic linguistic content."""
    for step_name, e in iter_full_entries(art):
        if e.get("dict_source_type") != "arabterm":
            continue
        s.counters["arabterm_total"] += 1
        if e.get("examples") == []: s.counters["arabterm_examples_empty"] += 1
        if e.get("plurals") == []: s.counters["arabterm_plurals_empty"] += 1
        if e.get("derived_forms") == []: s.counters["arabterm_derived_empty"] += 1
        if e.get("cross_refs") == []: s.counters["arabterm_cross_refs_empty"] += 1
        if not e.get("definitions_text", "").strip(): s.counters["arabterm_defs_text_empty"] += 1
        if e.get("dict_author") is None: s.counters["arabterm_author_null"] += 1
        if e.get("dict_death_year") is None: s.counters["arabterm_death_year_null"] += 1
        if e.get("provenance") is None: s.counters["arabterm_provenance_null"] += 1


def assess_rule6(art: dict, s: Stats) -> None:
    """Rule 6: cross_refs is empty 99.8% of the time. Also check related fields."""
    for step_name, e in iter_full_entries(art):
        s.counters["entries_total"] += 1
        if e.get("cross_refs") == []: s.counters["cross_refs_empty"] += 1
        elif e.get("cross_refs") is not None: s.counters["cross_refs_populated"] += 1
        if e.get("derived_forms") == []: s.counters["derived_forms_empty"] += 1
        elif e.get("derived_forms") is not None: s.counters["derived_forms_populated"] += 1
        if e.get("plurals") == []: s.counters["plurals_empty"] += 1
        elif e.get("plurals") is not None: s.counters["plurals_populated"] += 1
        if e.get("examples") == []: s.counters["examples_empty"] += 1
        elif e.get("examples") is not None: s.counters["examples_populated"] += 1


def assess_rule7(art: dict, s: Stats) -> None:
    """Rule 7: definitions_text == definitions[0].text for single-sense entries."""
    for step_name, e in iter_full_entries(art):
        defs = e.get("definitions", [])
        defs_text = e.get("definitions_text", "")
        if not defs:
            s.counters["no_definitions"] += 1
            continue
        if len(defs) == 1:
            s.counters["single_sense"] += 1
            sense_text = defs[0].get("text", "")
            if defs_text.strip() == sense_text.strip():
                s.counters["single_sense_match"] += 1
            else:
                s.counters["single_sense_mismatch"] += 1
        else:
            s.counters["multi_sense"] += 1


def assess_rule8(art: dict, s: Stats) -> None:
    """Rule 8: dict metadata fields are constant per dict_key."""
    META_FIELDS = ["dict_name_ar", "dict_name_en", "dict_source_type",
                   "dict_period", "dict_author", "dict_death_year"]
    by_key: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))

    for step_name, e in iter_full_entries(art):
        dk = e.get("dict_key")
        if not dk:
            continue
        for field in META_FIELDS:
            val = e.get(field)
            # Convert to hashable
            by_key[dk][field].add(str(val))

    s.counters["dict_keys_checked"] += len(by_key)
    for dk, fields in by_key.items():
        for field, vals in fields.items():
            if len(vals) > 1:
                s.counters["inconsistent_fields"] += 1
                s.details.append(f"  {dk}.{field}: {vals}")
            else:
                s.counters["consistent_fields"] += 1


def assess_rule9(art: dict, s: Stats) -> None:
    """Rule 9: dict_period is redundant with source type."""
    combos: Counter = Counter()
    for step_name, e in iter_full_entries(art):
        src = e.get("dict_source_type", "?")
        period = e.get("dict_period", "?")
        combos[(src, period)] += 1
    for (src, period), count in combos.items():
        s.counters[f"{src}:{period}"] += count
        s.counters["total_entries"] += count


def assess_rule10(art: dict, s: Stats) -> None:
    """Rule 10: hawramani_post_id and hawramani_slug are always null."""
    for step_name, e in iter_full_entries(art):
        if e.get("dict_source_type") != "hawramani":
            continue
        s.counters["hawramani_total"] += 1
        prov = e.get("provenance")
        if prov is None:
            s.counters["provenance_null"] += 1
            continue
        if prov.get("hawramani_post_id") is None:
            s.counters["post_id_null"] += 1
        else:
            s.counters["post_id_set"] += 1
        if prov.get("hawramani_slug") is None:
            s.counters["slug_null"] += 1
        else:
            s.counters["slug_set"] += 1


def assess_rule11(art: dict, s: Stats) -> None:
    """Rule 11: form null 97.5%, pos null 91%, is_partial always 0."""
    for step_name, e in iter_full_entries(art):
        s.counters["entries_total"] += 1
        if e.get("form") is None: s.counters["form_null"] += 1
        if e.get("pos") is None: s.counters["pos_null"] += 1
        if e.get("is_partial") == 0: s.counters["is_partial_zero"] += 1
        elif e.get("is_partial") is not None: s.counters["is_partial_nonzero"] += 1


def assess_rule12(art: dict, s: Stats) -> None:
    """Rule 12: provenance is null or mostly-null by source type."""
    PROV_FIELDS = ["page_number", "page_file", "entry_index", "volume",
                   "hawramani_post_id", "hawramani_slug", "source_uri"]
    for step_name, e in iter_full_entries(art):
        src = e.get("dict_source_type", "?")
        prov = e.get("provenance")
        s.counters[f"{src}_total"] += 1
        if prov is None:
            s.counters[f"{src}_prov_null"] += 1
            continue
        for field in PROV_FIELDS:
            if prov.get(field) is not None:
                s.counters[f"{src}_prov_{field}_set"] += 1
            else:
                s.counters[f"{src}_prov_{field}_null"] += 1


def assess_rule13(art: dict, s: Stats) -> None:
    """Rule 13: sql_template is the same string repeated per query block."""
    templates: dict[str, set] = defaultdict(set)
    count = 0

    for lemma_key, ld in art.get("per_lemma", {}).items():
        for step_key in ["step1_headword", "step2_definitions", "step6_examples",
                         "step7_chronological", "step8_reverse_lookup"]:
            st = ld.get(step_key, {}).get("sql_template")
            if st:
                templates[step_key].add(st)
                count += 1
        # step3 by_root
        for root_key, rd in ld.get("step3_root_family", {}).get("by_root", {}).items():
            st = rd.get("sql_template")
            if st:
                templates["step3_by_root"].add(st)
                count += 1

    ps = art.get("per_synset", {})
    for step_key in ["step4_fts_keyword", "step5_english_bridge"]:
        st = ps.get(step_key, {}).get("sql_template")
        if st:
            templates[step_key].add(st)
            count += 1

    s.counters["template_occurrences"] += count
    for step_key, unique_sqls in templates.items():
        s.counters[f"{step_key}_unique"] = max(s.counters.get(f"{step_key}_unique", 0), len(unique_sqls))
    # Total unique across all steps
    all_unique = set()
    for v in templates.values():
        all_unique |= v
    s.counters["total_unique_templates"] += len(all_unique)


def assess_rule14(art: dict, s: Stats) -> None:
    """Rule 14: _meta is identical across files."""
    meta = art.get("_meta", {})
    s.counters["files_checked"] += 1
    # Capture key values (excluding generated_at)
    db_path = str(meta.get("db_path", ""))
    db_stats = str(meta.get("db_stats", {}))
    schema = str(meta.get("schema_version", ""))
    key = f"{schema}|{db_path}|{db_stats}"
    s.counters[f"meta_key:{key}"] += 1


def assess_rule15(art: dict, s: Stats) -> None:
    """Rule 15: result_count always equals len(entries)."""
    for lemma_key, ld in art.get("per_lemma", {}).items():
        # step1
        s1 = ld.get("step1_headword", {})
        _check_rc(s1, "entries", s, "step1")
        # step2
        s2 = ld.get("step2_definitions", {})
        _check_rc(s2, "entries_with_senses", s, "step2")
        # step3 by_root
        for root_key, rd in ld.get("step3_root_family", {}).get("by_root", {}).items():
            _check_rc(rd, "entries", s, "step3")
        # step6
        s6 = ld.get("step6_examples", {})
        _check_rc(s6, "examples", s, "step6")
        # step7
        s7 = ld.get("step7_chronological", {})
        _check_rc(s7, "entries", s, "step7")
        # step8
        s8 = ld.get("step8_reverse_lookup", {})
        _check_rc(s8, "entries", s, "step8")

    ps = art.get("per_synset", {})
    _check_rc(ps.get("step4_fts_keyword", {}), "entries", s, "step4")
    _check_rc(ps.get("step5_english_bridge", {}), "entries", s, "step5")


def _check_rc(container: dict, list_key: str, s: Stats, label: str) -> None:
    rc = container.get("result_count")
    items = container.get(list_key, [])
    if rc is None:
        return
    s.counters["rc_checks"] += 1
    if rc == len(items):
        s.counters["rc_match"] += 1
    else:
        s.counters["rc_mismatch"] += 1
        s.details.append(f"  {label}: result_count={rc} but len({list_key})={len(items)}")


def assess_rule16(art: dict, s: Stats) -> None:
    """Rule 16: excluded_entry_ids in steps 4 and 5 can be large."""
    ps = art.get("per_synset", {})
    for step_key in ["step4_fts_keyword", "step5_english_bridge"]:
        excl = ps.get(step_key, {}).get("excluded_entry_ids", [])
        if excl:
            s.counters[f"{step_key}_excl_total"] += 1
            s.counters[f"{step_key}_excl_sum"] += len(excl)
            cur_max = s.counters.get(f"{step_key}_excl_max", 0)
            s.counters[f"{step_key}_excl_max"] = max(cur_max, len(excl))
            cur_min = s.counters.get(f"{step_key}_excl_min", 999999)
            s.counters[f"{step_key}_excl_min"] = min(cur_min, len(excl))


def assess_rule17(art: dict, s: Stats) -> None:
    """Rule 17: identity.lemma_bare and lemma_norm are derivable from lemma."""
    for lemma_key, ld in art.get("per_lemma", {}).items():
        ident = ld.get("identity", {})
        lemma = ident.get("lemma", "")
        bare = ident.get("lemma_bare", "")
        norm = ident.get("lemma_norm", "")
        is_mw = ident.get("is_multiword", False)
        components = ident.get("components", [])

        s.counters["lemmas_checked"] += 1

        # Check lemma_bare = strip_diacritics(lemma)
        computed_bare = strip_diacritics(lemma)
        if computed_bare == bare:
            s.counters["bare_match"] += 1
        else:
            s.counters["bare_mismatch"] += 1

        # Check lemma_norm = normalize_arabic(lemma)
        computed_norm = normalize_arabic(lemma)
        if computed_norm == norm:
            s.counters["norm_match"] += 1
        else:
            s.counters["norm_mismatch"] += 1

        # Check: components == [] when is_multiword == false
        if not is_mw and components == []:
            s.counters["components_consistent"] += 1
        elif not is_mw and components != []:
            s.counters["components_inconsistent"] += 1
        elif is_mw:
            s.counters["multiword_lemmas"] += 1


# ═══════════════════════════════════════════════════════════════════════════════
# Report formatting
# ═══════════════════════════════════════════════════════════════════════════════

def pct(num: int, denom: int) -> str:
    if denom == 0:
        return "N/A"
    return f"{num / denom * 100:.1f}%"


def report(all_stats: dict[int, Stats], n_files: int) -> None:
    sep = "=" * 65
    print(f"\n{sep}")
    print(f"   Evidence YAML Redundancy Rules — Assessment Report")
    print(f"   Files sampled: {n_files} / 120,630")
    print(sep)

    # Rule 1
    s = all_stats[1]
    total = s.counters["lemmas_checked"]
    match = s.counters["lemmas_match"]
    print(f"\nRule 1: step7 = step1 (drop step7)")
    print(f"  Factual: {'CONFIRMED' if match == total else 'PARTIAL'} — {match}/{total} lemmas match ({pct(match, total)})")
    print(f"  Safety:  Safe — neither consumer reads step7")
    print(f"  Status:  Already handled by slim_evidence.py R1")
    if s.details:
        for d in s.details[:3]: print(d)

    # Rule 2
    s = all_stats[2]
    total = s.counters["lemmas_checked"]
    subset = s.counters["lemmas_subset"]
    print(f"\nRule 2: step2 subset of step1 (drop step2)")
    print(f"  Factual: {'CONFIRMED' if subset == total else 'PARTIAL'} — {subset}/{total} lemmas are subsets ({pct(subset, total)})")
    print(f"  Detail:  step1 entries: {s.counters['step1_total']}, with defs: {s.counters['step1_with_defs']}, step2 entries: {s.counters['step2_total']}")
    print(f"  Safety:  UNSAFE — fill_prompt.py reads step2.entries_with_senses[].senses[].text")
    print(f"  Note:    Step2 provides structured sense data that definitions_text does not")
    if s.details:
        for d in s.details[:3]: print(d)

    # Rule 3
    s = all_stats[3]
    single = s.counters["single_lemma_files"]
    multi = s.counters["multi_lemma_files"]
    shared = s.counters["shared_roots"]
    avg_overlap = s.counters["overlap_sum"] / s.counters["overlap_count"] if s.counters["overlap_count"] else 0
    print(f"\nRule 3: step3 duplicated across lemmas sharing a root")
    print(f"  Files:   {single} single-lemma, {multi} multi-lemma")
    print(f"  Shared roots found: {shared}")
    if s.counters["overlap_count"]:
        print(f"  Avg overlap: {avg_overlap:.1f}% (union: {s.counters['union_entries']}, intersection: {s.counters['intersection_entries']})")
    else:
        print(f"  No shared roots found across lemmas")
    print(f"  Safety:  Safe if surviving copy accessible. Requires structural change (synset-level step3)")

    # Rule 4
    s = all_stats[4]
    total = s.counters["files_checked"]
    no_filters = s.counters["files_no_filters"]
    all_empty = s.counters["files_all_empty"]
    with_results = s.counters["files_with_results"]
    empty_rate = (no_filters + all_empty)
    print(f"\nRule 4: step9 almost never finds anything (drop it)")
    print(f"  Files with no filters: {no_filters}/{total}")
    print(f"  Files with all-empty filters: {all_empty}/{total}")
    print(f"  Files with some results: {with_results}/{total}")
    print(f"  Empty rate: {pct(empty_rate, total)}")
    if s.counters["total_filters"]:
        print(f"  Filters: {s.counters['filters_empty']} empty, {s.counters['filters_with_results']} with results")
    print(f"  Safety:  Safe — neither consumer reads step9")
    print(f"  Status:  Already handled by slim_evidence.py R2")

    # Rule 5
    s = all_stats[5]
    t = s.counters["arabterm_total"]
    if t:
        print(f"\nRule 5: Arabterm entries carry no Arabic linguistic content")
        print(f"  Arabterm entries checked: {t}")
        print(f"  examples=[]:       {pct(s.counters['arabterm_examples_empty'], t)}")
        print(f"  plurals=[]:        {pct(s.counters['arabterm_plurals_empty'], t)}")
        print(f"  derived_forms=[]:  {pct(s.counters['arabterm_derived_empty'], t)}")
        print(f"  cross_refs=[]:     {pct(s.counters['arabterm_cross_refs_empty'], t)}")
        print(f"  definitions_text='': {pct(s.counters['arabterm_defs_text_empty'], t)}")
        print(f"  dict_author=null:  {pct(s.counters['arabterm_author_null'], t)}")
        print(f"  dict_death_year=null: {pct(s.counters['arabterm_death_year_null'], t)}")
        print(f"  provenance=null:   {pct(s.counters['arabterm_provenance_null'], t)}")
        print(f"  Safety:  Safe — empty fields can be omitted")
        print(f"  Status:  Partially handled by slim_evidence.py R3+R4")
    else:
        print(f"\nRule 5: Arabterm entries — no arabterm entries found in sample")

    # Rule 6
    s = all_stats[6]
    t = s.counters["entries_total"]
    print(f"\nRule 6: cross_refs empty 99.8% of the time")
    if t:
        print(f"  Entries checked: {t}")
        print(f"  cross_refs empty:     {s.counters['cross_refs_empty']}/{t} ({pct(s.counters['cross_refs_empty'], t)})")
        print(f"  cross_refs populated: {s.counters['cross_refs_populated']}")
        print(f"  derived_forms empty:  {pct(s.counters['derived_forms_empty'], t)}")
        print(f"  plurals empty:        {pct(s.counters['plurals_empty'], t)}")
        print(f"  examples empty:       {pct(s.counters['examples_empty'], t)}")
    print(f"  Safety:  Safe — consumers never read enriched child tables")
    print(f"  Status:  Already handled by slim_evidence.py R3")

    # Rule 7
    s = all_stats[7]
    total_single = s.counters["single_sense"]
    match = s.counters["single_sense_match"]
    print(f"\nRule 7: definitions_text == definitions[0].text for single-sense entries")
    print(f"  No definitions: {s.counters['no_definitions']}")
    print(f"  Single-sense: {total_single} (match: {match}, mismatch: {s.counters['single_sense_mismatch']})")
    print(f"  Multi-sense: {s.counters['multi_sense']}")
    if total_single:
        print(f"  Match rate: {pct(match, total_single)}")
    print(f"  Safety:  Safe — enriched definitions[] never read by consumers")
    print(f"  Status:  Already handled by slim_evidence.py R3")

    # Rule 8
    s = all_stats[8]
    print(f"\nRule 8: Dict metadata fields are constant per dict_key")
    print(f"  Dict keys checked: {s.counters['dict_keys_checked']}")
    print(f"  Consistent fields: {s.counters['consistent_fields']}")
    print(f"  Inconsistent fields: {s.counters['inconsistent_fields']}")
    if s.details:
        for d in s.details[:5]: print(d)
    print(f"  Safety:  Requires consumer code changes to use lookup table")

    # Rule 9
    s = all_stats[9]
    print(f"\nRule 9: dict_period redundant with source type")
    print(f"  Cross-tab (source_type : period → count):")
    for key in sorted(k for k in s.counters if ":" in k and k != "total_entries"):
        print(f"    {key}: {s.counters[key]}")
    print(f"  Safety:  dict_period IS consumed by prepare_synset.py. Not safe to drop without code changes")

    # Rule 10
    s = all_stats[10]
    t = s.counters["hawramani_total"]
    print(f"\nRule 10: hawramani_post_id and hawramani_slug always null")
    if t:
        # Subtract provenance_null from total to get those with provenance
        with_prov = t - s.counters["provenance_null"]
        print(f"  Hawramani entries: {t} (with provenance: {with_prov})")
        if with_prov:
            print(f"  post_id null: {s.counters['post_id_null']}/{with_prov} ({pct(s.counters['post_id_null'], with_prov)})")
            print(f"  slug null:    {s.counters['slug_null']}/{with_prov} ({pct(s.counters['slug_null'], with_prov)})")
            print(f"  post_id set:  {s.counters['post_id_set']}")
            print(f"  slug set:     {s.counters['slug_set']}")
    else:
        print(f"  No hawramani entries in sample")
    print(f"  Safety:  Safe — consumers never read provenance")
    print(f"  Status:  Already handled by slim_evidence.py R3")

    # Rule 11
    s = all_stats[11]
    t = s.counters["entries_total"]
    print(f"\nRule 11: form null ~97.5%, pos null ~91%, is_partial always 0")
    if t:
        print(f"  Entries: {t}")
        print(f"  form null:      {pct(s.counters['form_null'], t)}")
        print(f"  pos null:       {pct(s.counters['pos_null'], t)}")
        print(f"  is_partial=0:   {pct(s.counters['is_partial_zero'], t)}")
        print(f"  is_partial!=0:  {s.counters['is_partial_nonzero']}")
    print(f"  Safety:  Safe — consumers never read form/pos/is_partial")
    print(f"  Status:  Already handled by slim_evidence.py R4")

    # Rule 12
    s = all_stats[12]
    print(f"\nRule 12: provenance mostly null by source type")
    for src in ["arabterm", "hawramani", "ocr"]:
        t = s.counters.get(f"{src}_total", 0)
        if not t: continue
        null = s.counters.get(f"{src}_prov_null", 0)
        print(f"  {src} ({t} entries): provenance=null: {pct(null, t)}")
        if null < t:
            for field in ["page_number", "page_file", "entry_index", "volume",
                          "hawramani_post_id", "hawramani_slug", "source_uri"]:
                s_count = s.counters.get(f"{src}_prov_{field}_set", 0)
                if s_count:
                    print(f"    {field}: {s_count}/{t - null} non-null provenance entries")
    print(f"  Safety:  Safe — consumers never read provenance")
    print(f"  Status:  Already handled by slim_evidence.py R3")

    # Rule 13
    s = all_stats[13]
    print(f"\nRule 13: sql_template repeated per query block")
    print(f"  Total sql_template occurrences: {s.counters['template_occurrences']}")
    print(f"  Total unique templates: {s.counters['total_unique_templates']}")
    for key in sorted(k for k in s.counters if k.endswith("_unique")):
        print(f"    {key}: {s.counters[key]}")
    print(f"  Safety:  Safe — consumers never read sql_template")
    print(f"  Status:  Already handled by slim_evidence.py R5")

    # Rule 14
    s = all_stats[14]
    meta_keys = [k for k in s.counters if k.startswith("meta_key:")]
    print(f"\nRule 14: _meta is identical across files")
    print(f"  Files checked: {s.counters['files_checked']}")
    print(f"  Unique _meta signatures: {len(meta_keys)}")
    for mk in meta_keys:
        print(f"    {mk.replace('meta_key:', '')}: {s.counters[mk]} files")
    print(f"  Safety:  Safe — consumers never read _meta")
    print(f"  Status:  Already handled by slim_evidence.py R6")

    # Rule 15
    s = all_stats[15]
    total = s.counters["rc_checks"]
    match = s.counters["rc_match"]
    print(f"\nRule 15: result_count == len(entries)")
    print(f"  Checks: {total}, match: {match}, mismatch: {s.counters['rc_mismatch']}")
    if total:
        print(f"  Match rate: {pct(match, total)}")
    if s.details:
        for d in s.details[:5]: print(d)
    print(f"  Safety:  result_count IS consumed by prepare_synset.py. Derivable but not safe to drop without code change")

    # Rule 16
    s = all_stats[16]
    print(f"\nRule 16: excluded_entry_ids can be large")
    for step_key in ["step4_fts_keyword", "step5_english_bridge"]:
        t = s.counters.get(f"{step_key}_excl_total", 0)
        if t:
            avg = s.counters.get(f"{step_key}_excl_sum", 0) / t
            print(f"  {step_key}: {t} files with exclusion lists")
            print(f"    min: {s.counters.get(f'{step_key}_excl_min', 0)}, max: {s.counters.get(f'{step_key}_excl_max', 0)}, avg: {avg:.0f}")
        else:
            print(f"  {step_key}: no exclusion lists found")
    print(f"  Safety:  Safe — consumers never read excluded_entry_ids")
    print(f"  Status:  Already handled by slim_evidence.py R5")

    # Rule 17
    s = all_stats[17]
    total = s.counters["lemmas_checked"]
    print(f"\nRule 17: identity.lemma_bare and lemma_norm are derivable")
    print(f"  Lemmas checked: {total}")
    if total:
        print(f"  lemma_bare matches strip_diacritics(): {pct(s.counters['bare_match'], total)}")
        print(f"  lemma_norm matches normalize_arabic(): {pct(s.counters['norm_match'], total)}")
        print(f"  components=[] when not multiword: {s.counters['components_consistent']}/{s.counters['components_consistent'] + s.counters.get('components_inconsistent', 0)}")
        print(f"  Multiword lemmas: {s.counters['multiword_lemmas']}")
    print(f"  Safety:  Low impact. Identity block is small.")

    # Summary
    print(f"\n{sep}")
    print(f"   Summary")
    print(sep)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Validate 17 redundancy rules against random evidence files.",
    )
    parser.add_argument("input_dir", help="Directory containing .evidence.yaml.gz files")
    parser.add_argument("--sample", type=int, default=40,
                        help="Number of random files to sample (default: 40)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--files", nargs="*",
                        help="Specific files to assess (overrides --sample)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.files:
        files = [Path(f) for f in args.files]
    else:
        all_files = sorted(f for f in input_dir.iterdir()
                           if f.name.endswith(".evidence.yaml.gz"))
        random.seed(args.seed)
        files = random.sample(all_files, min(args.sample, len(all_files)))
        print(f"Sampled {len(files)} of {len(all_files)} files (seed={args.seed})", file=sys.stderr)

    # Initialize stats for all 17 rules
    all_stats: dict[int, Stats] = {i: Stats() for i in range(1, 18)}

    # Assess functions
    assessors = [
        (1, assess_rule1), (2, assess_rule2), (3, assess_rule3),
        (4, assess_rule4), (5, assess_rule5), (6, assess_rule6),
        (7, assess_rule7), (8, assess_rule8), (9, assess_rule9),
        (10, assess_rule10), (11, assess_rule11), (12, assess_rule12),
        (13, assess_rule13), (14, assess_rule14), (15, assess_rule15),
        (16, assess_rule16), (17, assess_rule17),
    ]

    for i, fpath in enumerate(files, 1):
        print(f"\r  [{i}/{len(files)}] {fpath.name}...", end="", file=sys.stderr, flush=True)
        try:
            with gzip.open(fpath, "rt", encoding="utf-8") as f:
                art = yaml.load(f, Loader=_Loader)
        except Exception as e:
            print(f"\n  WARN: {fpath.name}: {e}", file=sys.stderr)
            continue

        for rule_num, fn in assessors:
            try:
                fn(art, all_stats[rule_num])
            except Exception as e:
                all_stats[rule_num].details.append(f"  ERROR in {fpath.name}: {e}")

    print(file=sys.stderr)  # newline after progress
    report(all_stats, len(files))


if __name__ == "__main__":
    main()
