#!/usr/bin/env python3
"""Generate .md review documents for AWN4 synsets.

For each synset, aggregates information from:
  - AWN4 XML (definition, examples, relations, lemmas)
  - OEWN English equivalents (via ILI cross-lingual index from ColBERT metadata)
  - Arabic dictionaries DB (classical/modern dictionary entries per lemma)
  - ARABTERM (multilingual technical terminology per lemma)
  - Hawramani Arabic Lexicon (53 classical/modern dictionaries, scraped cache)
  - Almaany (المعاني الجامع + قاموس الكل, scraped cache)
  - Connected synsets (1-hop relations with their own dictionary evidence)

Usage:
    python generate_synset_review.py --sample output/random_synset_sample.json
    python generate_synset_review.py --synset awn4-04875102-n
"""

import argparse
import json
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT_DIR = SCRIPT_DIR.parent  # synset_linguistic_audit/
AWN4_BASE = AUDIT_DIR.parent.parent  # arabic-wordnet-v4/
AWN4_XML = AWN4_BASE / "output" / "awn4.xml"
DICT_DB = AWN4_BASE.parent / "arabic-dictionaries" / "db" / "arabic_dict.db"
COLBERT_META_DIR = AWN4_BASE / "experiments" / "colbertv2 exp" / "metadata"
HAWRAMANI_CACHE = SCRIPT_DIR / "output" / "hawramani_cache.json"
ALMAANY_CACHE = SCRIPT_DIR / "output" / "almaany_cache.json"

# ─── Arabic normalization ─────────────────────────────────────────────────────

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
HAMZA_NORM = str.maketrans({
    "\u0623": "\u0627",  # أ → ا
    "\u0625": "\u0627",  # إ → ا
    "\u0622": "\u0627",  # آ → ا
    "\u0624": "\u0648",  # ؤ → و
    "\u0626": "\u064A",  # ئ → ي
})
HAMZA_REVERSE = str.maketrans({
    "\u064A": "\u0626",  # ي → ئ  (reverse: catches DB entries with hamza-on-ya)
    "\u0648": "\u0624",  # و → ؤ  (reverse: catches DB entries with hamza-on-waw)
})

POS_LABELS = {"n": "اسم — noun", "v": "فعل — verb", "a": "صفة — adjective", "r": "ظرف — adverb"}

RELATION_LABELS = {
    "hypernym": "تعميم (hypernym)",
    "hyponym": "تخصيص (hyponym)",
    "instance_hypernym": "تعميم مثال (instance hypernym)",
    "instance_hyponym": "تخصيص مثال (instance hyponym)",
    "mero_part": "جزء من (part meronym)",
    "holo_part": "يتكون من (part holonym)",
    "mero_member": "عضو في (member meronym)",
    "holo_member": "مجموعة تضم (member holonym)",
    "mero_substance": "مادة من (substance meronym)",
    "holo_substance": "يحتوي مادة (substance holonym)",
    "similar": "مشابه (similar)",
    "also": "انظر أيضاً (also)",
    "attribute": "صفة (attribute)",
    "domain_topic": "مجال (domain topic)",
    "has_domain_topic": "ينتمي لمجال (has domain topic)",
    "domain_region": "منطقة (domain region)",
    "has_domain_region": "ينتمي لمنطقة (has domain region)",
    "exemplifies": "مثال على (exemplifies)",
    "is_exemplified_by": "مُثال بـ (is exemplified by)",
    "entails": "يستلزم (entails)",
    "causes": "يسبب (causes)",
}


def strip_diacritics(text):
    return DIACRITICS_RE.sub("", text)


# ─── AWN4 XML parsing ─────────────────────────────────────────────────────────


def parse_awn4(xml_path):
    """Parse AWN4 XML into synset and lemma maps."""
    print(f"  Parsing AWN4 XML: {xml_path}")
    t0 = time.time()
    tree = ET.parse(xml_path)
    root = tree.getroot()
    lexicon = root.find("Lexicon")

    # Build synset_id → lemma list
    synset_lemmas = {}
    for entry in lexicon.findall("LexicalEntry"):
        eid = entry.get("id")
        lemma_el = entry.find("Lemma")
        wf = lemma_el.get("writtenForm")
        pos = lemma_el.get("partOfSpeech")
        for sense in entry.findall("Sense"):
            sid = sense.get("synset")
            if sid not in synset_lemmas:
                synset_lemmas[sid] = []
            synset_lemmas[sid].append({
                "writtenForm": wf,
                "partOfSpeech": pos,
                "entry_id": eid,
                "sense_id": sense.get("id"),
                "sense_number": sense.get("n"),
            })

    # Build synset_id → synset data
    synsets = {}
    for syn_el in lexicon.findall("Synset"):
        sid = syn_el.get("id")
        definitions = [d.text for d in syn_el.findall("Definition") if d.text]
        examples = [e.text for e in syn_el.findall("Example") if e.text]
        relations = []
        for rel in syn_el.findall("SynsetRelation"):
            relations.append({
                "relType": rel.get("relType"),
                "target": rel.get("target"),
            })
        synsets[sid] = {
            "id": sid,
            "ili": syn_el.get("ili") or "",
            "partOfSpeech": syn_el.get("partOfSpeech"),
            "definitions": definitions,
            "examples": examples,
            "relations": relations,
            "lemmas": synset_lemmas.get(sid, []),
        }

    print(f"  Parsed {len(synsets):,} synsets, {sum(len(v) for v in synset_lemmas.values()):,} senses in {time.time()-t0:.1f}s")
    return synsets, synset_lemmas


