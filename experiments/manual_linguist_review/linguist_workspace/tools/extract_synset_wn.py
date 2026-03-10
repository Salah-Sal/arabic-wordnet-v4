#!/usr/bin/env python3
"""
extract_synset_wn.py — مستكشف المجموعات الترادفية في AWN4
AWN4 Synset Explorer using the wn Python library.

Uses the wn library's SQLite backend for instant access — no XML parsing needed.
Provides Arabic definitions, English definitions (via OEWN), resolved relation
targets with Arabic lemmas, and hypernym path display.

Usage:
    python3 extract_synset_wn.py awn4-03466051-n             # Single synset
    python3 extract_synset_wn.py awn4-03466051-n awn4-01572394-v  # Multiple
    python3 extract_synset_wn.py --random 5                  # 5 random synsets
    python3 extract_synset_wn.py --random 10 --pos n         # 10 random nouns
    python3 extract_synset_wn.py --random 5 --min-lemmas 2   # At least 2 lemmas
    python3 extract_synset_wn.py --batch batch_file.txt      # From file
    python3 extract_synset_wn.py --stats                     # Corpus statistics
    python3 extract_synset_wn.py --english "dog"             # Find by English word
    python3 extract_synset_wn.py --english "tree" --pos n    # English + POS filter

Requirements:
    pip install wn
    The wn database must contain awn4:4.0 and oewn:2024.
    If not loaded, run once:
        python3 -c "import wn; wn.add('path/to/awn4.xml')"
        python3 -c "import wn; wn.download('oewn:2024')"
"""

import argparse
import random
import sys
from collections import defaultdict

try:
    import wn
except ImportError:
    print("Error: wn package not installed. Run: pip install wn", file=sys.stderr)
    sys.exit(1)

# ── POS label mapping ───────────────────────────────────────────────

POS_LABELS = {
    "n": "اسم (noun)",
    "v": "فعل (verb)",
    "a": "صفة (adjective)",
    "r": "ظرف (adverb)",
    "s": "صفة (adjective satellite)",
}

RELATION_LABELS = {
    "hypernym": "أعم (hypernym)",
    "hyponym": "أخص (hyponym)",
    "instance_hypernym": "صنف أعم (instance hypernym)",
    "instance_hyponym": "نموذج (instance hyponym)",
    "mero_member": "عضو في (member meronym)",
    "holo_member": "يتكون من أعضاء (member holonym)",
    "mero_part": "جزء من (part meronym)",
    "holo_part": "يتكون من أجزاء (part holonym)",
    "mero_substance": "مادة في (substance meronym)",
    "holo_substance": "يتكون من مادة (substance holonym)",
    "also": "انظر أيضاً (also)",
    "attribute": "سمة (attribute)",
    "similar": "شبيه (similar)",
    "domain_region": "نطاق جغرافي (domain region)",
    "domain_topic": "نطاق موضوعي (domain topic)",
    "exemplifies": "مثال على (exemplifies)",
    "entails": "يستلزم (entails)",
    "causes": "يسبب (causes)",
    "is_caused_by": "مُسبَّب بـ (is caused by)",
    "is_entailed_by": "مُستلزَم بـ (is entailed by)",
    "is_exemplified_by": "يتمثل في (is exemplified by)",
    "has_domain_region": "ضمن نطاق (has domain region)",
    "has_domain_topic": "ضمن موضوع (has domain topic)",
}


# ── Wordnet initialization ──────────────────────────────────────────

