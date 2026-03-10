#!/usr/bin/env python3
"""
prepare_synset.py — Prepare Stage 2 review materials for AWN4 synsets.

For a given synset ID:
  1. Reads the compressed evidence YAML from Stage 1
  2. Generates a human-readable evidence summary (summary.md)
  3. Generates a pre-filled review template (review.yaml)
  4. Decompresses the raw evidence for reference (evidence.yaml)

Usage:
    python3 tools/prepare_synset.py awn4-01572394-v
    python3 tools/prepare_synset.py awn4-01572394-v awn4-03466051-n
    python3 tools/prepare_synset.py --batch batches/my_batch.txt
    python3 tools/prepare_synset.py --no-raw awn4-01572394-v
    python3 tools/prepare_synset.py --evidence-dir /path/to/evidence/ awn4-01572394-v
"""
from __future__ import annotations

import argparse
import gzip
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# Import Arabic text utilities from the Stage 1 pipeline
# ═══════════════════════════════════════════════════════════════════════════════

_PIPELINE_DIR = str(Path(__file__).resolve().parent.parent.parent / "linguist_workspace" / "tools")
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from collect_evidence import (
    strip_diacritics,
    normalize_arabic,
    extract_keywords,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Dictionary priority for selecting top definitions in the summary.
# Order: OCR (authoritative structured) > key classical > modern references.
PRIORITY_DICT_KEYS = [
    "Al_Waseet",              # المعجم الوسيط (OCR, Academy of Arabic Language)
    "Al_Mujam_Al_Kabeer",     # المعجم الكبير (OCR, Academy)
    "Maqayis_Lugha",          # مقاييس اللغة (OCR, Ibn Faris d. 1004)
    "Kitab_Al_Ayn",           # كتاب العين (OCR, Al-Khalil d. 786)
    "Mujmal_Lugha",           # مجمل اللغة (OCR, Ibn Faris d. 1004)
    "hawramani_1",            # لسان العرب (Ibn Manzur d. 1311)
    "hawramani_25",           # تاج العروس (Al-Zabidi d. 1790)
    "hawramani_6",            # الصحاح (Al-Jawhari d. 1003)
    "hawramani_49",           # Lane's Lexicon (d. 1876)
    "hawramani_35",           # المعجم الوسيط — Hawramani version
    "hawramani_34",           # معجم اللغة المعاصرة (Ahmad Mukhtar d. 2003)
]

# Minimum keyword overlap to consider a definition "relevant" to the synset.
MIN_KEYWORD_OVERLAP = 1

# Maximum entries to show in each summary section.
MAX_TOP_DEFS = 5
MAX_SYNONYM_CANDIDATES = 15
MAX_EXAMPLES = 5
MAX_ROOT_FAMILY_HEADWORDS = 10
MAX_FTS_RESULTS = 10
MAX_ENGLISH_BRIDGE = 20


# ═══════════════════════════════════════════════════════════════════════════════
# Evidence Loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_evidence(synset_id: str, evidence_dir: Path) -> dict:
    """Load and decompress a .evidence.yaml.gz file. Returns parsed YAML dict."""
    gz_path = evidence_dir / f"{synset_id}.evidence.yaml.gz"
    plain_path = evidence_dir / f"{synset_id}.evidence.yaml"

    if gz_path.exists():
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            return yaml.safe_load(f)
    elif plain_path.exists():
        with open(plain_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        raise FileNotFoundError(
            f"Evidence file not found for {synset_id}.\n"
            f"  Checked: {gz_path}\n"
            f"  Checked: {plain_path}\n"
            f"  Run Stage 1 first or check --evidence-dir."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Summary Generation
# ═══════════════════════════════════════════════════════════════════════════════

def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis, collapsing newlines for table safety."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ").replace("|", "¦").strip()
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _safe_headword(entry: dict, max_len: int = 60) -> str:
    """Extract a clean headword from an entry, safe for markdown tables.

    Some dictionaries (e.g., Al-Mawrid) store multi-line numbered definitions
    in the headword field itself. This function detects and truncates those.
    """
    hw = entry.get("headword_bare") or entry.get("headword", "")
    if not hw:
        return ""
    # Strip newlines
    hw = hw.replace("\n", " ").replace("\r", " ").replace("|", "¦").strip()
    hw = re.sub(r" {2,}", " ", hw)
    # If headword looks like a numbered definition list, it's a data issue — truncate
    if len(hw) > max_len:
        hw = hw[:max_len] + "…"
    return hw


def _count_by_source_type(entries: list[dict]) -> dict[str, int]:
    """Count entries by dict_source_type."""
    counts: dict[str, int] = Counter()
    for e in entries:
        st = e.get("dict_source_type", "unknown")
        counts[st] += 1
    return dict(counts)


def _count_by_period(entries: list[dict]) -> dict[str, int]:
    """Count entries by dict_period."""
    counts: dict[str, int] = Counter()
    for e in entries:
        period = e.get("dict_period", "unknown")
        counts[period] += 1
    return dict(counts)


def _unique_dict_names(entries: list[dict], max_show: int = 5) -> str:
    """Return comma-separated unique dict names, truncated."""
    names = []
    seen = set()
    for e in entries:
        name = e.get("dict_name_ar") or e.get("dict_name_en") or e.get("dict_key", "")
        short = name[:30] if name else ""
        if short and short not in seen:
            seen.add(short)
            names.append(short)
    if len(names) > max_show:
        return "، ".join(names[:max_show]) + f" (+{len(names) - max_show})"
    return "، ".join(names) if names else "—"


def _select_top_definitions(lemma_data: dict, synset_def_ar: str) -> list[dict]:
    """Select the top definitions for a lemma, prioritized by dictionary authority.

    Uses a three-tier relevance filter:
    1. Keyword match — senses whose text overlaps with AWN definition keywords
    2. Lemma-form match — senses mentioning the specific lemma form (e.g., رَكَّبَ)
    3. Fallback — first sense (root's primary meaning)
    """
    # Extract keywords from the synset definition for relevance filtering
    keywords = set(extract_keywords(synset_def_ar)) if synset_def_ar else set()

    # Get the lemma's bare form for form-aware matching
    identity = lemma_data.get("identity", {})
    lemma_bare = identity.get("lemma_bare", "")
    # Generate morphologically discriminating search forms.
    # Problem: for Form II verbs like رَكَّبَ, lemma_bare="ركب" equals the root
    # and matches every definition. We need Form II-specific patterns.
    lemma_forms = set()
    root_data = lemma_data.get("step3_root_family", {})
    roots = root_data.get("roots_found", [])
    root_str = roots[0]["root"] if roots else ""
    if lemma_bare and lemma_bare != root_str:
        # Lemma is not identical to root — safe to use as search form
        lemma_forms.add(normalize_arabic(lemma_bare))
    elif root_str and len(root_str) == 3:
        # Lemma = root → likely a triliteral verb. Generate Form II masdar
        # (تفعيل pattern) as a more discriminating search keyword.
        # Form II masdar: تR1R2يR3 (e.g., ركب→تركيب, ثبت→تثبيت)
        r1, r2, r3 = root_str[0], root_str[1], root_str[2]
        masdar_ii = f"ت{r1}{r2}ي{r3}"  # تفعيل pattern
        lemma_forms.add(normalize_arabic(masdar_ii))
        # Also try the doubled-radical form (فعّل → R1R2ّR2R3)
        doubled_form = f"{r1}{r2}{r2}{r3}"  # e.g., ركّب → رككب (normalized)
        lemma_forms.add(normalize_arabic(doubled_form))

    # Collect definitions from step2 (structured per-sense)
    step2 = lemma_data.get("step2_definitions", {})
    entries_with_senses = step2.get("entries_with_senses", [])

    # Build a lookup: dict_key -> list of (sense_text, dict_name_ar, death_year)
    # Each sense also carries the entry's headword for form-matching.
    defs_by_dict: dict[str, list[dict]] = defaultdict(list)
    for entry in entries_with_senses:
        dk = entry.get("dict_key", "")
        entry_hw = entry.get("headword", "")
        for sense in entry.get("senses", []):
            text = sense.get("text", "")
            if not text:
                continue
            defs_by_dict[dk].append({
                "dict_key": dk,
                "dict_name_ar": entry.get("dict_name_ar", ""),
                "dict_name_en": entry.get("dict_name_en", ""),
                "dict_source_type": entry.get("dict_source_type", ""),
                "dict_death_year": entry.get("dict_death_year"),
                "sense_index": sense.get("sense_index", 0),
                "text": text,
                "_entry_headword": entry_hw,
            })

    # Also collect from step1 entries' definitions_text as fallback
    step1 = lemma_data.get("step1_headword", {})
    for entry in step1.get("entries", []):
        dk = entry.get("dict_key", "")
        if dk not in defs_by_dict:
            def_text = entry.get("definitions_text", "")
            if def_text:
                defs_by_dict[dk].append({
                    "dict_key": dk,
                    "dict_name_ar": entry.get("dict_name_ar", ""),
                    "dict_name_en": entry.get("dict_name_en", ""),
                    "dict_source_type": entry.get("dict_source_type", ""),
                    "dict_death_year": entry.get("dict_death_year"),
                    "sense_index": 0,
                    "text": def_text,
                })

    # Get the diacritized lemma for headword matching (e.g., "رَكَّبَ")
    lemma_diacritized = identity.get("lemma", "") or lemma_bare

    def _best_sense(candidates: list[dict]) -> dict:
        """Pick the most relevant sense from a dictionary's candidates.

        Four-tier preference:
        1. Keyword match against synset definition
        2. Headword match — senses from entries whose headword matches the
           diacritized lemma (e.g., prefer entry "رَكَّبَ" over "رَكِبَ")
        3. Lemma-form match via masdar pattern in sense text
        4. First sense (fallback)
        """
        if not candidates:
            return candidates[0]
        # Tier 1: keyword match
        if keywords:
            relevant = [
                d for d in candidates
                if any(kw in normalize_arabic(d["text"]) for kw in keywords)
            ]
            if relevant:
                return relevant[0]
        # Tier 2: headword match — prefer senses from entries whose diacritized
        # headword matches the lemma. This handles cases like ركّب (Form II) vs
        # ركب (Form I) which have distinct entries but share the same dict_key.
        if lemma_diacritized:
            lemma_stripped = strip_diacritics(lemma_diacritized)
            hw_match = [
                d for d in candidates
                if (strip_diacritics(d.get("_entry_headword", "")).strip("ال") ==
                    lemma_stripped and d.get("_entry_headword", "") == lemma_diacritized)
            ]
            if hw_match:
                return hw_match[0]
            # Relaxed match: diacritized headword contains the lemma's diacritics pattern
            # (handles minor differences like case endings)
            hw_relaxed = [
                d for d in candidates
                if d.get("_entry_headword", "").startswith(lemma_diacritized[:len(lemma_diacritized)-1])
                and len(d.get("_entry_headword", "")) > 0
            ]
            if hw_relaxed:
                return hw_relaxed[0]
        # Tier 3: lemma-form match via masdar in sense text
        if lemma_forms:
            form_match = [
                d for d in candidates
                if any(lf in normalize_arabic(d["text"]) for lf in lemma_forms)
            ]
            if form_match:
                return form_match[0]
        # Tier 4: fallback to first sense
        return candidates[0]

    # Select definitions by priority
    selected = []
    seen_keys = set()

    # First pass: priority dictionaries
    for dk in PRIORITY_DICT_KEYS:
        if dk in defs_by_dict and dk not in seen_keys:
            selected.append(_best_sense(defs_by_dict[dk]))
            seen_keys.add(dk)
            if len(selected) >= MAX_TOP_DEFS:
                break

    # Second pass: fill remaining slots from other dictionaries by death_year
    if len(selected) < MAX_TOP_DEFS:
        remaining = []
        for dk, defs in defs_by_dict.items():
            if dk not in seen_keys:
                remaining.append(_best_sense(defs))
        remaining.sort(key=lambda d: d.get("dict_death_year") or 9999)
        for d in remaining:
            if len(selected) >= MAX_TOP_DEFS:
                break
            selected.append(d)

    return selected


def _format_hypernym_chain(synset: dict) -> str:
    """Format the hypernym chain as a readable path."""
    chain = synset.get("hypernym_chain", {})
    path = chain.get("path", [])
    if not path:
        return "(no hypernym chain)"

    parts = []
    for ancestor in path:
        lemmas = ancestor.get("lemmas", [])
        lemma_str = "، ".join(lemmas[:3]) if lemmas else ancestor.get("id", "?")
        en = ancestor.get("oewn_lemmas_en")
        if en:
            lemma_str += f" ({', '.join(en[:2])})"
        parts.append(lemma_str)
    return " → ".join(parts)


def generate_summary(evidence: dict) -> str:
    """Generate a human-readable markdown summary from evidence data."""
    synset = evidence.get("synset", {})
    per_lemma = evidence.get("per_lemma", {})
    per_synset = evidence.get("per_synset", {})

    sid = synset.get("id", "?")
    pos = synset.get("pos", "?")
    lemmas = synset.get("lemmas", [])
    def_ar = synset.get("definition_ar", "")
    oewn = synset.get("oewn") or {}
    def_en = oewn.get("definition_en", "")
    lemmas_en = oewn.get("lemmas_en", [])

    lines = []

    # ── Header ────────────────────────────────────────────────────────────
    lines.append(f"# {sid} | {pos} | {def_ar}")
    lines.append("")
    if def_en:
        lines.append(f"> **EN:** {def_en}")
    lines.append(f"> **اللمّات:** {' ، '.join(lemmas)}")
    if lemmas_en:
        lines.append(f"> **OEWN:** {', '.join(lemmas_en)}")
    lines.append("")

    # ── Hypernym Chain ────────────────────────────────────────────────────
    lines.append("## سلسلة التعميم — Hypernym Chain")
    lines.append("")
    lines.append(_format_hypernym_chain(synset))
    lines.append("")

    # ── Relations ─────────────────────────────────────────────────────────
    relations = synset.get("relations", [])
    if relations:
        lines.append("## العلاقات — Relations")
        lines.append("")
        for rel in relations[:10]:
            rt = rel.get("rel_type", "?")
            tl = "، ".join(rel.get("target_lemmas", [])[:3])
            td = _truncate(rel.get("target_definition_ar", ""), 80)
            lines.append(f"- **{rt}:** {tl} — {td}")
        lines.append("")

    # ── Quick Stats ───────────────────────────────────────────────────────
    # Aggregate counts across all lemmas
    total_step1 = 0
    total_examples = 0
    total_root_family = 0
    all_entries = []
    for ld in per_lemma.values():
        step1 = ld.get("step1_headword", {})
        total_step1 += step1.get("result_count", 0)
        all_entries.extend(step1.get("entries", []))
        total_examples += ld.get("step6_examples", {}).get("result_count", 0)
        root_data = ld.get("step3_root_family", {})
        for root_info in root_data.get("by_root", {}).values():
            total_root_family += root_info.get("result_count", 0)

    period_counts = _count_by_period(all_entries)
    source_counts = _count_by_source_type(all_entries)
    unique_dicts = len({e.get("dict_key") for e in all_entries if e.get("dict_key")})

    lines.append("## إحصاءات سريعة — Quick Stats")
    lines.append("")
    lines.append("| المقياس — Metric | القيمة — Value |")
    lines.append("|-------------------|----------------|")
    lines.append(f"| اللمّات — Lemmas | {len(lemmas)} |")
    lines.append(f"| مطابقات معجمية — Dict hits | {total_step1} |")
    lines.append(f"| معاجم مختلفة — Distinct dicts | {unique_dicts} |")
    lines.append(f"| كلاسيكية — Classical | {period_counts.get('classical', 0)} |")
    lines.append(f"| حديثة — Modern | {period_counts.get('modern', 0)} |")
    lines.append(f"| ARABTERM | {source_counts.get('arabterm', 0)} |")
    lines.append(f"| شواهد — Examples | {total_examples} |")
    lines.append(f"| عائلة الجذر — Root family | {total_root_family} |")
    lines.append("")

    # ── Per-Lemma Sections ────────────────────────────────────────────────
    for lemma in lemmas:
        ld = per_lemma.get(lemma, {})
        if not ld:
            # Try bare form
            bare = strip_diacritics(lemma)
            for k, v in per_lemma.items():
                if strip_diacritics(k) == bare:
                    ld = v
                    break

        identity = ld.get("identity", {})
        lemma_bare = identity.get("lemma_bare", strip_diacritics(lemma))
        is_multiword = identity.get("is_multiword", False)

        lines.append("---")
        lines.append(f"## اللمّة — Lemma: {lemma} ({lemma_bare})")
        if is_multiword:
            components = identity.get("components", [])
            lines.append(f"> تركيب متعدد الكلمات — Multiword: {' + '.join(components)}")
        lines.append("")

        # Attestation overview
        step1 = ld.get("step1_headword", {})
        step1_entries = step1.get("entries", [])
        step1_count = step1.get("result_count", 0)
        pc = _count_by_period(step1_entries)
        sc = _count_by_source_type(step1_entries)

        lines.append("### التوثيق — Attestation")
        lines.append("")
        lines.append(f"- **مطابقات الراسمة:** {step1_count} معجم")
        if pc.get("classical"):
            classical_entries = [e for e in step1_entries if e.get("dict_period") == "classical"]
            lines.append(f"- **كلاسيكية:** {pc['classical']} ({_unique_dict_names(classical_entries)})")
        else:
            lines.append("- **كلاسيكية:** 0")
        if pc.get("modern"):
            modern_entries = [e for e in step1_entries if e.get("dict_period") == "modern"]
            lines.append(f"- **حديثة:** {pc.get('modern', 0)} ({_unique_dict_names(modern_entries)})")
        if sc.get("arabterm"):
            at_entries = [e for e in step1_entries if e.get("dict_source_type") == "arabterm"]
            domains = {e.get("domain", "") for e in at_entries if e.get("domain")}
            domain_str = "، ".join(list(domains)[:3]) if domains else ""
            lines.append(f"- **ARABTERM:** {sc['arabterm']} ({domain_str})")
        lines.append("")

        # Multiword component results
        if is_multiword:
            by_comp = step1.get("by_component") or {}
            if by_comp:
                lines.append("#### المكوّنات — Components")
                lines.append("")
                for comp_word, comp_data in by_comp.items():
                    comp_count = comp_data.get("result_count", 0)
                    proclitic = comp_data.get("proclitic_stripped")
                    if proclitic:
                        lines.append(f"- **{comp_word}** → جذع: {proclitic.get('stem', '?')} — {proclitic.get('result_count', 0)} مطابقة")
                    else:
                        lines.append(f"- **{comp_word}**: {comp_count} مطابقة")
                lines.append("")

        # Top definitions
        top_defs = _select_top_definitions(ld, def_ar)
        if top_defs:
            lines.append("### أهم التعريفات — Top Definitions")
            lines.append("")
            for d in top_defs:
                name = d.get("dict_name_ar") or d.get("dict_name_en") or d.get("dict_key", "")
                dy = d.get("dict_death_year")
                dy_str = f"ت {dy}" if dy else "حديث"
                text = _truncate(d["text"], 300)
                lines.append(f"> **{name}** ({dy_str}):")
                lines.append(f"> {text}")
                lines.append("")

        # Root info
        root_data = ld.get("step3_root_family", {})
        roots_found = root_data.get("roots_found", [])
        by_root = root_data.get("by_root", {})

        if roots_found:
            lines.append("### الجذر — Root")
            lines.append("")
            primary_root = roots_found[0]
            lines.append(f"- **الجذر:** {primary_root.get('root', '?')} (المصدر: {primary_root.get('root_source', '?')})")
            # Deduplicate alternative roots by (root, root_source) pair
            seen_roots = {(primary_root.get("root"), primary_root.get("root_source"))}
            alt_unique = []
            for r in roots_found[1:]:
                key = (r.get("root"), r.get("root_source"))
                if key not in seen_roots:
                    seen_roots.add(key)
                    alt_unique.append(r)
            if alt_unique:
                alt_roots = ", ".join(f"{r['root']} ({r['root_source']})" for r in alt_unique)
                lines.append(f"- **جذور بديلة:** {alt_roots}")

            # Root family headwords
            root_str = primary_root.get("root", "")
            family = by_root.get(root_str, {})
            family_entries = family.get("entries", [])
            family_count = family.get("result_count", 0)
            if family_entries:
                # Get unique headwords sorted by how many dictionaries attest them
                hw_counter: Counter = Counter()
                for e in family_entries:
                    hw = e.get("headword_bare") or e.get("headword", "")
                    if hw:
                        hw_counter[hw] += 1
                top_hw = hw_counter.most_common(MAX_ROOT_FAMILY_HEADWORDS)
                hw_str = "، ".join(f"{hw} ({n})" for hw, n in top_hw)
                lines.append(f"- **عائلة الجذر:** {family_count} مدخل — أبرز المشتقات: {hw_str}")
            lines.append("")

        # Synonym candidates from reverse lookup
        step8 = ld.get("step8_reverse_lookup", {})
        step8_entries = step8.get("entries", [])
        if step8_entries:
            lines.append("### مرشحات الترادف (بحث عكسي) — Synonym Candidates")
            lines.append("")
            lines.append("| المرشح | المعجم | المعنى |")
            lines.append("|--------|--------|--------|")
            seen_hw = set()
            count = 0
            for e in step8_entries:
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
            lines.append("")

        # Usage examples
        step6 = ld.get("step6_examples", {})
        examples = step6.get("examples", [])
        if examples:
            lines.append("### الشواهد — Usage Examples")
            lines.append("")
            for ex in examples[:MAX_EXAMPLES]:
                ex_type = ex.get("type", "usage")
                ex_text = _truncate(ex.get("text", ""), 200)
                attr = ex.get("attribution", "")
                dk_name = ex.get("dict_name_ar") or ex.get("dict_name_en") or ""
                attr_str = f" — {attr}" if attr else ""
                lines.append(f"- **[{ex_type}]** {ex_text}{attr_str} ({dk_name})")
            if len(examples) > MAX_EXAMPLES:
                lines.append(f"- *(+{len(examples) - MAX_EXAMPLES} more)*")
            lines.append("")

    # ── Per-Synset Sections ───────────────────────────────────────────────

    # FTS keyword results
    step4 = per_synset.get("step4_fts_keyword", {})
    step4_entries = step4.get("entries", [])
    keywords_extracted = step4.get("keywords_extracted", [])
    if step4_entries:
        lines.append("---")
        lines.append("## نتائج البحث النصي (الخطوة ٤) — FTS Keyword Results")
        lines.append("")
        lines.append(f"**كلمات مفتاحية:** {' '.join(keywords_extracted)}")
        lines.append(f"**النتائج:** {step4.get('result_count', 0)} مدخل")
        lines.append("")
        lines.append("| الراسمة | المعجم | المعنى |")
        lines.append("|---------|--------|--------|")
        for e in step4_entries[:MAX_FTS_RESULTS]:
            hw = _safe_headword(e)
            dk_name = _truncate(e.get("dict_name_ar") or e.get("dict_name_en") or "", 25)
            def_text = _truncate(e.get("definitions_text", ""), 100)
            lines.append(f"| {hw} | {dk_name} | {def_text} |")
        lines.append("")

    # English bridge / ARABTERM
    step5 = per_synset.get("step5_english_bridge", {})
    step5_entries = step5.get("entries", [])
    en_terms = step5.get("english_terms_used", [])
    if step5_entries:
        lines.append("## الجسر الإنجليزي / ARABTERM (الخطوة ٥) — English Bridge")
        lines.append("")
        lines.append(f"**مصطلحات إنجليزية:** {', '.join(en_terms)}")
        lines.append(f"**النتائج:** {step5.get('result_count', 0)} مدخل")
        lines.append("")
        lines.append("| المصطلح العربي | الترجمة | المجال | المعجم |")
        lines.append("|---------------|---------|--------|--------|")
        for e in step5_entries[:MAX_ENGLISH_BRIDGE]:
            hw = _safe_headword(e, max_len=80)
            tr = _truncate(e.get("translation_en", ""), 40)
            domain = _truncate(e.get("domain", ""), 30)
            dk_name = _truncate(e.get("dict_name_ar") or e.get("dict_name_en") or "", 25)
            lines.append(f"| {hw} | {tr} | {domain} | {dk_name} |")
        lines.append("")

    # ── Decision Prompts ──────────────────────────────────────────────────
    lines.append("---")
    lines.append("## أسئلة القرار — Decision Prompts")
    lines.append("")
    lines.append("### التحقق من اللمّات (الخطوة ١)")
    lines.append("")
    if len(lemmas) > 1:
        for i, l1 in enumerate(lemmas):
            for l2 in lemmas[i + 1:]:
                lines.append(f"- [ ] اختبار الإبدال: هل يمكن استبدال «{strip_diacritics(l1)}» بـ «{strip_diacritics(l2)}» في السياقات المعتادة؟")
        lines.append("")
    for lem in lemmas:
        lines.append(f"- [ ] ما يميّز «{strip_diacritics(lem)}» عن أخواتها (الفارق الدقيق)؟")
    lines.append("")

    lines.append("### تدقيق التعريف (الخطوة ٣)")
    lines.append("")
    lines.append(f"- [ ] تعريف AWN: «{def_ar}» — هل يطابق المعاجم؟")
    lines.append("- [ ] ألّف تعريفاً مصطلحياً (الجنس القريب + الفصل النوعي)")
    lines.append("")

    # Hypernym check
    hypernyms = [r for r in relations if r.get("rel_type") == "hypernym"]
    if hypernyms:
        h = hypernyms[0]
        h_lemmas = "، ".join(h.get("target_lemmas", [])[:3])
        lines.append("### فحص العلاقات (الخطوة ٤)")
        lines.append("")
        first_lemma = strip_diacritics(lemmas[0]) if lemmas else "?"
        lines.append(f"- [ ] هل «{first_lemma}» هي فعلاً نوع من «{h_lemmas}»؟")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Review Template Generation
# ═══════════════════════════════════════════════════════════════════════════════

def _yaml_str(s: str) -> str:
    """Quote a string for safe YAML output."""
    if not s:
        return '""'
    # Quote if it contains special characters
    if any(c in s for c in ":{}[],'\"&*?|>!%@`#"):
        s = s.replace('"', '\\"')
        return f'"{s}"'
    return f'"{s}"'


def generate_review_template(evidence: dict) -> str:
    """Generate a pre-filled review YAML template from evidence data."""
    synset = evidence.get("synset", {})
    per_lemma = evidence.get("per_lemma", {})

    sid = synset.get("id", "")
    lemmas = synset.get("lemmas", [])
    def_ar = synset.get("definition_ar", "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = []
    lines.append("# ══════════════════════════════════════════════════════════════")
    lines.append(f"# Stage 2 Review — {sid}")
    lines.append(f"# Generated: {now}")
    lines.append("# Evidence: evidence.yaml | Summary: summary.md")
    lines.append("# Guide: docs/STAGE2_GUIDE.md | Schema: docs/REVIEW_SCHEMA.md")
    lines.append("# ══════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append(f"synset_id: {_yaml_str(sid)}")
    lines.append('reviewer: ""')
    lines.append('review_date: ""')
    lines.append("status: pending")
    lines.append("")

    # Analysis
    lines.append("# ═══════════════════════════════════════")
    lines.append("# التحليل — Analysis")
    lines.append("# ═══════════════════════════════════════")
    lines.append("analysis:")
    lines.append('  initial_impression: ""')
    lines.append('  key_evidence: ""')
    lines.append('  concerns: ""')
    lines.append("")

    # Definition
    lines.append("# ═══════════════════════════════════════")
    lines.append("# التعريف — Definition")
    lines.append("# ═══════════════════════════════════════")
    lines.append("definition:")
    lines.append(f"  awn_gloss: {_yaml_str(def_ar)}")
    lines.append('  verdict: ""                           # retain | revise | reject')
    lines.append('  revised_text: ""')
    lines.append('  notes: ""')
    lines.append("")

    # Authored definitions
    lines.append("authored_definitions:")
    lines.append('  terminological: ""                    # إلزامي — REQUIRED')
    lines.append('  linguistic: ""')
    lines.append('  encyclopedic: ""')
    lines.append("  quality_check:")
    lines.append("    clarity: null")
    lines.append("    conciseness: null")
    lines.append("    equivalence: null")
    lines.append("    positive: null")
    lines.append("    no_tautology: null")
    lines.append("")

    # Lemmas
    lines.append("# ═══════════════════════════════════════")
    lines.append("# اللمّات — Lemmas")
    lines.append("# ═══════════════════════════════════════")
    lines.append("lemmas:")

    for lemma in lemmas:
        # Find root from evidence
        ld = per_lemma.get(lemma, {})
        if not ld:
            bare = strip_diacritics(lemma)
            for k, v in per_lemma.items():
                if strip_diacritics(k) == bare:
                    ld = v
                    break

        root_data = ld.get("step3_root_family", {})
        roots = root_data.get("roots_found", [])
        root_str = roots[0]["root"] if roots else ""
        root_source = roots[0]["root_source"] if roots else ""

        lines.append(f"  - lemma: {_yaml_str(lemma)}")
        lines.append('    status: ""                         # confirmed | rejected | modified')
        lines.append(f"    root: {_yaml_str(root_str)}")
        lines.append(f"    root_source: {_yaml_str(root_source)}")
        lines.append('    usage: ""                          # archaic | modern | common')
        lines.append('    eloquence: ""                      # eloquent | neologism | colloquial')
        lines.append('    connotation: ""                    # positive | negative | reverential | pejorative | neutral')
        lines.append('    literal_figurative: ""             # literal | figurative')
        lines.append('    figurative_relation: ""')
        lines.append('    syntactic_frame: ""                # لازم | متعدٍ بنفسه | متعدٍ بـ')
        lines.append('    typical_collocate: ""')
        lines.append('    nuance_note: ""                    # إلزامي — REQUIRED')
        lines.append('    source: ""')
        lines.append("    morpho_check:")
        lines.append('      result: ""                       # ok | root_corrected | orthography_fixed')
        lines.append('      notes: ""')
        lines.append("")

    # Missing lemmas
    lines.append("# ═══════════════════════════════════════")
    lines.append("# اللمّات المفقودة — Missing Lemmas")
    lines.append("# ═══════════════════════════════════════")
    lines.append("missing_lemmas: []")
    lines.append("# - candidate: \"\"")
    lines.append("#   verdict: \"\"                         # add_lemma | propose_new_synset | reject_candidate")
    lines.append("#   reason: \"\"")
    lines.append("")

    # Examples
    lines.append("# ═══════════════════════════════════════")
    lines.append("# الأمثلة — Examples")
    lines.append("# ═══════════════════════════════════════")
    lines.append("examples: []")
    lines.append("# - type: \"\"                            # quran | hadith | poetry | prose | authored")
    lines.append("#   text: \"\"")
    lines.append("#   source: \"\"")
    lines.append("")

    # Relations
    lines.append("# ═══════════════════════════════════════")
    lines.append("# العلاقات — Relations")
    lines.append("# ═══════════════════════════════════════")
    lines.append("relations:")
    relations = synset.get("relations", [])
    hypernyms = [r for r in relations if r.get("rel_type") == "hypernym"]
    if hypernyms:
        h = hypernyms[0]
        h_id = h.get("target_id", "")
        h_lemmas = h.get("target_lemmas", [])
        lines.append("  hypernym:")
        lines.append(f"    target: {_yaml_str(h_id)}")
        h_lemmas_str = "[" + ", ".join(_yaml_str(l) for l in h_lemmas) + "]"
        lines.append(f"    target_lemmas: {h_lemmas_str}")
        lines.append('    verdict: ""                       # ok | flag')
        lines.append('    note: ""')
    else:
        lines.append("  hypernym:")
        lines.append('    target: ""')
        lines.append("    target_lemmas: []")
        lines.append('    verdict: ""')
        lines.append('    note: ""')
    lines.append("")

    # Cultural fit
    lines.append("# ═══════════════════════════════════════")
    lines.append("# الملاءمة الثقافية — Cultural Fit")
    lines.append("# ═══════════════════════════════════════")
    lines.append("cultural_fit:")
    lines.append('  lexical_gap_type: ""                  # direct | near_synonym | phraset | lexical_gap | omission')
    lines.append('  note: ""')
    lines.append("")

    # Scoring
    lines.append("# ═══════════════════════════════════════")
    lines.append("# التقييم — Scoring")
    lines.append("# ═══════════════════════════════════════")
    lines.append("scoring:")
    lines.append("  semantic_accuracy: null               # 0–3")
    lines.append("  gloss_quality: null                   # 0–3")
    lines.append("  synonym_coherence: null               # 0–2")
    lines.append("  completeness: null                    # 0–2")
    lines.append('  cultural_adequacy: ""                 # direct | near_synonym | phraset | lexical_gap | omission')
    lines.append('  overall: ""                           # excellent | good | acceptable | poor')
    lines.append("")

    # Flags and actions
    lines.append("# ═══════════════════════════════════════")
    lines.append("# الأعلام والإجراءات — Flags & Actions")
    lines.append("# ═══════════════════════════════════════")
    lines.append("flags: []")
    lines.append("actions: []")
    lines.append("# - {action: \"\", target: \"\", note: \"\"}")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Output Writing
# ═══════════════════════════════════════════════════════════════════════════════

def write_output(
    synset_id: str,
    summary_md: str,
    review_yaml: str,
    evidence: dict,
    output_dir: Path,
    write_raw: bool = True,
) -> Path:
    """Write all output files to output/{synset_id}/."""
    synset_dir = output_dir / synset_id
    synset_dir.mkdir(parents=True, exist_ok=True)

    # Summary
    (synset_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    # Review template
    (synset_dir / "review.yaml").write_text(review_yaml, encoding="utf-8")

    # Raw evidence (decompressed)
    if write_raw:
        with open(synset_dir / "evidence.yaml", "w", encoding="utf-8") as f:
            yaml.dump(evidence, f, allow_unicode=True,
                      default_flow_style=False, sort_keys=False, width=120)

    return synset_dir


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Prepare Stage 2 review materials for AWN4 synsets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s awn4-01572394-v                    # single synset
  %(prog)s awn4-01572394-v awn4-03466051-n    # multiple synsets
  %(prog)s --batch batches/my_batch.txt       # from batch file
  %(prog)s --no-raw awn4-01572394-v           # skip decompressing raw evidence
""",
    )
    parser.add_argument("synset_ids", nargs="*", help="Synset IDs to prepare")
    parser.add_argument("--batch", "-b", metavar="FILE",
                        help="Batch file with synset IDs (one per line)")
    parser.add_argument("--output-dir", "-o", default="output",
                        help="Output directory (default: output)")
    parser.add_argument("--evidence-dir", "-e", default=None,
                        help="Evidence directory (auto-detected if not specified)")
    parser.add_argument("--no-raw", action="store_true",
                        help="Skip writing decompressed evidence.yaml")
    args = parser.parse_args()

    workspace = Path(__file__).resolve().parent.parent

    # Collect target IDs
    target_ids: list[str] = list(args.synset_ids)
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.is_absolute():
            batch_path = workspace / args.batch
        with open(batch_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Support various formats: plain ID, YAML synset_id: ..., markdown list
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

    # Resolve output directory
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = workspace / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process synsets
    ok = 0
    fail = 0
    for i, sid in enumerate(target_ids, 1):
        print(f"[{i}/{len(target_ids)}] {sid}...", end=" ", file=sys.stderr, flush=True)
        try:
            evidence = load_evidence(sid, evidence_dir)
            summary_md = generate_summary(evidence)
            review_yaml = generate_review_template(evidence)
            synset_dir = write_output(sid, summary_md, review_yaml, evidence,
                                      output_dir, write_raw=not args.no_raw)
            print(f"-> {synset_dir.relative_to(workspace)}", file=sys.stderr)
            ok += 1
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            fail += 1

    print(f"\nDone. {ok} prepared, {fail} failed.", file=sys.stderr)
    if ok > 0:
        print(f"Output: {output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