# ─── OEWN English equivalents (via ILI metadata) ────────────────────────────


class OEWNLookup:
    """Loads ColBERT metadata for ILI → OEWN English equivalent lookups.

    Note: This only uses the pre-built metadata JSON files (ILI map +
    synset metadata), NOT the ColBERT model or index. The ColBERT index
    currently lacks dict/ARABTERM embeddings; see research/README.md for details.
    """

    def __init__(self, meta_dir):
        meta_path = meta_dir / "synset_metadata.json"
        ili_path = meta_dir / "ili_map.json"
        print("  Loading ILI metadata for OEWN lookups...")
        with open(meta_path) as f:
            self.metadata = json.load(f)
        with open(ili_path) as f:
            self.ili_map = json.load(f)
        print(f"    {len(self.ili_map):,} ILI entries")

    def get_oewn_equivalent(self, ili):
        """Look up OEWN English equivalent via ILI."""
        if not ili or ili not in self.ili_map:
            return None
        for doc_id in self.ili_map[ili]:
            if doc_id.startswith("oewn-"):
                return self.metadata.get(doc_id)
        return None


# ─── Dictionary DB queries ─────────────────────────────────────────────────────


def _generate_headword_variants(bare_form):
    """Generate candidate headword_bare values in priority order.

    Produces (variant_string, match_type) tuples for a 3-tier cascade:
      Tier 1 — exact bare form
      Tier 2 — ال definite article added/stripped
      Tier 3 — hamza normalization, reverse hamza, taa marbuta, geminates,
               prepositional prefix stripping — each also tried with/without ال
    """
    variants = []

    # Tier 1: exact
    variants.append((bare_form, "exact"))

    # Tier 2: ال prefix
    if not bare_form.startswith("ال"):
        variants.append(("ال" + bare_form, "al_prefix"))
    else:
        variants.append((bare_form[2:], "al_prefix"))

    # Tier 3a: hamza forward normalization (أ→ا, ئ→ي, ؤ→و)
    normalized = bare_form.translate(HAMZA_NORM)
    if normalized != bare_form:
        variants.append((normalized, "hamza_normalized"))
        if not normalized.startswith("ال"):
            variants.append(("ال" + normalized, "hamza_normalized"))

    # Tier 3b: hamza reverse (ي→ئ, و→ؤ) — catches DB entries with hamza carriers
    reversed_hz = bare_form.translate(HAMZA_REVERSE)
    if reversed_hz != bare_form:
        variants.append((reversed_hz, "hamza_normalized"))
        if not reversed_hz.startswith("ال"):
            variants.append(("ال" + reversed_hz, "hamza_normalized"))

    # Tier 3c: taa marbuta (ة ↔ ه)
    if bare_form.endswith("ة"):
        base = bare_form[:-1]
        variants.append((base + "ه", "taa_marbuta"))
        variants.append(("ال" + base + "ه", "taa_marbuta"))
        if len(base) >= 2:
            variants.append((base, "taa_marbuta"))
            variants.append(("ال" + base, "taa_marbuta"))
    elif bare_form.endswith("ه") and len(bare_form) >= 3:
        base = bare_form[:-1]
        variants.append((base + "ة", "taa_marbuta"))
        variants.append(("ال" + base + "ة", "taa_marbuta"))

    # Tier 3d: geminate root collapse/expansion (مدد→مد or مد→مدد)
    if len(bare_form) >= 3 and bare_form[-1] == bare_form[-2]:
        collapsed = bare_form[:-1]
        variants.append((collapsed, "geminate"))
        variants.append(("ال" + collapsed, "geminate"))
    if len(bare_form) == 2:
        expanded = bare_form + bare_form[-1]
        variants.append((expanded, "geminate"))
        variants.append(("ال" + expanded, "geminate"))

    # Tier 3e: prepositional prefix (بال/وال/كال → strip prefix, try with/without ال)
    for prefix in ("بال", "وال", "كال"):
        if bare_form.startswith(prefix) and len(bare_form) > len(prefix) + 1:
            stem = bare_form[len(prefix):]
            variants.append(("ال" + stem, "prep_stripped"))
            variants.append((stem, "prep_stripped"))

    # Deduplicate while preserving priority order
    seen = set()
    result = []
    for v, mt in variants:
        if v and v not in seen:
            seen.add(v)
            result.append((v, mt))
    return result


