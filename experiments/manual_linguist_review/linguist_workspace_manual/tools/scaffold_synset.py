#!/usr/bin/env python3
"""
scaffold_synset.py — مولّد الهيكل الأوّلي
YAML Scaffold Generator for Manual Evidence Collection.

Generates a scaffold YAML file with:
  - _meta section (schema_version, timestamp, generator: "manual")
  - synset section (fully populated from wn library)
  - per_lemma sections (identity filled, steps empty with TODO comments)
  - per_synset sections (empty with TODO comments)

Does NOT access the database. Uses only the wn Python library.

Usage:
    python3 tools/scaffold_synset.py awn4-05162506-n
    python3 tools/scaffold_synset.py awn4-05162506-n awn4-03466051-n
    python3 tools/scaffold_synset.py --batch batches/my_batch.txt
    python3 tools/scaffold_synset.py -o output/evidence/ awn4-05162506-n

Requirements:
    pip install wn
    wn database must contain awn4 and oewn:2024.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import wn
except ImportError:
    print("Error: wn package not installed. Run: pip install wn", file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Arabic Text Utilities (same as collect_evidence.py)
# ═══════════════════════════════════════════════════════════════════════════════

DIACRITICS_RE = re.compile("[\u0617-\u061A\u064B-\u065F\u0670]")
ARABIC_TOKEN_RE = re.compile(r"[\u0600-\u06FF]+")

ARABIC_STOPWORDS = frozenset({
    "من", "في", "على", "إلى", "الى", "عن", "مع", "هو", "هي",
    "هذا", "هذه", "ذلك", "تلك", "الذي", "التي", "ما",
    "لا", "أن", "ان", "إن", "كان", "كانت", "يكون", "قد", "بل",
    "أو", "او", "ثم", "حتى", "لم", "لن", "إذا", "إذ", "كل",
    "بعض", "غير", "بين", "عند", "فوق", "تحت", "بعد", "قبل",
    "أي", "كيف", "أين", "متى", "لماذا", "ليس", "وهو", "وهي",
})


def strip_diacritics(text: str) -> str:
    return DIACRITICS_RE.sub("", text)


def normalize_arabic(text: str) -> str:
    text = strip_diacritics(text)
    text = re.sub("[أإآ]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("\u0640", "")
    return text.strip()


def al_variants(lemma_norm: str) -> tuple[str, str]:
    if lemma_norm.startswith("ال"):
        return (lemma_norm, lemma_norm[2:])
    return (lemma_norm, "ال" + lemma_norm)


def extract_keywords(text: str) -> list[str]:
    text_norm = normalize_arabic(text)
    tokens = ARABIC_TOKEN_RE.findall(text_norm)
    return [t for t in tokens if len(t) > 2 and t not in ARABIC_STOPWORDS]


# ═══════════════════════════════════════════════════════════════════════════════
# YAML Helpers (no pyyaml — string-based generation)
# ═══════════════════════════════════════════════════════════════════════════════

def _y(s: str) -> str:
    """Escape a string for safe YAML output (double-quoted)."""
    if not s:
        return '""'
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _ylist(items: list[str], indent: int = 4) -> str:
    """Format a list of strings as YAML."""
    if not items:
        return "[]"
    pad = " " * indent
    return "\n".join(f"{pad}- {_y(item)}" for item in items)


def _ylist_inline(items: list[str]) -> str:
    """Format a short list inline: ["a", "b"]."""
    if not items:
        return "[]"
    return "[" + ", ".join(_y(i) for i in items) + "]"


# ═══════════════════════════════════════════════════════════════════════════════
# wn Bridge (simplified — synset data only, no DB)
# ═══════════════════════════════════════════════════════════════════════════════

def _init_wordnets():
    """Initialize AWN4 and OEWN wordnets."""
    ar_lexicons = [l for l in wn.lexicons() if l.language == "arb"]
    if not ar_lexicons:
        print("Error: AWN4 not loaded. Run:", file=sys.stderr)
        print("  python3 -c \"import wn; wn.add('path/to/awn4.xml')\"", file=sys.stderr)
        sys.exit(1)
    ar_wn = wn.Wordnet(ar_lexicons[0].specifier())

    en_lexicons = [l for l in wn.lexicons() if l.language == "en"]
    en_wn = wn.Wordnet(en_lexicons[0].specifier()) if en_lexicons else None

    return ar_wn, en_wn


def _get_oewn(ss, en_wn):
    """Get OEWN data for a synset via ILI."""
    if not en_wn or not ss.ili:
        return None
    en_synsets = wn.synsets(ili=ss.ili, lang="en")
    if not en_synsets:
        return None
    en = en_synsets[0]
    return {
        "definition_en": en.definition() or "",
        "lemmas_en": [w.lemma() for w in en.words()],
        "examples_en": en.examples() or [],
        "pos_en": en.pos or "",
    }


def _get_oewn_short(ss, en_wn):
    """Get just definition + lemmas for hypernym chain."""
    if not en_wn or not ss.ili:
        return None
    en_synsets = wn.synsets(ili=ss.ili, lang="en")
    if not en_synsets:
        return None
    en = en_synsets[0]
    return {
        "def": en.definition() or "",
        "lemmas": [w.lemma() for w in en.words()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Scaffold Generation
# ═══════════════════════════════════════════════════════════════════════════════

def generate_scaffold(synset_id: str, ar_wn, en_wn) -> str:
    """Generate a complete scaffold YAML string for a synset."""
    ss = ar_wn.synset(synset_id)
    lemmas = [w.lemma() for w in ss.words()]
    oewn = _get_oewn(ss, en_wn)

    lines = []

    # ── _meta ──
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append("_meta:")
    lines.append('  schema_version: "1.0.0"')
    lines.append(f"  generated_at: {_y(now)}")
    lines.append('  generator: "manual"')
    lines.append('  db_path: "data/arabic_dict.db"')
    lines.append("  db_stats:")
    lines.append("    total_entries: 760660")
    lines.append("    total_dictionaries: 107")
    lines.append("")

    # ── synset ──
    lines.append("synset:")
    lines.append(f"  id: {_y(ss.id)}")
    lines.append(f"  ili: {_y(ss.ili) if ss.ili else 'null'}")
    lines.append(f"  pos: {_y(ss.pos)}")
    lines.append("  lemmas:")
    for lem in lemmas:
        lines.append(f"    - {_y(lem)}")
    lines.append(f"  definition_ar: {_y(ss.definition() or '')}")
    examples_ar = ss.examples() or []
    if examples_ar:
        lines.append("  examples_ar:")
        for ex in examples_ar:
            lines.append(f"    - {_y(ex)}")
    else:
        lines.append("  examples_ar: []")

    # oewn
    if oewn:
        lines.append("  oewn:")
        lines.append(f"    definition_en: {_y(oewn['definition_en'])}")
        lines.append("    lemmas_en:")
        for lem_en in oewn["lemmas_en"]:
            lines.append(f"      - {_y(lem_en)}")
        if oewn["examples_en"]:
            lines.append("    examples_en:")
            for ex in oewn["examples_en"]:
                lines.append(f"      - {_y(ex)}")
        else:
            lines.append("    examples_en: []")
        lines.append(f"    pos_en: {_y(oewn['pos_en'])}")
    else:
        lines.append("  oewn: null")

    # hypernym_chain
    paths = ss.hypernym_paths()
    if paths:
        shortest = min(paths, key=len)
        lines.append("  hypernym_chain:")
        lines.append(f"    depth: {len(shortest)}")
        lines.append("    path:")
        for ancestor in shortest:
            oewn_a = _get_oewn_short(ancestor, en_wn)
            lines.append(f"      - id: {_y(ancestor.id)}")
            lines.append("        lemmas:")
            for al in [w.lemma() for w in ancestor.words()]:
                lines.append(f"          - {_y(al)}")
            lines.append(f"        definition_ar: {_y(ancestor.definition() or '')}")
            if oewn_a:
                lines.append(f"        oewn_definition_en: {_y(oewn_a['def'])}")
                lines.append(f"        oewn_lemmas_en: {_ylist_inline(oewn_a['lemmas'])}")
            else:
                lines.append("        oewn_definition_en: null")
                lines.append("        oewn_lemmas_en: null")
    else:
        lines.append("  hypernym_chain:")
        lines.append("    depth: 0")
        lines.append("    path: []")

    # relations
    rels = ss.relations()
    if rels:
        lines.append("  relations:")
        for rel_type, targets in rels.items():
            for target in targets:
                oewn_t = _get_oewn_short(target, en_wn)
                lines.append(f"    - rel_type: {_y(rel_type)}")
                lines.append(f"      target_id: {_y(target.id)}")
                lines.append("      target_lemmas:")
                for tl in [w.lemma() for w in target.words()]:
                    lines.append(f"        - {_y(tl)}")
                lines.append(f"      target_definition_ar: {_y(target.definition() or '')}")
                if oewn_t:
                    lines.append(f"      target_oewn_definition_en: {_y(oewn_t['def'])}")
                    lines.append(f"      target_oewn_lemmas_en: {_ylist_inline(oewn_t['lemmas'])}")
                else:
                    lines.append("      target_oewn_definition_en: null")
                    lines.append("      target_oewn_lemmas_en: null")
    else:
        lines.append("  relations: []")

    lines.append("")

    # ── per_lemma ──
    lines.append("per_lemma:")
    lines.append("")

    for lemma in lemmas:
        lemma_bare = strip_diacritics(lemma)
        lemma_norm = normalize_arabic(lemma)
        is_multiword = " " in lemma
        components = lemma.split() if is_multiword else []
        base, al_form = al_variants(lemma_norm)

        lines.append(f"  {_y(lemma)}:")
        lines.append("")

        # identity
        lines.append("    identity:")
        lines.append(f"      lemma: {_y(lemma)}")
        lines.append(f"      lemma_bare: {_y(lemma_bare)}")
        lines.append(f"      lemma_norm: {_y(lemma_norm)}")
        lines.append(f"      is_multiword: {'true' if is_multiword else 'false'}")
        if components:
            lines.append(f"      components: {_ylist_inline(components)}")
        else:
            lines.append("      components: []")
        lines.append("")

        # Step 1
        lines.append("    step1_headword:")
        lines.append(f"      al_variants_searched: {_ylist_inline([base, al_form])}")
        lines.append("      result_count: 0")
        lines.append("      entries: []")
        if is_multiword:
            lines.append("      by_component:")
            for comp in components:
                comp_norm = normalize_arabic(comp)
                comp_base, comp_al = al_variants(comp_norm)
                lines.append(f"        {_y(comp_norm)}:")
                lines.append(f"          al_variants_searched: {_ylist_inline([comp_base, comp_al])}")
                lines.append("          result_count: 0")
                lines.append("          entries: []")
        else:
            lines.append("      by_component: null")

        # Step 2
        lines.append("    step2_definitions:")
        lines.append("      result_count: 0")
        lines.append("      entries_with_senses: []")

        # Step 3
        lines.append("    step3_root_family:")
        lines.append("      roots_found: []")
        lines.append("      by_root: {}")

        # Step 6
        lines.append("    step6_examples:")
        lines.append("      result_count: 0")
        lines.append("      examples: []")

        # Step 7
        lines.append("    step7_chronological:")
        lines.append("      result_count: 0")
        lines.append("      entries: []")

        # Step 8
        lines.append("    step8_reverse_lookup:")
        lines.append("      result_count: 0")
        lines.append("      entries: []")
        lines.append("")

    # ── per_synset ──
    lines.append("per_synset:")
    lines.append("")

    # Step 4
    definition_ar = ss.definition() or ""
    keywords = extract_keywords(definition_ar)
    lines.append("  step4_fts_keyword:")
    lines.append(f"    keywords_extracted: {_ylist_inline(keywords)}")
    lines.append("    excluded_entry_ids: []")
    lines.append("    result_count: 0")
    lines.append("    entries: []")

    # Step 5
    en_terms = oewn["lemmas_en"] if oewn else []
    lines.append("  step5_english_bridge:")
    lines.append(f"    english_terms_used: {_ylist_inline(en_terms)}")
    lines.append("    excluded_entry_ids: []")
    lines.append("    result_count: 0")
    lines.append("    entries: []")

    # Step 9
    lines.append("  step9_specialized:")
    lines.append("    filters_applied: []")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate YAML scaffolds for manual evidence collection.",
        epilog="The scaffold pre-fills synset metadata and identity blocks. "
               "The linguist then runs SQL queries and fills in the empty sections."
    )
    parser.add_argument("synset_ids", nargs="*", help="One or more synset IDs (e.g., awn4-05162506-n)")
    parser.add_argument("--batch", "-b", help="Batch file with synset IDs (one per line)")
    parser.add_argument("--output-dir", "-o", default="output/evidence",
                        help="Output directory (default: output/evidence)")

    args = parser.parse_args()

    # Collect target IDs
    target_ids: list[str] = list(args.synset_ids)
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.is_absolute():
            batch_path = Path(__file__).resolve().parent.parent / args.batch
        with open(batch_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.search(r'synset_id:\s*(awn4-\S+)', line)
                if m:
                    target_ids.append(m.group(1))
                    continue
                token = line.split()[0].lstrip("-").strip()
                if token.startswith("awn4-"):
                    target_ids.append(token)

    if not target_ids:
        parser.print_help()
        sys.exit(1)

    # Resolve output dir
    workspace = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = workspace / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize wn
    ar_wn, en_wn = _init_wordnets()

    # Generate scaffolds
    ok = 0
    fail = 0
    for i, sid in enumerate(target_ids, 1):
        print(f"[{i}/{len(target_ids)}] {sid}...", end=" ", file=sys.stderr, flush=True)
        try:
            yaml_str = generate_scaffold(sid, ar_wn, en_wn)
            out_path = output_dir / f"{sid}.scaffold.yaml"
            out_path.write_text(yaml_str, encoding="utf-8")
            print(f"-> {out_path.name}", file=sys.stderr)
            ok += 1
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            fail += 1

    print(f"\nDone. {ok} scaffolds generated, {fail} failed.", file=sys.stderr)


if __name__ == "__main__":
    main()
