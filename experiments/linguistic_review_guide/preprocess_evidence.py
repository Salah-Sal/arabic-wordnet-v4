#!/usr/bin/env python3
"""
Preprocess .evidence.yaml files for prompt injection.

Strips database metadata, SQL templates, internal IDs, and empty fields
to produce a compact YAML suitable for LLM context windows.

Typical compression: 80-90% (90K lines → 5-10K lines).

Usage:
    python preprocess_evidence.py input.evidence.yaml -o compact.yaml
    python preprocess_evidence.py input.evidence.yaml > compact.yaml
"""

import argparse
import sys
import yaml


# Fields to keep per dictionary entry (everything else is stripped)
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
    "dict_name_ar",
    "dict_period",
    "dict_death_year",
}

# Section-level keys to strip (SQL boilerplate, query metadata)
SECTION_STRIP_KEYS = {
    "sql_template",
    "query_params",
    "al_variants_searched",
    "excluded_entry_ids",
}


def compact_entry(entry: dict) -> dict:
    """Strip an entry down to linguistically relevant fields."""
    compact = {}
    for key in ENTRY_KEEP_FIELDS:
        if key not in entry:
            continue
        val = entry[key]
        # Skip null/empty values
        if val is None:
            continue
        if isinstance(val, list) and len(val) == 0:
            continue
        if isinstance(val, str) and val == "":
            continue
        # For definitions list, keep only the text
        if key == "definitions" and isinstance(val, list):
            texts = [d["text"] for d in val if isinstance(d, dict) and d.get("text")]
            if not texts:
                continue
            # If definitions_text already captures the same content, skip
            if len(texts) == 1 and entry.get("definitions_text") == texts[0]:
                continue
            compact[key] = texts
            continue
        compact[key] = val
    return compact


def compact_entries_list(entries: list) -> list:
    """Compact a list of entries, dropping empties."""
    result = []
    for e in entries:
        c = compact_entry(e)
        if c:
            result.append(c)
    return result


def compact_section(section: dict, entries_key: str = "entries") -> dict:
    """Strip a section (step1_headword, etc.) to just result_count + compact entries."""
    out = {}
    if "result_count" in section:
        out["result_count"] = section["result_count"]
    if entries_key in section:
        entries = section[entries_key]
        if isinstance(entries, list) and entries:
            compacted = compact_entries_list(entries)
            if compacted:
                out[entries_key] = compacted
    return out


def process_per_lemma(per_lemma: dict) -> dict:
    """Process all lemmas, compacting each section."""
    result = {}
    for lemma_name, lemma_data in per_lemma.items():
        compact_lemma = {}

        # identity: keep as-is (already small)
        if "identity" in lemma_data:
            compact_lemma["identity"] = lemma_data["identity"]

        # step1_headword
        if "step1_headword" in lemma_data:
            s1 = lemma_data["step1_headword"]
            cs1 = compact_section(s1, "entries")
            # Handle by_component for MWEs
            if "by_component" in s1 and isinstance(s1["by_component"], dict):
                by_comp = {}
                for comp_name, comp_data in s1["by_component"].items():
                    cc = compact_section(comp_data, "entries")
                    if cc:
                        by_comp[comp_name] = cc
                if by_comp:
                    cs1["by_component"] = by_comp
            if cs1:
                compact_lemma["step1_headword"] = cs1

        # step2_definitions
        if "step2_definitions" in lemma_data:
            cs2 = compact_section(lemma_data["step2_definitions"], "entries_with_senses")
            if cs2:
                compact_lemma["step2_definitions"] = cs2

        # step3_root_family
        if "step3_root_family" in lemma_data:
            s3 = lemma_data["step3_root_family"]
            cs3 = {}
            if "roots_found" in s3:
                cs3["roots_found"] = s3["roots_found"]
            if "roots_from_components" in s3:
                cs3["roots_from_components"] = s3["roots_from_components"]
            if "by_root" in s3 and isinstance(s3["by_root"], dict):
                by_root = {}
                for root_name, root_data in s3["by_root"].items():
                    cr = compact_section(root_data, "entries")
                    if cr:
                        by_root[root_name] = cr
                if by_root:
                    cs3["by_root"] = by_root
            if cs3:
                compact_lemma["step3_root_family"] = cs3

        # step6_examples
        if "step6_examples" in lemma_data:
            cs6 = compact_section(lemma_data["step6_examples"], "examples")
            if cs6:
                compact_lemma["step6_examples"] = cs6

        # step7_chronological
        if "step7_chronological" in lemma_data:
            cs7 = compact_section(lemma_data["step7_chronological"], "entries")
            if cs7:
                compact_lemma["step7_chronological"] = cs7

        # step8_reverse_lookup
        if "step8_reverse_lookup" in lemma_data:
            cs8 = compact_section(lemma_data["step8_reverse_lookup"], "entries")
            if cs8:
                compact_lemma["step8_reverse_lookup"] = cs8

        result[lemma_name] = compact_lemma
    return result


def process_per_synset(per_synset: dict) -> dict:
    """Process synset-level search sections."""
    result = {}

    # step4_fts_keyword
    if "step4_fts_keyword" in per_synset:
        s4 = per_synset["step4_fts_keyword"]
        cs4 = compact_section(s4, "entries")
        if "keywords_extracted" in s4:
            cs4["keywords_extracted"] = s4["keywords_extracted"]
        if cs4:
            result["step4_fts_keyword"] = cs4

    # step5_english_bridge
    if "step5_english_bridge" in per_synset:
        s5 = per_synset["step5_english_bridge"]
        cs5 = compact_section(s5, "entries")
        if "english_terms_used" in s5:
            cs5["english_terms_used"] = s5["english_terms_used"]
        if cs5:
            result["step5_english_bridge"] = cs5

    # step9_specialized
    if "step9_specialized" in per_synset:
        s9 = per_synset["step9_specialized"]
        cs9 = {}
        if "filters_applied" in s9:
            cs9["filters_applied"] = s9["filters_applied"]
        if cs9:
            result["step9_specialized"] = cs9

    return result


def preprocess(data: dict) -> dict:
    """Main preprocessing: strip noise, keep linguistic data."""
    output = {}

    # synset section: keep as-is (already compact)
    if "synset" in data:
        output["synset"] = data["synset"]

    # per_lemma: compact each lemma's sections
    if "per_lemma" in data:
        output["per_lemma"] = process_per_lemma(data["per_lemma"])

    # per_synset: compact synset-level searches
    if "per_synset" in data:
        output["per_synset"] = process_per_synset(data["per_synset"])

    return output


class ArabicDumper(yaml.Dumper):
    """YAML dumper that handles Arabic text properly."""
    pass


def str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


ArabicDumper.add_representer(str, str_representer)


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess .evidence.yaml for prompt injection"
    )
    parser.add_argument("input", help="Path to .evidence.yaml file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    result = preprocess(data)

    output_yaml = yaml.dump(
        result,
        Dumper=ArabicDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=200,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_yaml)
    else:
        sys.stdout.write(output_yaml)


if __name__ == "__main__":
    main()