def _is_subsequence(letters, text):
    """Check if `letters` appear as an ordered subsequence in `text`."""
    j = 0
    for ch in text:
        if j < len(letters) and ch == letters[j]:
            j += 1
    return j == len(letters)


def _resolve_hamza_via_lex(root_dotted, lex_bare_set):
    """Resolve '#' in a CAMeL root by subsequence-matching against lex forms.

    For roots with a single '#', tries each hamza variant and checks whether
    the resulting root letters appear as an ordered subsequence in the lex_bare.
    This disambiguates e.g. #.ج.ر → أجر (from lex مأجور) vs وجر.

    Returns a list of resolved root_joined strings, or None if unresolvable.
    """
    root_letters = root_dotted.split(".")
    hamza_positions = [i for i, l in enumerate(root_letters) if l == "#"]
    if not hamza_positions:
        return ["".join(root_letters)]
    if len(hamza_positions) > 1:
        return None  # multi-# roots: fall back to brute-force expansion

    REPLACEMENTS = ("أ", "و", "ي", "ء", "ا")
    resolved = []
    for r in REPLACEMENTS:
        candidate = [r if l == "#" else l for l in root_letters]
        for lex_bare in lex_bare_set:
            if _is_subsequence(candidate, lex_bare):
                resolved.append("".join(candidate))
                break
    return resolved or None


def _camel_root_to_db_variants(camel_root):
    """Convert a CAMeL Tools root (e.g. '#.ص.ل') to DB root_joined candidates.

    CAMeL uses '#' for the hamza radical, which can correspond to أ, و, ي, or ء
    in the actual root.  For single-# roots, tries each replacement.  For
    multi-# roots (e.g. ر.#.#), generates the cross-product of replacements
    capped at 25 variants to avoid combinatorial explosion.
    """
    letters = camel_root.split(".")
    hamza_positions = [i for i, l in enumerate(letters) if l == "#"]
    if not hamza_positions:
        return ["".join(letters)]

    REPLACEMENTS = ("أ", "و", "ي", "ء", "ا")
    if len(hamza_positions) == 1:
        return ["".join(r if l == "#" else l for l in letters)
                for r in REPLACEMENTS]

    # Multi-#: cross-product, capped
    from itertools import product
    variants = []
    for combo in product(REPLACEMENTS, repeat=len(hamza_positions)):
        result = list(letters)
        for pos, repl in zip(hamza_positions, combo):
            result[pos] = repl
        variants.append("".join(result))
        if len(variants) >= 25:
            break
    return variants


