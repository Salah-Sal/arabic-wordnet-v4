#!/usr/bin/env python3
"""
fill_prompt.py — Fill the linguist prompt template with evidence data for a synset.

Reads a compressed evidence YAML file and fills in all {{placeholder}} values in
the linguist_prompt.md template, producing a self-contained prompt ready for use.

Usage:
    python3 tools/fill_prompt.py awn4-01572394-v
    python3 tools/fill_prompt.py awn4-01572394-v --output-dir output/
    python3 tools/fill_prompt.py --batch batches/sample.txt --output-dir output/
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# Import helpers from prepare_synset.py (same directory)
from prepare_synset import (
    load_evidence,
    _truncate,
    _safe_headword,
    _count_by_period,
    _count_by_source_type,
    _unique_dict_names,
    _select_top_definitions,
    _format_hypernym_chain,
    strip_diacritics,
    MAX_TOP_DEFS,
    MAX_SYNONYM_CANDIDATES,
    MAX_EXAMPLES,
    MAX_FTS_RESULTS,
    MAX_ENGLISH_BRIDGE,
    MAX_ROOT_FAMILY_HEADWORDS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _format_relations(synset: dict) -> str:
    """Format synset relations as a markdown list."""
    relations = synset.get("relations", [])
    if not relations:
        return "(لا توجد علاقات)"
    lines = []
    for rel in relations[:10]:
        rt = rel.get("rel_type", "?")
        tl = "، ".join(rel.get("target_lemmas", [])[:3])
        td = _truncate(rel.get("target_definition_ar", ""), 80)
        lines.append(f"- **{rt}:** {tl} — {td}")
    return "\n".join(lines)


def _format_top_definitions(defs: list[dict]) -> str:
    """Format selected definitions as markdown blockquotes."""
    if not defs:
        return "(لا توجد تعريفات)"
    lines = []
    for d in defs:
        name = d.get("dict_name_ar") or d.get("dict_name_en") or d.get("dict_key", "")
        dy = d.get("dict_death_year")
        dy_str = f"ت {dy}" if dy else "حديث"
        text = _truncate(d["text"], 300)
        lines.append(f"> **{name}** ({dy_str}):")
        lines.append(f"> {text}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_synonym_table(entries: list[dict]) -> str:
    """Format reverse lookup entries as a markdown table."""
    if not entries:
        return "(لا توجد مرشحات)"
    lines = [
        "| المرشح | المعجم | المعنى |",
        "|--------|--------|--------|",
    ]
    seen_hw = set()
    count = 0
    for e in entries:
        hw = _safe_headword(e)
        if not hw or hw in seen_hw:
            continue
        seen_hw.add(hw)
        dk_name = _truncate(e.get("dict_name_ar") or e.get("dict_name_en") or "", 25)
        def_text = _truncate(e.get("definitions_text", ""), 100)
        lines.append(f"| {hw} | {dk_name} | {def_text} |")
        count += 1
        if count >= MAX_SYNONYM_CANDIDATES:
            break
    return "\n".join(lines)


def _format_examples(examples: list[dict]) -> str:
    """Format usage examples as a markdown list."""
    if not examples:
        return "(لا توجد شواهد)"
    lines = []
    for ex in examples[:MAX_EXAMPLES]:
        ex_type = ex.get("type", "usage")
        ex_text = _truncate(ex.get("text", ""), 200)
        attr = ex.get("attribution", "")
        dk_name = ex.get("dict_name_ar") or ex.get("dict_name_en") or ""
        attr_str = f" — {attr}" if attr else ""
        lines.append(f"- **[{ex_type}]** {ex_text}{attr_str} ({dk_name})")
    if len(examples) > MAX_EXAMPLES:
        lines.append(f"- *(+{len(examples) - MAX_EXAMPLES} أخرى)*")
    return "\n".join(lines)


def _format_fts_table(entries: list[dict]) -> str:
    """Format FTS keyword results as a markdown table."""
    if not entries:
        return "(لا توجد نتائج)"
    lines = [
        "| الراسمة | المعجم | المعنى |",
        "|---------|--------|--------|",
    ]
    for e in entries[:MAX_FTS_RESULTS]:
        hw = _safe_headword(e)
        dk_name = _truncate(e.get("dict_name_ar") or e.get("dict_name_en") or "", 25)
        def_text = _truncate(e.get("definitions_text", ""), 100)
        lines.append(f"| {hw} | {dk_name} | {def_text} |")
    return "\n".join(lines)


def _format_bridge_table(entries: list[dict]) -> str:
    """Format English bridge / ARABTERM results as a markdown table."""
    if not entries:
        return "(لا توجد نتائج)"
    lines = [
        "| المصطلح العربي | الترجمة | المجال | المعجم |",
        "|---------------|---------|--------|--------|",
    ]
    for e in entries[:MAX_ENGLISH_BRIDGE]:
        hw = _safe_headword(e, max_len=80)
        tr = _truncate(e.get("translation_en", ""), 40)
        domain = _truncate(e.get("domain", ""), 30)
        dk_name = _truncate(e.get("dict_name_ar") or e.get("dict_name_en") or "", 25)
        lines.append(f"| {hw} | {tr} | {domain} | {dk_name} |")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Template filling
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_lemma_data(lemma: str, per_lemma: dict) -> dict:
    """Get per-lemma evidence data, with bare-form fallback."""
    ld = per_lemma.get(lemma, {})
    if not ld:
        bare = strip_diacritics(lemma)
        for k, v in per_lemma.items():
            if strip_diacritics(k) == bare:
                ld = v
                break
    return ld


def _render_lemma_block(block: str, lemma: str, ld: dict, def_ar: str) -> str:
    """Fill all per-lemma placeholders in one copy of the lemma block."""
    identity = ld.get("identity", {})
    lemma_bare = identity.get("lemma_bare", strip_diacritics(lemma))

    # Root
    root_data = ld.get("step3_root_family", {})
    roots_found = root_data.get("roots_found", [])
    root = roots_found[0]["root"] if roots_found else ""
    root_source = roots_found[0]["root_source"] if roots_found else ""

    # Attestation
    step1 = ld.get("step1_headword", {})
    step1_entries = step1.get("entries", [])
    pc = _count_by_period(step1_entries)
    sc = _count_by_source_type(step1_entries)

    classical_entries = [e for e in step1_entries if e.get("dict_period") == "classical"]
    modern_entries = [e for e in step1_entries if e.get("dict_period") == "modern"]

    # Top definitions
    top_defs = _select_top_definitions(ld, def_ar)
    top_defs_str = _format_top_definitions(top_defs)

    # Root family
    by_root = root_data.get("by_root", {})
    family = by_root.get(root, {})
    family_count = family.get("result_count", 0)
    family_entries = family.get("entries", [])
    if family_entries:
        hw_counter: Counter = Counter()
        for e in family_entries:
            hw = e.get("headword_bare") or e.get("headword", "")
            if hw:
                hw_counter[hw] += 1
        top_hw = hw_counter.most_common(MAX_ROOT_FAMILY_HEADWORDS)
        root_family_str = "، ".join(f"{hw} ({n})" for hw, n in top_hw)
    else:
        root_family_str = "—"

    # Synonym candidates
    step8 = ld.get("step8_reverse_lookup", {})
    step8_entries = step8.get("entries", [])
    synonym_str = _format_synonym_table(step8_entries)

    # Usage examples
    step6 = ld.get("step6_examples", {})
    examples = step6.get("examples", [])
    examples_str = _format_examples(examples)

    # ARABTERM domain names for attestation
    at_entries = [e for e in step1_entries if e.get("dict_source_type") == "arabterm"]
    at_count = len(at_entries)
    if at_entries:
        domains = {e.get("domain", "") for e in at_entries if e.get("domain")}
        at_str = f"{at_count} ({', '.join(list(domains)[:3])})" if domains else str(at_count)
    else:
        at_str = "0"

    # Short definition for inline use in questions
    def_ar_short = _truncate(def_ar, 80)

    # Fill placeholders
    replacements = {
        "{{lemma}}": lemma,
        "{{lemma_bare}}": lemma_bare,
        "{{root}}": root,
        "{{root_source}}": root_source,
        "{{attestation_total}}": str(step1.get("result_count", 0)),
        "{{attestation_classical}}": str(pc.get("classical", 0)),
        "{{classical_dict_names}}": _unique_dict_names(classical_entries),
        "{{attestation_modern}}": str(pc.get("modern", 0)),
        "{{modern_dict_names}}": _unique_dict_names(modern_entries),
        "{{attestation_arabterm}}": at_str,
        "{{top_definitions}}": top_defs_str,
        "{{root_family_count}}": str(family_count),
        "{{root_family_top_headwords}}": root_family_str,
        "{{synonym_candidates}}": synonym_str,
        "{{usage_examples}}": examples_str,
        "{{definition_ar_short}}": def_ar_short,
    }

    result = block
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def fill_template(template: str, evidence: dict) -> str:
    """Fill all placeholders in the prompt template with evidence data."""
    synset = evidence.get("synset", {})
    per_lemma = evidence.get("per_lemma", {})
    per_synset = evidence.get("per_synset", {})

    lemmas = synset.get("lemmas", [])
    oewn = synset.get("oewn") or {}
    def_ar = synset.get("definition_ar", "")

    # ── Handle {{#each lemma}} block ──────────────────────────────────────
    each_pattern = re.compile(
        r'\{\{#each lemma\}\}(.*?)\{\{/each\}\}',
        re.DOTALL,
    )
    match = each_pattern.search(template)
    if match:
        block_template = match.group(1)
        rendered_blocks = []
        for lemma in lemmas:
            ld = _extract_lemma_data(lemma, per_lemma)
            rendered = _render_lemma_block(block_template, lemma, ld, def_ar)
            rendered_blocks.append(rendered)
        template = template[:match.start()] + "\n".join(rendered_blocks) + template[match.end():]

    # ── Synset-level placeholders ─────────────────────────────────────────
    synset_replacements = {
        "{{synset_id}}": synset.get("id", ""),
        "{{pos}}": synset.get("pos", ""),
        "{{definition_ar}}": def_ar,
        "{{definition_en}}": oewn.get("definition_en", ""),
        "{{lemmas_ar}}": " ، ".join(lemmas),
        "{{lemmas_en}}": ", ".join(oewn.get("lemmas_en", [])),
        "{{hypernym_chain}}": _format_hypernym_chain(synset),
        "{{relations}}": _format_relations(synset),
    }

    # ── Cross-lemma placeholders ──────────────────────────────────────────
    step4 = per_synset.get("step4_fts_keyword", {})
    step5 = per_synset.get("step5_english_bridge", {})

    cross_replacements = {
        "{{fts_keywords}}": " ".join(step4.get("keywords_extracted", [])),
        "{{fts_results}}": _format_fts_table(step4.get("entries", [])),
        "{{english_terms}}": ", ".join(step5.get("english_terms_used", [])),
        "{{english_bridge_results}}": _format_bridge_table(step5.get("entries", [])),
    }

    for key, value in {**synset_replacements, **cross_replacements}.items():
        template = template.replace(key, value)

    return template


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Fill the linguist prompt template with evidence data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s awn4-01572394-v                          # print to stdout
  %(prog)s awn4-01572394-v --output-dir output/     # write to file
  %(prog)s --batch batches/sample.txt --output-dir output/
""",
    )
    parser.add_argument("synset_ids", nargs="*", metavar="SYNSET_ID",
                        help="Synset IDs to process (e.g. awn4-01572394-v)")
    parser.add_argument("--batch", metavar="FILE",
                        help="Read synset IDs from a file (one per line)")
    parser.add_argument("--template", metavar="PATH",
                        help="Override template path (default: templates/linguist_prompt.md)")
    parser.add_argument("--output-dir", metavar="DIR",
                        help="Write filled prompts to files instead of stdout")
    parser.add_argument("--evidence-dir", metavar="DIR",
                        help="Override evidence directory path")
    args = parser.parse_args()

    workspace = Path(__file__).resolve().parent.parent

    # Collect target IDs
    target_ids: list[str] = list(args.synset_ids or [])
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.is_absolute():
            batch_path = workspace / args.batch
        with open(batch_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.search(r'(awn4-\S+)', line)
                if m:
                    target_ids.append(m.group(1))

    if not target_ids:
        parser.print_help()
        sys.exit(1)

    # Resolve evidence directory
    if args.evidence_dir:
        evidence_dir = Path(args.evidence_dir)
    else:
        evidence_dir = workspace.parent / "linguist_workspace" / "output" / "evidence"

    if not evidence_dir.exists():
        print(f"Error: Evidence directory not found: {evidence_dir}", file=sys.stderr)
        print("  Use --evidence-dir to specify the path.", file=sys.stderr)
        sys.exit(1)

    # Resolve template
    if args.template:
        template_path = Path(args.template)
    else:
        template_path = workspace / "templates" / "linguist_prompt.md"

    if not template_path.exists():
        print(f"Error: Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    template_text = template_path.read_text(encoding="utf-8")

    # Resolve output directory
    output_dir = None
    if args.output_dir:
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = workspace / args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

    # Process synsets
    ok = 0
    fail = 0
    for i, sid in enumerate(target_ids, 1):
        if output_dir or len(target_ids) > 1:
            print(f"[{i}/{len(target_ids)}] {sid}...", end=" ", file=sys.stderr, flush=True)
        try:
            evidence = load_evidence(sid, evidence_dir)
            filled = fill_template(template_text, evidence)

            # Check for unfilled placeholders
            remaining = re.findall(r'\{\{(?!#|/)([^}]+)\}\}', filled)
            if remaining:
                unique_remaining = sorted(set(remaining))
                print(f"WARNING: {len(unique_remaining)} unfilled placeholder(s): {', '.join(unique_remaining)}",
                      file=sys.stderr)

            if output_dir:
                synset_dir = output_dir / sid
                synset_dir.mkdir(parents=True, exist_ok=True)
                out_path = synset_dir / "prompt.md"
                out_path.write_text(filled, encoding="utf-8")
                print(f"-> {out_path.relative_to(workspace)}", file=sys.stderr)
            else:
                sys.stdout.write(filled)

            ok += 1
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            fail += 1

    if output_dir or len(target_ids) > 1:
        print(f"\nDone. {ok} filled, {fail} failed.", file=sys.stderr)


if __name__ == "__main__":
    main()