def get_wordnets():
    """Initialize and return (ar_wn, en_wn).

    ar_wn: wn.Wordnet for AWN4 (Arabic)
    en_wn: wn.Wordnet for OEWN (English) — may be None if not loaded
    """
    ar_lexicons = wn.lexicons(lang="arb")
    if not ar_lexicons:
        print("Error: AWN4 not found in the wn database.", file=sys.stderr)
        print("Load it with: python3 -c \"import wn; wn.add('path/to/awn4.xml')\"", file=sys.stderr)
        sys.exit(1)

    awn_spec = ar_lexicons[0].specifier()
    ar_wn = wn.Wordnet(awn_spec)
    print(f"AWN4 loaded: {awn_spec}", file=sys.stderr)

    en_wn = None
    en_lexicons = wn.lexicons(lang="en")
    if en_lexicons:
        en_spec = en_lexicons[0].specifier()
        en_wn = wn.Wordnet(en_spec)
        print(f"OEWN loaded: {en_spec}", file=sys.stderr)
    else:
        print("Warning: OEWN not found — English definitions unavailable.", file=sys.stderr)
        print("Load with: python3 -c \"import wn; wn.download('oewn:2024')\"", file=sys.stderr)

    return ar_wn, en_wn


# ── English definition lookup ────────────────────────────────────────

def get_english_definition(synset, en_wn):
    """Get English definition for an Arabic synset via ILI → OEWN.

    Uses wn.synsets(ili=...) for reliable cross-lexicon access.
    Falls back to direct OEWN ID mapping if ILI lookup fails.
    """
    if en_wn is None or not synset.ili:
        return None

    # Primary: ILI-based lookup
    en_synsets = wn.synsets(ili=synset.ili, lang="en")
    for ess in en_synsets:
        defn = ess.definition()
        if defn:
            return defn

    # Fallback: direct ID mapping (awn4-XXXXX-X → oewn-XXXXX-X)
    oewn_id = synset.id.replace("awn4-", "oewn-")
    try:
        oewn_ss = en_wn.synset(oewn_id)
        return oewn_ss.definition()
    except wn.Error:
        return None


# ── Hypernym chain ──────────────────────────────────────────────────

def get_hypernym_chain(synset):
    """Build the shortest hypernym path from synset to root.

    Returns a list of (synset_id, lemma_list) tuples, excluding the
    synset itself. Empty list if no hypernyms.
    """
    paths = synset.hypernym_paths()
    if not paths:
        return []

    # Pick the shortest path (most direct taxonomy)
    shortest = min(paths, key=len)

    chain = []
    for ancestor in shortest:
        lemmas = ancestor.lemmas()[:3]
        chain.append((ancestor.id, lemmas))
    return chain


# ── Formatting ──────────────────────────────────────────────────────

def format_synset(synset, en_wn):
    """Format a single synset for full display."""
    lines = []
    sid = synset.id
    pos = synset.pos
    pos_label = POS_LABELS.get(pos, pos)

    lines.append(f"{'═' * 60}")
    lines.append(f"  {sid}")
    lines.append(f"{'═' * 60}")
    lines.append("")
    lines.append(f"  النوع (POS):     {pos_label}")
    lines.append(f"  ILI:             {synset.ili or '(none)'}")
    lines.append("")

    # Lemmas
    lemmas = synset.lemmas()
    lines.append("  اللمّات — Lemmas:")
    if lemmas:
        for i, lem in enumerate(lemmas, 1):
            lines.append(f"    {i}. {lem}")
    else:
        lines.append("    (no lemmas found)")
    lines.append("")

    # Arabic definition
    ar_def = synset.definition()
    lines.append("  التعريف العربي — Arabic Definition:")
    lines.append(f"    {ar_def or '(none)'}")
    lines.append("")

    # English definition (via OEWN)
    en_def = get_english_definition(synset, en_wn)
    if en_def:
        lines.append("  التعريف الإنجليزي — English Definition (OEWN):")
        lines.append(f"    {en_def}")
        lines.append("")

    # Examples
    examples = synset.examples()
    if examples:
        lines.append("  الأمثلة — Examples:")
        for ex in examples:
            lines.append(f"    • {ex}")
        lines.append("")

    # Relations — with resolved Arabic lemmas
    rels = synset.relations()
    if rels:
        lines.append("  العلاقات — Relations:")
        for rel_type, targets in rels.items():
            rel_label = RELATION_LABELS.get(rel_type, rel_type)
            for target in targets:
                target_lemmas = target.lemmas()[:3]
                lemma_str = f" [{' / '.join(target_lemmas)}]" if target_lemmas else ""
                lines.append(f"    • {rel_label} → {target.id}{lemma_str}")
        lines.append("")

    # Hypernym path
    chain = get_hypernym_chain(synset)
    if chain:
        own_lemmas = synset.lemmas()[:1]
        start = own_lemmas[0] if own_lemmas else sid
        path_parts = [start]
        for _, ancestor_lemmas in chain:
            if ancestor_lemmas:
                path_parts.append(ancestor_lemmas[0])
            else:
                path_parts.append("?")
        lines.append("  مسار التصنيف — Hypernym Path:")
        lines.append(f"    {' → '.join(path_parts)}")
        lines.append("")

    return "\n".join(lines)