def _derive_root_candidates(bare_form, morph_analyzer=None):
    """Derive candidate roots for a bare Arabic word.

    If morph_analyzer (CAMeL Tools Analyzer) is provided, uses it for
    linguistically accurate morphological decomposition (handles all Forms I-X,
    broken plurals, quadriliterals, prepositional prefixes, etc.).

    Uses a two-phase approach:
      Phase 1 — Surface-matched analyses: only analyses whose diacritized form
                matches the input (after stripping diacritics).  For roots with
                '#', resolves the hamza letter via subsequence matching against
                the lexeme citation form.
      Phase 2 — All analyses (fallback): if Phase 1 yields nothing, uses all
                analyses ranked by frequency with brute-force hamza expansion.

    Falls back to regex-based heuristics if no analyzer is available.
    Returns a list of root strings to query against root_joined.
    """
    candidates = []

    # ── CAMeL Tools morphological analysis (preferred) ──
    if morph_analyzer is not None:
        analyses = morph_analyzer.analyze(bare_form)

        # Phase 1: surface-matched analyses (diac_bare == input)
        surface_root_counts = {}
        surface_root_lexes = {}
        for a in analyses:
            root = a.get("root", "")
            if root and root not in ("NTWS", "FOREIGN", "ntws"):
                diac_bare = DIACRITICS_RE.sub("", a.get("diac", ""))
                if diac_bare == bare_form:
                    surface_root_counts[root] = surface_root_counts.get(root, 0) + 1
                    lex_bare = DIACRITICS_RE.sub("", a.get("lex", ""))
                    surface_root_lexes.setdefault(root, set()).add(lex_bare)

        if surface_root_counts:
            sorted_roots = sorted(surface_root_counts,
                                  key=lambda r: -surface_root_counts[r])
            for root in sorted_roots:
                joined = root.replace(".", "")
                if "#" not in joined:
                    candidates.append(joined)
                else:
                    resolved = _resolve_hamza_via_lex(
                        root, surface_root_lexes.get(root, set()))
                    if resolved:
                        candidates.extend(resolved)
                    else:
                        candidates.extend(_camel_root_to_db_variants(root))

        # Phase 2: all analyses fallback (if Phase 1 yielded nothing)
        if not candidates:
            all_root_counts = {}
            for a in analyses:
                root = a.get("root", "")
                if root and root not in ("NTWS", "FOREIGN", "ntws"):
                    all_root_counts[root] = all_root_counts.get(root, 0) + 1
            all_sorted = sorted(all_root_counts,
                                key=lambda r: -all_root_counts[r])
            for root in all_sorted:
                candidates.extend(_camel_root_to_db_variants(root))

        # Apply hamza normalization to expand matching
        expanded = []
        for c in candidates:
            expanded.append(c)
            normed = c.translate(HAMZA_NORM)
            if normed != c:
                expanded.append(normed)
        candidates = expanded

    # ── Regex fallback (no CAMeL Tools) ──
    if not candidates:
        stem = bare_form[2:] if bare_form.startswith("ال") else bare_form
        for prefix in ("بال", "وال", "كال"):
            if bare_form.startswith(prefix) and len(bare_form) > len(prefix) + 1:
                stem = bare_form[len(prefix):]
                break
        n = len(stem)

        if n == 5:
            if stem[0] == "م" and stem[3] == "و":  # مفعول
                candidates.append(stem[1] + stem[2] + stem[4])
            if stem[0] == "م" and stem[2] == "ا":  # مُفاعِل
                candidates.append(stem[1] + stem[3] + stem[4])
            if stem[0] == "ت":  # تَفَعُّل
                candidates.append(stem[1] + stem[2] + stem[3])
                candidates.append(stem[1] + stem[2] + stem[4])
            if stem[0] in ("إ", "أ", "ا") and stem[3] == "ا":  # إفعال
                candidates.append(stem[1] + stem[2] + stem[4])
        if n == 4:
            if stem[2] == "ا":  # فِعال
                candidates.append(stem[0] + stem[1] + stem[3])
            if stem[1] == "ا":  # فاعِل
                candidates.append(stem[0] + stem[2] + stem[3])
            if stem[-1] in ("ة", "ه"):  # فَعْلة
                candidates.append(stem[0] + stem[1] + stem[2])
            if stem[2] == "و":  # فعول
                candidates.append(stem[0] + stem[1] + stem[3])
            if stem[0] in ("أ", "إ", "ا"):  # أَفْعَل
                candidates.append(stem[1] + stem[2] + stem[3])
        if n == 3:
            candidates.append(stem)
        if n == 2:
            candidates.append(stem + stem[-1])

        # Apply hamza normalization to regex-derived candidates
        expanded = []
        for c in candidates:
            expanded.append(c)
            normed = c.translate(HAMZA_NORM)
            if normed != c:
                expanded.append(normed)
        candidates = expanded

    # Deduplicate while preserving priority order
    seen = set()
    return [c for c in candidates if c and not (c in seen or seen.add(c))]


def query_dict_entries(db_path, bare_form, morph_analyzer=None):
    """Query arabic_dict.db for entries matching a bare (undiacritized) form.

    Uses a 5-tier Arabic-aware lookup cascade:
      Tier 1 — exact headword_bare match
      Tier 2 — ال-prefixed / stripped match
      Tier 3 — hamza / taa-marbuta / geminate / preposition variants
      Tier 4 — root-based lookup (CAMeL morphological analyzer, or regex fallback)
      Tier 5 — FTS definition mention (low confidence, last resort)

    Returns (entries, match_type) describing how the match was found.
    """
    cols = "source, headword, pos, form, definitions, plurals, examples"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # ── Tiers 1–3: headword variant matching ──
    for variant, match_type in _generate_headword_variants(bare_form):
        rows = conn.execute(
            f"SELECT {cols} FROM entries WHERE headword_bare = ?",
            (variant,),
        ).fetchall()
        if rows:
            conn.close()
            return [dict(r) for r in rows], match_type

    # ── Tier 4: root-based lookup ──
    for candidate in _derive_root_candidates(bare_form, morph_analyzer):
        rows = conn.execute(
            f"SELECT {cols} FROM entries WHERE root_joined = ? "
            "ORDER BY CASE WHEN pos = 'verb' THEN 0 WHEN pos = 'noun' THEN 1 ELSE 2 END "
            "LIMIT 12",
            (candidate,),
        ).fetchall()
        if rows:
            conn.close()
            return [dict(r) for r in rows], f"root ({candidate})"

    # ── Tier 5: FTS definition mention (last resort) ──
    if len(bare_form) >= 3:
        rows = conn.execute(
            "SELECT e.source, e.headword, e.pos, e.form, e.definitions, e.plurals, e.examples "
            "FROM entries_fts fts "
            "JOIN entries e ON e.id = fts.rowid "
            "WHERE entries_fts MATCH ? "
            "LIMIT 8",
            (f'definitions_text:"{bare_form}"',),
        ).fetchall()
        if rows:
            conn.close()
            return [dict(r) for r in rows], "definition_mention"

    conn.close()
    return [], "none"


