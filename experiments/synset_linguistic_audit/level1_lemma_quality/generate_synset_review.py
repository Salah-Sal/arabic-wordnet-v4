#!/usr/bin/env python3
"""Generate .md review documents for AWN4 synsets.

For each synset, aggregates information from:
  - AWN4 XML (definition, examples, relations, lemmas)
  - OEWN English equivalents (via ILI cross-lingual index from ColBERT metadata)
  - Arabic dictionaries DB (classical/modern dictionary entries per lemma)
  - ARABTERM (multilingual technical terminology per lemma)
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

# ─── Arabic normalization ─────────────────────────────────────────────────────

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
HAMZA_NORM = str.maketrans({
    "\u0623": "\u0627",  # أ → ا
    "\u0625": "\u0627",  # إ → ا
    "\u0622": "\u0627",  # آ → ا
    "\u0624": "\u0648",  # ؤ → و
    "\u0626": "\u064A",  # ئ → ي
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


def query_dict_entries(db_path, bare_form):
    """Query arabic_dict.db for entries matching a bare (undiacritized) form.

    Returns (entries, match_type) where match_type is:
      "exact" — headword_bare exact match
      "normalized" — hamza-normalized match
      "definition_mention" — term appears in definitions text (FTS)
    """
    cols = "source, headword, pos, form, definitions, plurals, examples"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Strategy 1: exact match
    rows = conn.execute(
        f"SELECT {cols} FROM entries WHERE headword_bare = ?",
        (bare_form,),
    ).fetchall()
    if rows:
        conn.close()
        return [dict(r) for r in rows], "exact"

    # Strategy 2: hamza normalization + trailing hamza removal
    if len(bare_form) >= 2:
        normalized = bare_form.translate(HAMZA_NORM)
        variants = {normalized, bare_form.rstrip("\u0621"), normalized.rstrip("\u0621")}
        variants.discard(bare_form)
        for variant in variants:
            if variant:
                rows = conn.execute(
                    f"SELECT {cols} FROM entries WHERE headword_bare = ?",
                    (variant,),
                ).fetchall()
                if rows:
                    conn.close()
                    return [dict(r) for r in rows], "normalized"

    # Strategy 3: FTS on definitions (entries that mention this term)
    if len(bare_form) >= 3:
        rows = conn.execute(
            f"SELECT e.source, e.headword, e.pos, e.form, e.definitions, e.plurals, e.examples "
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
    if match_type == "normalized":
        lines.append("*Match type: hamza-normalized (أ/إ/آ→ا, ء removed)*\n")
    elif match_type == "definition_mention":
        lines.append("*Match type: term mentioned in definitions (not a headword match)*\n")

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


def generate_review(synset_id, synsets, oewn, db_path):
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
        dict_entries, match_type = query_dict_entries(db_path, bare)
        md.append(render_dict_entries(dict_entries, match_type))

        # ARABTERM
        md.append("##### ARABTERM Technical Terminology\n")
        at_entries = query_arabterm(db_path, bare)
        md.append(render_arabterm_entries(at_entries))

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
                d_entries, d_match = query_dict_entries(db_path, bare)
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
    print("\n[1/2] Loading AWN4 XML...")
    synsets, _ = parse_awn4(args.awn4_xml)

    # Load OEWN ILI metadata
    print("\n[2/2] Loading OEWN metadata...")
    oewn = OEWNLookup(Path(args.meta_dir))

    # Generate reviews
    print(f"\nGenerating {len(synset_ids)} review documents...")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for sid in synset_ids:
        print(f"  {sid}...")
        md_content = generate_review(sid, synsets, oewn, args.db)
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
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