def format_synset_compact(synset, en_wn):
    """Format a synset in compact style for batch files."""
    sid = synset.id
    lemmas = synset.lemmas()
    lemma_str = " / ".join(lemmas) if lemmas else "(none)"
    ar_def = synset.definition() or "(none)"
    en_def = get_english_definition(synset, en_wn) or ""

    rels = synset.relations()
    hypernym_strs = []
    for rel_type in ("hypernym", "instance_hypernym"):
        for target in rels.get(rel_type, []):
            hypernym_strs.append(f"hypernym → {target.id}")
    rel_str = ", ".join(hypernym_strs) if hypernym_strs else "(none)"

    lines = [
        f"- synset_id: {sid}",
        f"  pos: {synset.pos}",
        f"  lemmas: [{lemma_str}]",
        f'  definition_ar: "{ar_def}"',
    ]
    if en_def:
        lines.append(f'  definition_en: "{en_def}"')
    lines.append(f"  hypernym: {rel_str}")
    lines.append("")

    return "\n".join(lines)


# ── Statistics ──────────────────────────────────────────────────────

def show_stats(ar_wn):
    """Print corpus statistics."""
    all_synsets = ar_wn.synsets()
    total = len(all_synsets)

    pos_counts = defaultdict(int)
    lemma_counts = defaultdict(int)
    no_lemma = 0
    multi_lemma = 0

    for ss in all_synsets:
        pos_counts[ss.pos] += 1
        n_lemmas = len(ss.lemmas())
        lemma_counts[n_lemmas] += 1
        if n_lemmas == 0:
            no_lemma += 1
        if n_lemmas >= 2:
            multi_lemma += 1

    total_senses = sum(len(ss.senses()) for ss in all_synsets)

    print(f"\n{'═' * 50}")
    print(f"  AWN4 Corpus Statistics")
    print(f"{'═' * 50}\n")

    print(f"  Total synsets: {total:,}")
    print(f"  Total sense links: {total_senses:,}")

    print(f"\n  By POS:")
    for pos in sorted(pos_counts, key=pos_counts.get, reverse=True):
        label = POS_LABELS.get(pos, pos)
        print(f"    {label}: {pos_counts[pos]:,}")

    print(f"\n  Lemma distribution:")
    for n in sorted(lemma_counts.keys()):
        pct = lemma_counts[n] / total * 100
        bar = "█" * int(pct / 2)
        print(f"    {n} lemmas: {lemma_counts[n]:>6,} ({pct:5.1f}%) {bar}")

    print(f"\n  Synsets with ≥2 lemmas: {multi_lemma:,} ({multi_lemma/total*100:.1f}%)")
    print(f"  Synsets with 0 lemmas:  {no_lemma:,}")
    print()


# ── English lookup ──────────────────────────────────────────────────