def query_arabterm(db_path, bare_form):
    """Query arabterm_terms for entries matching a bare form."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT arabic, english, french, description, domain "
        "FROM arabterm_terms WHERE arabic_bare = ?",
        (bare_form,),
    ).fetchall()
    conn.close()

    # Deduplicate by (english, domain)
    seen = set()
    deduped = []
    for r in rows:
        r = dict(r)
        key = (r.get("english", ""), r.get("domain", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


# ─── External scraped caches ──────────────────────────────────────────────────


class ScrapedCaches:
    """Loads Hawramani and Almaany scraped caches (JSON files)."""

    def __init__(self, hawramani_path=None, almaany_path=None):
        self.hawramani = {}
        self.almaany = {}

        if hawramani_path and Path(hawramani_path).exists():
            with open(hawramani_path) as f:
                self.hawramani = json.load(f)
            print(f"    Hawramani cache: {len(self.hawramani)} entries")

        if almaany_path and Path(almaany_path).exists():
            with open(almaany_path) as f:
                self.almaany = json.load(f)
            print(f"    Almaany cache: {len(self.almaany)} entries")

    def get_hawramani(self, bare_form):
        """Get Hawramani definitions for a bare form. Returns list of dicts."""
        entry = self.hawramani.get(bare_form)
        if not entry or not entry.get("found"):
            return []
        return entry.get("definitions", [])

    def get_almaany(self, bare_form):
        """Get Almaany sections for a bare form. Returns list of section dicts."""
        entry = self.almaany.get(bare_form)
        if not entry or not entry.get("found"):
            return []
        return entry.get("sections", [])


# ─── Markdown rendering ───────────────────────────────────────────────────────


def _escape_md(text):
    """Escape pipe characters for markdown tables."""
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", " ")


def _truncate(text, maxlen=150):
    if not text:
        return ""
    if len(text) <= maxlen:
        return text
    return text[:maxlen] + "…"


def _parse_json_field(raw):
    """Parse a JSON string field from the DB, return list of strings."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return [str(v) if not isinstance(v, str) else v for v in val]
        return [str(val)]
    except (json.JSONDecodeError, TypeError):
        return [str(raw)]


def _format_definitions(raw):
    """Format a JSON array of definitions into a readable string."""
    defs = _parse_json_field(raw)
    if not defs:
        return "—"
    if len(defs) == 1:
        return _truncate(defs[0], 200)
    return " / ".join(_truncate(d, 100) for d in defs[:3])


def _format_examples_db(raw):
    """Format examples from DB (JSON array of {type, text, attribution} objects)."""
    if not raw or raw == "[]":
        return []
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(items, list):
        return []

    parts = []
    for item in items[:3]:
        if isinstance(item, dict):
            text = item.get("text", "")
            etype = item.get("type", "")
            attr = item.get("attribution", "")
            label = f"[{etype}]" if etype else ""
            attribution = f" — {attr}" if attr else ""
            parts.append(f"{label} {text}{attribution}".strip())
        elif isinstance(item, str):
            parts.append(item)
    return parts


def render_dict_entries(entries, match_type="exact"):
    """Render dictionary entries as a markdown table."""
    if not entries:
        return "*No dictionary entries found.*\n\n"

    lines = []
    if match_type == "al_prefix":
        lines.append("*تطابق مع إضافة «ال» التعريف — Match with definite article ال added*\n")
    elif match_type == "hamza_normalized":
        lines.append("*تطابق بعد توحيد الهمزة — Match after hamza normalization (أ/إ/آ↔ا, ئ↔ي, ؤ↔و)*\n")
    elif match_type == "taa_marbuta":
        lines.append("*تطابق بعد توحيد التاء المربوطة — Match after taa marbuta normalization (ة↔ه)*\n")
    elif match_type == "geminate":
        lines.append("*تطابق جذر مضعّف — Match after geminate root handling (e.g. مدد↔مد)*\n")
    elif match_type == "prep_stripped":
        lines.append("*تطابق بعد حذف حرف الجر — Match after stripping prepositional prefix (بال→ال)*\n")
    elif match_type.startswith("root"):
        lines.append(f"*إدخالات من نفس الجذر — Root-based lookup: {match_type}*\n")
    elif match_type == "definition_mention":
        lines.append("*⚠ ذُكر في تعريفات كلمات أخرى — Term mentioned in other words' definitions (low confidence)*\n")

    lines.extend([
        "| Source | Headword | POS | Form | Definitions | Plurals |",
        "|--------|----------|-----|------|-------------|---------|",
    ])
    for e in entries:
        defs = _escape_md(_format_definitions(e["definitions"]))
        plurals_raw = _parse_json_field(e.get("plurals", "[]"))
        plurals = "، ".join(plurals_raw[:5]) if plurals_raw else "—"
        form = e.get("form", "") or "—"
        lines.append(
            f"| {e['source']} | {e['headword']} | {e['pos']} | {form} | {defs} | {plurals} |"
        )

    # Show examples separately if any exist
    has_examples = any(e.get("examples") and e["examples"] != "[]" for e in entries)
    if has_examples:
        lines.append("")
        lines.append("**Examples from dictionaries:**")
        for e in entries:
            exs = _format_examples_db(e.get("examples", "[]"))
            if exs:
                for ex in exs[:2]:
                    lines.append(f"- [{e['source']}] {_truncate(str(ex), 200)}")

    lines.append("")
    return "\n".join(lines)


def render_arabterm_entries(entries):
    """Render ARABTERM entries as a markdown table."""
    if not entries:
        return "*No ARABTERM entries found.*\n\n"

    lines = [
        "| Domain | Arabic | English | French | Description |",
        "|--------|--------|---------|--------|-------------|",
    ]
    for e in entries[:10]:  # limit to 10 to avoid huge tables
        desc = _escape_md(_truncate(e.get("description", "") or "", 100))
        lines.append(
            f"| {e.get('domain', '')} | {e.get('arabic', '')} | {e.get('english', '')} "
            f"| {e.get('french', '') or '—'} | {desc or '—'} |"
        )
    if len(entries) > 10:
        lines.append(f"| … | *+{len(entries)-10} more entries* | | | |")
    lines.append("")
    return "\n".join(lines)


def render_hawramani_entries(definitions):
    """Render Hawramani dictionary entries as markdown."""
    if not definitions:
        return "*No Hawramani entries found.*\n\n"

    lines = []
    for d in definitions:
        dict_name = d.get("dict_name_ar") or d.get("dict_name_en") or f"Dictionary #{d.get('html_dict_id', '?')}"
        defn_text = d.get("definition_text", "")
        # Truncate long definitions
        if len(defn_text) > 500:
            defn_text = defn_text[:500] + "…"
        lines.append(f"**{dict_name}:**")
        lines.append(f"> {_escape_md(defn_text)}")
        lines.append("")

    return "\n".join(lines)


def render_almaany_entries(sections):
    """Render Almaany dictionary sections as markdown."""
    if not sections:
        return "*No Almaany entries found.*\n\n"

    lines = []
    for sec in sections:
        # Section header (e.g. "معجم المعاني الجامع" or "قاموس الكل")
        sec_name = sec.get("section_name", "")
        # Clean up the section name (remove repeated word)
        sec_name = re.sub(r"تعريف و معنى\s*\S+\s*في\s*", "", sec_name).strip()
        if sec_name:
            lines.append(f"**{sec_name}** ({sec['num_entries']} entries):\n")

        # Show entries as a compact table
        entries = sec.get("entries", [])
        if entries:
            lines.append("| Headword | POS | Source | Definition |")
            lines.append("|----------|-----|--------|------------|")
            for e in entries[:15]:  # cap at 15 per section
                hw = _escape_md(e.get("headword", ""))
                pos = _escape_md(e.get("pos", "—"))
                src = _escape_md(e.get("source_dict", "—")) or "—"
                defn = _escape_md(_truncate(e.get("definition_text", ""), 150))
                lines.append(f"| {hw} | {pos} | {src} | {defn} |")
            if len(entries) > 15:
                lines.append(f"| … | | | *+{len(entries)-15} more* |")
            lines.append("")

    return "\n".join(lines)