def find_by_english(ar_wn, en_wn, term, pos=None):
    """Find Arabic synsets matching an English word via ILI alignment.

    Returns a list of Arabic Synset objects (re-fetched for full data).
    """
    if en_wn is None:
        print("Error: OEWN not loaded — cannot search by English.", file=sys.stderr)
        return []

    en_synsets = en_wn.synsets(term, pos=pos)
    ar_synsets = []
    seen_ids = set()

    for ess in en_synsets:
        if not ess.ili:
            continue
        # Find Arabic synsets sharing the same ILI
        matches = wn.synsets(ili=ess.ili, lang="arb")
        for ars in matches:
            if ars.id not in seen_ids:
                seen_ids.add(ars.id)
                # Re-fetch via ar_wn for full data access
                try:
                    full_ss = ar_wn.synset(ars.id)
                    ar_synsets.append(full_ss)
                except wn.Error:
                    ar_synsets.append(ars)

    return ar_synsets


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract synset data from AWN4 using the wn library.",
        epilog="Examples:\n"
               "  python3 extract_synset_wn.py awn4-03466051-n\n"
               "  python3 extract_synset_wn.py --random 5 --pos n --min-lemmas 2\n"
               "  python3 extract_synset_wn.py --batch my_batch.txt\n"
               "  python3 extract_synset_wn.py --english \"computer\"\n"
               "  python3 extract_synset_wn.py --stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("synset_ids", nargs="*", help="Synset IDs to extract")
    parser.add_argument("--random", type=int, metavar="N", help="Pick N random synsets")
    parser.add_argument("--pos", choices=["n", "v", "a", "r", "s"], help="Filter by POS")
    parser.add_argument("--min-lemmas", type=int, default=0, help="Minimum number of lemmas")
    parser.add_argument("--batch", metavar="FILE", help="Read synset IDs from file (one per line)")
    parser.add_argument("--stats", action="store_true", help="Show corpus statistics")
    parser.add_argument("--english", metavar="WORD", help="Find Arabic synsets by English word")
    parser.add_argument("--compact", action="store_true", help="Use compact output format")
    parser.add_argument("--output", "-o", metavar="FILE", help="Write output to file")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")

    args = parser.parse_args()

    # ── Initialize ──────────────────────────────────────────────
    ar_wn, en_wn = get_wordnets()

    # ── Stats mode ──────────────────────────────────────────────
    if args.stats:
        show_stats(ar_wn)
        return

    # ── English lookup mode ─────────────────────────────────────
    if args.english:
        synsets = find_by_english(ar_wn, en_wn, args.english, pos=args.pos)
        if not synsets:
            print(f"No Arabic synsets found for English word: {args.english!r}", file=sys.stderr)
            return
        print(f"Found {len(synsets)} Arabic synset(s) for '{args.english}':\n", file=sys.stderr)

        formatter = format_synset_compact if args.compact else format_synset
        output_lines = [formatter(ss, en_wn) for ss in synsets]
        result = "\n".join(output_lines)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"Wrote {len(synsets)} synset(s) to {args.output}", file=sys.stderr)
        else:
            print(result)
        return

    # ── Collect target IDs ──────────────────────────────────────
    target_ids = list(args.synset_ids)

    if args.batch:
        with open(args.batch) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    target_ids.append(line.split()[0])

    if args.random:
        if args.seed is not None:
            random.seed(args.seed)

        all_synsets = ar_wn.synsets(pos=args.pos)
        candidates = []
        for ss in all_synsets:
            if len(ss.lemmas()) >= args.min_lemmas:
                candidates.append(ss.id)

        n = min(args.random, len(candidates))
        if n < args.random:
            print(f"Warning: only {len(candidates)} synsets match filters "
                  f"(requested {args.random})", file=sys.stderr)
        target_ids.extend(random.sample(candidates, n))

    if not target_ids:
        parser.print_help()
        sys.exit(1)

    # ── Format output ───────────────────────────────────────────
    formatter = format_synset_compact if args.compact else format_synset
    output_lines = []
    found = 0

    for sid in target_ids:
        try:
            ss = ar_wn.synset(sid)
            output_lines.append(formatter(ss, en_wn))
            found += 1
        except wn.Error:
            output_lines.append(f"⚠ Synset not found: {sid}\n")

    result = "\n".join(output_lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Wrote {found} synset(s) to {args.output}", file=sys.stderr)
    else:
        print(result)

    if found < len(target_ids):
        print(f"\n⚠ {len(target_ids) - found} synset(s) not found", file=sys.stderr)


if __name__ == "__main__":
    main()