def generate_review(synset_id, synsets, oewn, db_path, caches=None, morph_analyzer=None):
    """Generate the full markdown review for a single synset."""
    synset = synsets.get(synset_id)
    if not synset:
        return f"# Error\n\nSynset `{synset_id}` not found in AWN4 XML.\n"

    md = []

    # ── Header ──
    md.append(f"# مراجعة المجموعة الدلالية — Synset Review\n")
    md.append(f"## `{synset_id}`\n")

    # ── 1. Synset Overview ──
    md.append("### 1. معلومات المجموعة الدلالية — Synset Overview\n")
    pos_label = POS_LABELS.get(synset["partOfSpeech"], synset["partOfSpeech"])
    md.append(f"- **ID:** `{synset_id}`")
    md.append(f"- **ILI:** `{synset['ili'] or '—'}`")
    md.append(f"- **POS:** {pos_label}")
    lemma_forms = [l["writtenForm"] for l in synset["lemmas"]]
    md.append(f"- **Lemmas ({len(lemma_forms)}):** {' ، '.join(lemma_forms)}")
    md.append("")

    # Arabic definition
    if synset["definitions"]:
        md.append("**التعريف (Arabic Definition):**")
        for d in synset["definitions"]:
            md.append(f"> {d}")
        md.append("")

    # Examples
    if synset["examples"]:
        md.append("**أمثلة (Examples):**")
        for ex in synset["examples"]:
            md.append(f"- {ex}")
        md.append("")

    # English equivalent
    oewn_entry = oewn.get_oewn_equivalent(synset["ili"])
    if oewn_entry:
        en_lemmas = ", ".join(oewn_entry.get("lemmas", []))
        md.append("**English Equivalent (OEWN via ILI):**")
        md.append(f"- **Lemmas:** {en_lemmas}")
        md.append(f"- **Definition:** {oewn_entry.get('definition', '—')}")
        md.append("")
    elif synset["ili"]:
        md.append("*No OEWN English equivalent found for this ILI.*\n")

    md.append("---\n")

    # ── 2. Lemmas ──
    md.append("### 2. الوحدات المعجمية — Lemmas in this Synset\n")
    for i, lemma in enumerate(synset["lemmas"], 1):
        wf = lemma["writtenForm"]
        sn = lemma.get("sense_number") or "—"
        md.append(f"#### {i}. «{wf}» (sense #{sn})\n")

        bare = strip_diacritics(wf)
        md.append(f"*Bare form:* `{bare}`\n")

        # Dictionary evidence
        md.append("##### Dictionary Evidence\n")
        dict_entries, match_type = query_dict_entries(db_path, bare, morph_analyzer)
        md.append(render_dict_entries(dict_entries, match_type))

        # ARABTERM
        md.append("##### ARABTERM Technical Terminology\n")
        at_entries = query_arabterm(db_path, bare)
        md.append(render_arabterm_entries(at_entries))

        # Hawramani
        if caches:
            hw_defs = caches.get_hawramani(bare)
            md.append("##### Hawramani Arabic Lexicon\n")
            md.append(render_hawramani_entries(hw_defs))

            # Almaany
            al_sections = caches.get_almaany(bare)
            md.append("##### Almaany (المعاني)\n")
            md.append(render_almaany_entries(al_sections))

        if i < len(synset["lemmas"]):
            md.append("---\n")

    md.append("---\n")

    # ── 3. Semantic Relations ──
    md.append("### 3. العلاقات الدلالية — Semantic Relations\n")
    if synset["relations"]:
        md.append("| Relation | Target Synset | Target Lemmas | Target Definition |")
        md.append("|----------|---------------|---------------|-------------------|")
        for rel in synset["relations"]:
            rel_label = RELATION_LABELS.get(rel["relType"], rel["relType"])
            target_id = rel["target"]
            target_syn = synsets.get(target_id)
            if target_syn:
                t_lemmas = "، ".join(l["writtenForm"] for l in target_syn["lemmas"][:4])
                t_def = _escape_md(_truncate(target_syn["definitions"][0], 100)) if target_syn["definitions"] else "—"
            else:
                t_lemmas = "—"
                t_def = "—"
            md.append(f"| {rel_label} | `{target_id}` | {t_lemmas} | {t_def} |")
        md.append("")
    else:
        md.append("*No semantic relations defined for this synset.*\n")

    md.append("---\n")

    # ── 4. Connected Synset Details ──
    md.append("### 4. تفاصيل المجموعات المتصلة — Connected Synset Details\n")
    if synset["relations"]:
        for rel in synset["relations"]:
            target_id = rel["target"]
            target_syn = synsets.get(target_id)
            if not target_syn:
                md.append(f"#### `{target_id}` — *not found in AWN4 XML*\n")
                continue

            rel_label = RELATION_LABELS.get(rel["relType"], rel["relType"])
            t_lemma_forms = [l["writtenForm"] for l in target_syn["lemmas"]]
            md.append(f"#### `{target_id}` — {' ، '.join(t_lemma_forms)}")
            md.append(f"*Relation:* {rel_label}\n")

            t_pos = POS_LABELS.get(target_syn["partOfSpeech"], target_syn["partOfSpeech"])
            md.append(f"- **POS:** {t_pos}")
            if target_syn["definitions"]:
                md.append(f"- **Definition:** {target_syn['definitions'][0]}")

            # English equivalent for connected synset
            t_oewn = oewn.get_oewn_equivalent(target_syn["ili"])
            if t_oewn:
                md.append(f"- **English:** {', '.join(t_oewn.get('lemmas', []))} — {t_oewn.get('definition', '')}")
            md.append("")

            # Dictionary evidence for connected synset's lemmas
            for tl in target_syn["lemmas"]:
                bare = strip_diacritics(tl["writtenForm"])
                d_entries, d_match = query_dict_entries(db_path, bare, morph_analyzer)
                if d_entries:
                    md.append(f"**Dictionary entries for «{tl['writtenForm']}»:**\n")
                    md.append(render_dict_entries(d_entries, d_match))

            md.append("---\n")
    else:
        md.append("*No connected synsets.*\n")

    # ── Footer ──
    md.append("\n---\n")
    md.append("*Generated by `generate_synset_review.py` — AWN4 Synset Linguistic Audit*\n")

    return "\n".join(md)


# ─── Pipeline ──────────────────────────────────────────────────────────────────


def run(args):
    t0 = time.time()

    # Collect synset IDs to process
    synset_ids = []
    if args.synset:
        synset_ids = args.synset
    elif args.sample:
        with open(args.sample) as f:
            data = json.load(f)
        synset_ids = [s["id"] for s in data["synsets"]]
        print(f"Loaded {len(synset_ids)} synsets from sample file")

    if not synset_ids:
        print("Error: no synset IDs provided. Use --synset or --sample.")
        import sys
        sys.exit(1)

    # Parse AWN4
    print("\n[1/4] Loading AWN4 XML...")
    synsets, _ = parse_awn4(args.awn4_xml)

    # Load OEWN ILI metadata
    print("\n[2/4] Loading OEWN metadata...")
    oewn = OEWNLookup(Path(args.meta_dir))

    # Load scraped caches
    print("\n[3/4] Loading scraped dictionary caches...")
    caches = ScrapedCaches(
        hawramani_path=args.hawramani_cache,
        almaany_path=args.almaany_cache,
    )

    # Load CAMeL Tools morphological analyzer
    morph_analyzer = None
    print("\n[4/4] Loading CAMeL Tools morphological analyzer...")
    try:
        from camel_tools.morphology.database import MorphologyDB
        from camel_tools.morphology.analyzer import Analyzer
        db = MorphologyDB.builtin_db()
        morph_analyzer = Analyzer(db)
        print("    CAMeL morphology ready (all Arabic Forms I-X, broken plurals, etc.)")
    except ImportError:
        print("    CAMeL Tools not installed — using regex fallback for root derivation")
    except Exception as e:
        print(f"    CAMeL Tools error: {e} — using regex fallback")

    # Generate reviews
    print(f"\nGenerating {len(synset_ids)} review documents...")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for sid in synset_ids:
        print(f"  {sid}...")
        md_content = generate_review(sid, synsets, oewn, args.db, caches, morph_analyzer)
        safe_name = sid.replace("/", "_")
        out_path = output_dir / f"{safe_name}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)

    elapsed = time.time() - t0
    print(f"\nDone! {len(synset_ids)} review documents in {elapsed:.1f}s")
    print(f"Output: {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Generate AWN4 synset review .md files")
    parser.add_argument("--synset", nargs="+", help="One or more synset IDs (e.g. awn4-04875102-n)")
    parser.add_argument("--sample", help="Path to random_synset_sample.json")
    parser.add_argument("-o", "--output", default="output/reviews", help="Output directory (default: output/reviews)")
    parser.add_argument("--awn4-xml", default=str(AWN4_XML), help="Path to awn4.xml")
    parser.add_argument("--db", default=str(DICT_DB), help="Path to arabic_dict.db")
    parser.add_argument("--meta-dir", default=str(COLBERT_META_DIR), help="Path to ColBERT metadata dir (for ILI lookups)")
    parser.add_argument("--hawramani-cache", default=str(HAWRAMANI_CACHE), help="Path to hawramani_cache.json")
    parser.add_argument("--almaany-cache", default=str(ALMAANY_CACHE), help="Path to almaany_cache.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
