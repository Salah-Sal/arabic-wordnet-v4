#!/usr/bin/env python3
"""Generate linguist review documents for AWN4 synsets.

For each synset produces:
  - {synset_id}.md  — Read-only reference with all evidence
  - {synset_id}.yaml — Structured decision sidecar for the linguist

AWN4 was machine-translated from English OEWN by Google Gemini.
This tool pulls dictionary evidence so linguists can validate the translations.

Usage:
  python generate_review_doc.py --synset-ids awn4-13271441-n
  python generate_review_doc.py --synset-ids awn4-13271441-n --no-colbert
  python generate_review_doc.py --count 5 --seed 42
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ── Path setup ───────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
AWN4_BASE = SCRIPT_DIR.parent.parent              # arabic-wordnet-v4/
COLBERT_DIR = AWN4_BASE / "experiments" / "colbertv2 exp"
AWN4_XML = AWN4_BASE / "output" / "awn4.xml"
DICT_DB = AWN4_BASE.parent / "arabic-dictionaries" / "db" / "arabic_dict.db"

# Import retrieval machinery (triggers RAG sys.path setup)
import retrieve_dict_evidence as rde                        # noqa: E402
from retrieve_dict_evidence import (                        # noqa: E402
    SynsetInfo, parse_awn4, select_diverse_synsets,
    strategy_a, strategy_b, strategy_c, strategy_d, strategy_e,
    classify_evidence, _get_english_lemmas,
)

# RAG imports (available after retrieve_dict_evidence's sys.path setup)
from rag.db import get_connection, build_authority_map       # noqa: E402
from rag.similarity import definition_similarity, definition_containment, ARABIC_STOPWORDS  # noqa: E402
from common import normalize_arabic, strip_diacritics        # noqa: E402

# ── Monkey-patch _row_to_dict for longer definitions + extra fields ──────────

_orig_row_to_dict = rde._row_to_dict

def _row_to_dict_review(row):
    d = _orig_row_to_dict(row)
    d["definitions_text"] = row["definitions_text"] or ""
    d["dict_name_ar"] = row["dict_name_ar"] or ""
    d["root_source"] = row["root_source"] or ""
    return d

rde._row_to_dict = _row_to_dict_review

# ── Constants ────────────────────────────────────────────────────────────────

_NON_ARABIC_RE = re.compile(r'[a-zA-Z0-9]')

POS_LABELS = {
    "n": "اسم — noun",
    "v": "فعل — verb",
    "a": "صفة — adjective",
    "r": "ظرف — adverb",
}

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


# ── AWN4 relation parsing (second pass) ──────────────────────────────────────

def parse_awn4_relations(xml_path: Path) -> dict[str, list[dict]]:
    """Parse SynsetRelation elements from AWN4 XML.

    Returns {synset_id: [{"relType": str, "target": str}, ...]}.
    """
    print("  Parsing AWN4 relations...")
    t0 = time.time()
    relations: dict[str, list[dict]] = defaultdict(list)
    current_synset_id = None

    for event, elem in ET.iterparse(str(xml_path), events=("start", "end")):
        if event == "start" and elem.tag == "Synset":
            current_synset_id = elem.get("id")
        elif event == "end":
            if elem.tag == "SynsetRelation" and current_synset_id:
                relations[current_synset_id].append({
                    "relType": elem.get("relType"),
                    "target": elem.get("target"),
                })
            elif elem.tag == "Synset":
                current_synset_id = None
            elem.clear()

    print(f"  {sum(len(v) for v in relations.values()):,} relations in {time.time()-t0:.1f}s")
    return dict(relations)


# ── OEWN English data lookup ────────────────────────────────────────────────

def get_oewn_data(ili: str) -> dict | None:
    """Get English OEWN data for an ILI: definition, lemmas, examples."""
    if not ili:
        return None
    try:
        import wn
        oewn_synsets = wn.synsets(ili=ili, lang="en")
        if not oewn_synsets:
            return None
        s = oewn_synsets[0]
        return {
            "definition": s.definition() or "",
            "lemmas": [w.lemma() for w in s.words()],
            "examples": s.examples() or [],
            "pos": s.pos,
        }
    except Exception:
        return None


# ── Per-lemma evidence merging ───────────────────────────────────────────────

@dataclass
class LemmaEvidence:
    lemma: str
    bare: str
    norm: str
    headword_entries: list[dict] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    root_sources: list[str] = field(default_factory=list)
    root_family: list[dict] = field(default_factory=list)
    synonym_candidates: list[dict] = field(default_factory=list)
    arabterm_entries: list[dict] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)  # [{type, text, attribution}]
    is_loanword: bool = False
    is_multiword: bool = False


def _entry_sort_key(entry: dict, lemma_bare: str = "") -> tuple:
    """Sort entries: exact headword match first, then by dictionary authority.

    Entries whose headword_bare exactly matches the lemma (stripped of diacritics)
    sort before entries that only match after hamza normalization. This prevents
    e.g. مأل (fatness) entries from appearing before مال (money) entries.
    """
    # Priority 0: exact headword match quality
    hw_bare = (entry.get("headword_bare") or "").strip()
    is_exact = 0 if (lemma_bare and hw_bare == lemma_bare) else 1

    # Priority 1-5: dictionary authority
    src = entry.get("source_type", "")
    period = entry.get("period", "")
    if period == "classical":
        authority = (1, entry.get("dict_name_en", ""))
    elif src == "ocr" and period == "modern":
        authority = (2, entry.get("dict_name_en", ""))
    elif src == "hawramani" and period == "modern":
        authority = (3, entry.get("dict_name_en", ""))
    elif src == "arabterm":
        authority = (4, entry.get("dict_name_en", ""))
    else:
        authority = (5, entry.get("dict_name_en", ""))

    return (is_exact,) + authority


def fetch_examples_for_entries(conn, entry_ids: set[int],
                               max_per_entry: int = 5) -> dict[int, list[dict]]:
    """Fetch dictionary examples (poetry, quran, hadith, etc.) for entry_ids.

    Returns {entry_id: [{type, text, attribution}, ...]}.
    Queries the ``examples`` child table in chunks to respect SQLite limits.
    """
    if not entry_ids:
        return {}

    results: dict[int, list[dict]] = {}
    id_list = list(entry_ids)

    for i in range(0, len(id_list), 500):
        chunk = id_list[i:i + 500]
        placeholders = ",".join("?" * len(chunk))
        sql = f"""
            SELECT entry_id, type, text, attribution
            FROM examples
            WHERE entry_id IN ({placeholders})
            ORDER BY entry_id, idx
        """
        rows = conn.execute(sql, chunk).fetchall()
        for row in rows:
            eid = row[0] if isinstance(row, (tuple, list)) else row["entry_id"]
            if eid not in results:
                results[eid] = []
            if len(results[eid]) < max_per_entry:
                if isinstance(row, (tuple, list)):
                    results[eid].append({
                        "type": row[1] or "",
                        "text": row[2] or "",
                        "attribution": row[3] or "",
                    })
                else:
                    results[eid].append({
                        "type": row["type"] or "",
                        "text": row["text"] or "",
                        "attribution": row["attribution"] or "",
                    })

    return results


def merge_evidence_by_lemma(synset: SynsetInfo,
                            strategies: dict[str, dict]) -> dict[str, LemmaEvidence]:
    """Reorganize flat strategy results into per-lemma evidence groups."""

    # Build lemma → normalized form mapping
    lemma_norms: dict[str, str] = {}
    for lemma in synset.lemmas:
        lemma_norms[lemma] = normalize_arabic(strip_diacritics(lemma))

    # Initialize per-lemma evidence
    evidence: dict[str, LemmaEvidence] = {}
    for lemma in synset.lemmas:
        bare = strip_diacritics(lemma)
        evidence[lemma] = LemmaEvidence(
            lemma=lemma,
            bare=bare,
            norm=lemma_norms[lemma],
            is_loanword=bool(_NON_ARABIC_RE.search(lemma)),
            is_multiword=" " in lemma,
        )

    def _match_lemma(entry_hw: str) -> str | None:
        """Match an entry headword to a synset lemma."""
        hw_norm = normalize_arabic(entry_hw)
        for lemma, norm in lemma_norms.items():
            if hw_norm == norm:
                return lemma
        # Try individual words for multi-word lemmas
        for lemma in synset.lemmas:
            if " " in lemma:
                for word in lemma.split():
                    if len(word) > 2 and normalize_arabic(strip_diacritics(word)) == hw_norm:
                        return lemma
        return None

    # ── Strategy A: assign headword matches to lemmas ──
    seen_a = set()
    for entry in strategies.get("A", {}).get("entries", []):
        eid = entry.get("entry_id")
        if eid in seen_a:
            continue
        seen_a.add(eid)

        # Prefix-stripped entries: route back to their original lemma
        if entry.get("_prefix_stripped"):
            orig = entry.get("_original_lemma")
            target = orig if orig and orig in evidence else synset.lemmas[0]
            evidence[target].headword_entries.append(entry)
            # Extract root from the stripped form's DB entry (e.g., ذكاء → root ذكو)
            root = entry.get("root")
            if root and root not in evidence[target].roots:
                evidence[target].roots.append(root)
                evidence[target].root_sources.append(entry.get("root_source", ""))
            continue

        hw = entry.get("headword_bare") or entry.get("headword", "")
        matched = _match_lemma(hw)
        if matched:
            evidence[matched].headword_entries.append(entry)
            root = entry.get("root")
            if root and root not in evidence[matched].roots:
                evidence[matched].roots.append(root)
                rs = entry.get("root_source", "")
                evidence[matched].root_sources.append(rs)
        else:
            # Assign to first lemma as fallback
            evidence[synset.lemmas[0]].headword_entries.append(entry)

    # ── Strategy B: assign root family entries by shared root ──
    root_to_lemma: dict[str, str] = {}
    for lemma, ev in evidence.items():
        for root in ev.roots:
            root_to_lemma.setdefault(root, lemma)

    seen_b = set()
    for entry in strategies.get("B", {}).get("entries", []):
        eid = entry.get("entry_id")
        if eid in seen_b:
            continue
        seen_b.add(eid)
        entry_root = entry.get("root")
        if entry_root and entry_root in root_to_lemma:
            target = root_to_lemma[entry_root]
            evidence[target].root_family.append(entry)
        elif synset.lemmas:
            evidence[synset.lemmas[0]].root_family.append(entry)

    # ── Strategy C/D: classify and collect synonym candidates ──
    all_synonym_candidates: list[dict] = []
    for key in ["C", "D"]:
        for entry in strategies.get(key, {}).get("entries", []):
            types = classify_evidence(entry, synset)
            if "synonym_candidate" in types:
                entry_def = entry.get("definitions_text", "")
                sim = definition_similarity(entry_def, synset.definition) if entry_def else 0
                entry["_similarity"] = round(sim, 2)
                all_synonym_candidates.append(entry)

    # Deduplicate synonym candidates by entry_id, keep best similarity
    syn_cand_by_id: dict[int, dict] = {}
    for e in all_synonym_candidates:
        eid = e.get("entry_id", -1)
        if eid not in syn_cand_by_id or e.get("_similarity", 0) > syn_cand_by_id[eid].get("_similarity", 0):
            syn_cand_by_id[eid] = e
    # Sort by similarity descending
    deduped = sorted(syn_cand_by_id.values(), key=lambda x: x.get("_similarity", 0), reverse=True)
    # Assign to first lemma (synonym candidates are synset-level)
    if synset.lemmas:
        evidence[synset.lemmas[0]].synonym_candidates = deduped

    # ── Strategy E: assign ARABTERM entries by headword match ──
    for entry in strategies.get("E", {}).get("entries", []):
        hw = entry.get("headword_bare") or entry.get("headword", "")
        matched = _match_lemma(hw)
        target = matched or synset.lemmas[0] if synset.lemmas else None
        if target:
            evidence[target].arabterm_entries.append(entry)

    # Sort headword entries: exact match first, then by dictionary authority
    for ev in evidence.values():
        ev.headword_entries.sort(key=lambda e: _entry_sort_key(e, ev.bare))
        ev.root_family.sort(key=lambda e: _entry_sort_key(e, ev.bare))

    return evidence


# ── ColBERT-only entries ─────────────────────────────────────────────────────

def identify_colbert_only(strategies: dict[str, dict]) -> list[dict]:
    """Find entries retrieved ONLY by ColBERT (strategy D), not by A/B/C/E."""
    d_entries = strategies.get("D", {}).get("entries", [])
    if not d_entries:
        return []

    other_ids = set()
    for key in ["A", "B", "C", "E"]:
        other_ids |= strategies.get(key, {}).get("entry_ids", set())

    colbert_only = []
    for entry in d_entries:
        eid = entry.get("entry_id", -1)
        if eid > 0 and eid not in other_ids:
            colbert_only.append(entry)

    return colbert_only


# ── Markdown rendering ──────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape pipe and newlines for markdown tables."""
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", " ")


def _trunc_word(text: str, limit: int = 500) -> str:
    """Truncate at word boundary with ellipsis if over limit."""
    if not text or len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    if cut == -1:
        cut = limit
    return text[:cut] + " …"


def _dict_display(entry: dict, authority_map: dict) -> str:
    """Human-readable dictionary name (Arabic if available, else English)."""
    dk = entry.get("dict_key", "")
    ar = entry.get("dict_name_ar", "")
    en = entry.get("dict_name_en", "")
    # Try authority map for entries missing Arabic name (e.g. ColBERT)
    if not ar and dk and dk in authority_map:
        ar = authority_map[dk].get("name_ar", "")
        en = en or authority_map[dk].get("name_en", "")
    if ar and en:
        return f"{ar} ({en})"
    return ar or en or dk


def cluster_definitions(entries: list[dict], threshold: float = 0.65) -> list[list[dict]]:
    """Cluster dictionary entries with near-duplicate definitions.

    Uses definition_containment() for asymmetric "A copied B" detection.
    Returns list of clusters; first entry in each is the primary (longest definition).
    """
    if len(entries) <= 1:
        return [entries] if entries else []

    n = len(entries)
    assigned = [False] * n
    clusters: list[list[dict]] = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [entries[i]]
        assigned[i] = True
        def_i = entries[i].get("definitions_text", "")

        for j in range(i + 1, n):
            if assigned[j]:
                continue
            def_j = entries[j].get("definitions_text", "")
            if def_i and def_j:
                sim = definition_containment(def_i, def_j)
                if sim >= threshold:
                    cluster.append(entries[j])
                    assigned[j] = True

        # Longest definition first (most complete version)
        cluster.sort(key=lambda e: len(e.get("definitions_text", "")), reverse=True)
        clusters.append(cluster)

    return clusters


def render_md(synset: SynsetInfo,
              oewn_data: dict | None,
              lemma_evidence: dict[str, LemmaEvidence],
              colbert_only: list[dict],
              relations: list[dict],
              all_synsets: dict[str, SynsetInfo],
              authority_map: dict,
              colbert_enabled: bool,
              is_instance: bool = False) -> str:
    """Render the complete linguist review .md document."""
    md: list[str] = []

    # ── Header ──
    md.append("# مراجعة المجموعة الدلالية — Synset Review\n")
    md.append(f"> **ملاحظة:** تمت ترجمة هذه المجموعة الدلالية آلياً من شبكة الكلمات الإنجليزية المفتوحة (OEWN) بواسطة Google Gemini.")
    md.append(f"> هذا المستند مرجعي فقط. سجّل قراراتك في الملف المصاحب: **`{synset.id}.yaml`**\n")
    md.append("---\n")

    # ── Section 1: Synset Overview ──
    md.append("## 1. معلومات المجموعة الدلالية — Synset Overview\n")

    pos_label = POS_LABELS.get(synset.pos, synset.pos)
    md.append("| الحقل — Field | القيمة — Value |")
    md.append("|------|-------|")
    md.append(f"| **المعرّف — ID** | `{synset.id}` |")
    md.append(f"| **ILI** | `{synset.ili or '—'}` |")
    md.append(f"| **صنف الكلمة — POS** | {pos_label} |")
    md.append(f"| **الوحدات المعجمية — Lemmas ({len(synset.lemmas)})** | {' ، '.join(synset.lemmas)} |")
    md.append("")

    # Side-by-side English/Arabic comparison
    if oewn_data:
        md.append("### المقارنة — Source vs. Translation\n")
        md.append("| الحقل — Field | الإنجليزية (OEWN) | العربية (AWN4) |")
        md.append("|---|---|---|")
        md.append(f"| **التعريف — Def** | {_esc(oewn_data['definition'])} | {_esc(synset.definition)} |")
        en_lemmas = ", ".join(oewn_data["lemmas"])
        ar_lemmas = " ، ".join(synset.lemmas)
        md.append(f"| **الوحدات — Lemmas** | {_esc(en_lemmas)} | {_esc(ar_lemmas)} |")
        en_ex = " \\| ".join(oewn_data["examples"][:3]) if oewn_data["examples"] else "—"
        ar_ex = " \\| ".join(synset.examples[:3]) if synset.examples else "—"
        md.append(f"| **أمثلة — Examples** | {_esc(en_ex)} | {_esc(ar_ex)} |")
        md.append("")
    elif not synset.ili:
        md.append("> ⚠ **لا يوجد رابط ILI** — هذه المجموعة ليس لها ربط بشبكة الكلمات الإنجليزية. المعلومات الإنجليزية غير متوفرة.\n")
        md.append("### الترجمة العربية — Arabic Translation (AWN4)\n")
        md.append(f"- **التعريف — Definition:** {synset.definition}")
        md.append(f"- **الوحدات — Lemmas:** {' ، '.join(synset.lemmas)}")
        if synset.examples:
            md.append(f"- **أمثلة — Examples:** {' | '.join(synset.examples[:3])}")
        md.append("")
    else:
        md.append("### الترجمة العربية — Arabic Translation (AWN4)\n")
        md.append(f"- **التعريف — Definition:** {synset.definition}")
        md.append(f"- **الوحدات — Lemmas:** {' ، '.join(synset.lemmas)}")
        if synset.examples:
            md.append(f"- **أمثلة — Examples:** {' | '.join(synset.examples[:3])}")
        md.append("")

    if is_instance:
        md.append("> **كيان مُسمّى — Named Entity (instance synset).** نتائج البحث الدلالي قد تعكس تشابهاً صوتياً/صرفياً وليس دلالياً.\n")

    md.append("---\n")

    # ── Section 2: Per-Lemma Dictionary Evidence ──
    md.append("## 2. شواهد معجمية لكل وحدة — Per-Lemma Dictionary Evidence\n")

    for idx, lemma in enumerate(synset.lemmas, 1):
        ev = lemma_evidence.get(lemma)
        if not ev:
            continue

        md.append(f"### 2.{idx} «{lemma}»\n")

        # Attestation summary
        hw_dicts = {e.get("dict_key") for e in ev.headword_entries}
        hw_dicts.discard(None)
        n_entries = len(ev.headword_entries)
        n_dicts = len(hw_dicts)

        if n_entries > 0:
            md.append(f"**حالة التوثيق — Attestation:** {n_entries} entries across {n_dicts} dictionaries")
        else:
            md.append("**حالة التوثيق — Attestation:** ⚠ لم يُعثر على إدخالات — No dictionary entries found")

        # Root info
        if ev.roots:
            root_str = "، ".join(ev.roots)
            src_str = "، ".join(s for s in ev.root_sources if s) or "unknown"
            md.append(f"**الجذر — Root:** {root_str} (source: {src_str})")
        elif ev.is_loanword:
            md.append("**الجذر — Root:** لفظ مقترض — Loanword (no Arabic root expected)")
        else:
            md.append("**الجذر — Root:** لم يُعثر على جذر — No root found")

        # Multi-word note
        if ev.is_multiword:
            words = ", ".join(w for w in lemma.split()
                              if len(w.strip()) > 2 and w.strip() not in ARABIC_STOPWORDS)
            md.append(f"\n> **تعبير متعدد الكلمات — Multi-word expression.** البحث شمل الكلمات المفردة: {words}")

        md.append("")

        # Core dictionary definitions — split into entries with/without definitions
        with_def = [e for e in ev.headword_entries
                    if not e.get("_prefix_stripped") and (e.get("definitions_text") or "").strip()]
        without_def = [e for e in ev.headword_entries
                       if not e.get("_prefix_stripped") and not (e.get("definitions_text") or "").strip()]
        prefix_stripped = [e for e in ev.headword_entries if e.get("_prefix_stripped")]

        if with_def:
            md.append("#### القواميس الأساسية — Core Dictionary Definitions\n")
            clusters = cluster_definitions(with_def)
            for c_idx, cluster in enumerate(clusters, 1):
                primary = cluster[0]
                dname = _esc(_dict_display(primary, authority_map))
                period = primary.get("period", "—") or "—"
                defn = _esc(_trunc_word(primary.get("definitions_text", "")))
                md.append(f"**{c_idx}.** {dname} ({period})")
                md.append(f"> {defn}\n")
                if len(cluster) > 1:
                    also_names = [_dict_display(e, authority_map) for e in cluster[1:]]
                    also_str = " ، ".join(dict.fromkeys(also_names))
                    md.append(f"> *نفس المعنى في — Same definition in:* {also_str}\n")
            md.append("")

        if without_def:
            names = " ، ".join(dict.fromkeys(
                _dict_display(e, authority_map) for e in without_def
            ))
            md.append(f"> أيضاً موثّق (بدون تعريف) في — Also attested (no definitions) in: {names}\n")

        # Prefix-stripped fallback results
        if prefix_stripped:
            ps = prefix_stripped[0]
            stripped_form = ps.get("_stripped_form", "")
            prefix_char = ps.get("_stripped_prefix", "")
            md.append(f"#### مطابقة بعد حذف البادئة — Prefix-stripped matches\n")
            md.append(f"> البحث عن «{stripped_form}» بعد حذف البادئة «{prefix_char}» — Searched for \"{stripped_form}\" after stripping prefix \"{prefix_char}\"\n")
            md.append("| # | القاموس — Dictionary | الحقبة — Period | التعريف — Definition |")
            md.append("|---|-----------|--------|---------------------|")
            for j, e in enumerate(prefix_stripped, 1):
                dname = _esc(_dict_display(e, authority_map))
                period = e.get("period", "—") or "—"
                defn = _esc(_trunc_word(e.get("definitions_text", "")))
                md.append(f"| {j} | {dname} | {period} | {defn} |")
            md.append("")

        # Dictionary usage examples (from the examples child table)
        if ev.examples:
            md.append("#### شواهد وأمثلة — Usage Examples\n")
            by_type: dict[str, list[dict]] = defaultdict(list)
            for ex in ev.examples:
                by_type[ex.get("type") or "usage"].append(ex)

            type_labels = {
                "quran": "قرآن — Quran",
                "hadith": "حديث — Hadith",
                "poetry": "شعر — Poetry",
                "proverb": "مثل — Proverb",
                "usage": "استعمال — Usage",
            }
            for ex_type in ["quran", "hadith", "poetry", "proverb", "usage"]:
                examples_of_type = by_type.get(ex_type, [])
                if examples_of_type:
                    label = type_labels.get(ex_type, ex_type)
                    md.append(f"**{label}:**\n")
                    for ex in examples_of_type[:3]:
                        attr = f" — *{_esc(ex['attribution'])}*" if ex.get("attribution") else ""
                        md.append(f"> {_esc(ex['text'])}{attr}\n")
            md.append("")

        # Root family (skip ARABTERM noise and empty definitions)
        interesting_rf = [e for e in ev.root_family
                          if e.get("source_type") != "arabterm"
                          and e.get("definitions_text", "").strip()]
        if interesting_rf:
            md.append("#### أقارب الجذر — Root Family\n")
            md.append("| الكلمة — Headword | القاموس — Dictionary | التعريف — Definition |")
            md.append("|----------|-----------|---------------------|")
            for e in interesting_rf:
                hw = _esc(e.get("headword", ""))
                dname = _esc(_dict_display(e, authority_map))
                defn = _esc(_trunc_word(e.get("definitions_text", "")))
                md.append(f"| {hw} | {dname} | {defn} |")
            md.append("")

        # Synonym candidates
        if ev.synonym_candidates:
            md.append("#### مرشحات مرادف — Synonym Candidates\n")
            md.append("*إدخالات بكلمات مختلفة لكن تعريفات متشابهة — Entries with different headwords but similar definitions*\n")
            md.append("| الكلمة — Headword | القاموس — Dictionary | التشابه — Sim. | التعريف — Definition |")
            md.append("|----------|-----------|-----------|------------|")
            for e in ev.synonym_candidates:
                hw = _esc(e.get("headword_bare") or e.get("headword", ""))
                dname = _esc(_dict_display(e, authority_map))
                sim = e.get("_similarity", "—")
                defn = _esc(_trunc_word(e.get("definitions_text", "")))
                md.append(f"| {hw} | {dname} | {sim} | {defn} |")
            md.append("")

        # ARABTERM translations
        if ev.arabterm_entries:
            md.append("#### مسرد أرابتيرم — ARABTERM Translations\n")
            md.append("| المجال — Domain | العربية | English | Français |")
            md.append("|--------|--------|---------|--------|")
            for e in ev.arabterm_entries:
                domain = _esc(e.get("domain", "") or "—")
                hw = _esc(e.get("headword", ""))
                en = _esc(e.get("translation_en", "") or "—")
                fr = _esc(e.get("translation_fr", "") or "—")
                md.append(f"| {domain} | {hw} | {en} | {fr} |")
            md.append("")

        # Separator between lemmas
        if idx < len(synset.lemmas):
            md.append("---\n")

    md.append("---\n")

    # ── Section 3: Semantic Evidence (ColBERT-only) ──
    md.append("## 3. شواهد دلالية (ColBERT فقط) — Semantic Evidence (ColBERT-only)\n")
    md.append("*إدخالات وجدها البحث الدلالي فقط، قد تكشف عن بدائل عربية أفضل.*\n")

    if is_instance and colbert_enabled:
        md.append("*⚠ كيان مُسمّى — Named Entity: ColBERT results below may reflect phonetic similarity rather than semantic relevance.*\n")

    if not colbert_enabled:
        md.append("*تم تخطي البحث الدلالي (--no-colbert). أعد التشغيل بدون هذا الخيار لعرض النتائج.*\n")
    elif colbert_only:
        md.append("| # | الكلمة — Headword | القاموس — Dictionary | النتيجة — Score | التعريف — Definition |")
        md.append("|---|----------|-----------|-----------|------------|")
        for j, e in enumerate(colbert_only, 1):
            hw = _esc(e.get("headword", ""))
            dname = _esc(_dict_display(e, authority_map))
            score = e.get("colbert_score", "—")
            defn = _esc(_trunc_word(e.get("definitions_text", "")))
            md.append(f"| {j} | {hw} | {dname} | {score} | {defn} |")
        md.append("")
    else:
        md.append("*لا توجد إدخالات إضافية من البحث الدلالي — No additional semantic evidence beyond keyword strategies.*\n")

    md.append("---\n")

    # ── Section 4: Connected Synsets ──
    md.append("## 4. المجموعات المتصلة — Connected Synsets\n")

    if not relations:
        md.append("*لا توجد علاقات دلالية — No semantic relations defined.*\n")
    else:
        for rel in relations:
            rel_label = RELATION_LABELS.get(rel["relType"], rel["relType"])
            target_id = rel["target"]
            target = all_synsets.get(target_id)

            md.append(f"### {rel_label}: `{target_id}`\n")

            if not target:
                md.append("*المجموعة غير موجودة في AWN4 — Synset not found in AWN4 XML.*\n")
                continue

            # Get English equivalent for connected synset
            t_oewn = get_oewn_data(target.ili) if target.ili else None

            md.append("| | العربية (AWN4) | الإنجليزية (OEWN) |")
            md.append("|---|--------------|----------------|")

            ar_lemmas = " ، ".join(target.lemmas[:5])
            en_lemmas = ", ".join(t_oewn["lemmas"][:5]) if t_oewn else "—"
            md.append(f"| **الوحدات** | {ar_lemmas} | {en_lemmas} |")

            ar_def = _esc(target.definition)
            en_def = _esc(t_oewn["definition"]) if t_oewn else "—"
            md.append(f"| **التعريف** | {ar_def} | {en_def} |")
            md.append("")

    md.append("---\n")

    # ── Footer ──
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    md.append(f"*Generated by `generate_review_doc.py` — AWN4 Linguist Review — {ts}*\n")

    return "\n".join(md)


# ── YAML sidecar ─────────────────────────────────────────────────────────────

def render_yaml(synset: SynsetInfo,
                lemma_evidence: dict[str, LemmaEvidence],
                authority_map: dict,
                relations_map: dict[str, list[dict]] | None = None,
                all_synsets: dict[str, "SynsetInfo"] | None = None) -> str:
    """Generate the enriched YAML sidecar with full review methodology.

    Structure follows the plan in REVIEW_GUIDE.md:
    - Analysis (chain of thought)
    - Actions (structured reviewer decisions — see §12 of REVIEW_GUIDE.md)
    - Scoring rubric (ordinal scales for IAA analysis)
    - Definition review (3 sub-dimensions + verdict)
    - Authored definitions (Step 2.5 — multiple definitions per synset)
    - Per-lemma enrichment (10+ fields + morpho checks + error type)
    - Missing lemmas, examples, relations, cultural fit, overall
    """

    doc = {
        "synset_id": synset.id,
        "reviewer": "",
        "review_date": "",
        "status": "pending",  # pending | in_progress | completed
    }

    # ── Analysis (Chain of Thought — fill before structured fields) ──
    doc["analysis"] = {
        "initial_impression": "",        # First reaction: does this synset "feel right"?
        "key_evidence": "",              # Which dictionary evidence was most decisive?
        "concerns": "",                  # Any doubts or issues noticed
        "comparison_with_english": "",   # How does the Arabic concept map to the English source?
        "reasoning": "",                 # Free-form reasoning leading to decisions below
    }

    # ── Actions (structured reviewer decisions — see §12 of REVIEW_GUIDE.md) ──
    doc["actions"] = []
    # Each entry: {action: "<code>", target: "<lemma or field>",
    #              reasoning: "<linguistic/logical chain of thought>",
    #              requirements: "<what's needed to complete>"}

    # ── Scoring rubric (ordinal scales for IAA analysis) ──
    doc["scores"] = {
        "semantic_accuracy": None,   # 0=wrong | 1=partial | 2=mostly correct | 3=fully correct
        "gloss_quality": None,       # 0=missing | 1=poor | 2=adequate | 3=excellent
        "synonym_coherence": None,   # 0=not synonymous | 1=partial | 2=fully synonymous
        "completeness": None,        # 0=critically incomplete | 1=partial | 2=complete
        "cultural_adequacy": "",     # direct | near_synonym | phraset | lexical_gap | omission
    }

    # ── Definition review ──
    doc["definition"] = {
        "accuracy": "",       # faithful | narrowed | broadened | mistranslated
        "fluency": "",        # natural | calque | awkward | ungrammatical
        "structure": "",      # genus_differentia | acceptable | circular | vague
        "verdict": "",        # accept | revise | reject
        "revised_text": "",
        "notes": "",
        "flags": [],          # e.g., [CALQUE_WARNING, WEAK_STYLE]
    }

    # ── Authored definitions (Step 2.5 — multiple definitions per synset) ──
    # Auto-populate genus_source from hypernym relation
    hypernym_id = ""
    if relations_map and synset.id in relations_map:
        for rel in relations_map[synset.id]:
            if rel.get("relType") in ("hypernym", "instance_hypernym"):
                hypernym_id = rel.get("target", "")
                break

    _quality_check = {
        "clarity": None,        # true | false (الوضوح)
        "conciseness": None,    # true | false (الإيجاز)
        "equivalence": None,    # true | false (التساوي)
        "positive": None,       # true | false (الإيجاب)
        "no_tautology": None,   # true | false (الخلو من اللغو)
    }
    doc["authored_definitions"] = {
        "terminological": {
            "text": "",
            "method": "",           # genus_differentia | iso704 | adapted_from_dict
            "genus_source": hypernym_id,  # auto-populated from hypernym relation
            "differentiae": "",
            "source": "",
            "quality_check": dict(_quality_check),
            "notes": "",
        },
        "linguistic": {
            "text": "",
            "method": "",           # synonym | antonym | example | derivation | context
            "source": "",
            "quality_check": dict(_quality_check),
            "notes": "",
        },
        "encyclopedic": {
            "text": "",
            "method": "",           # essential_properties | descriptive | classification
            "essential_characteristics": "",
            "accidental_characteristics": "",
            "source": "",
            "quality_check": dict(_quality_check),
            "notes": "",
        },
        "relationship_note": "",
        "definition_count": None,   # 1 | 2 | 3
        "skip_reason": "",
    }

    # ── Per-lemma enrichment ──
    lemma_list = []
    for lemma in synset.lemmas:
        ev = lemma_evidence.get(lemma)

        # Auto-populated evidence summary (read-only context for reviewer)
        attestation_count = 0
        dictionary_count = 0
        auto_roots = []
        auto_root_sources = []
        is_loanword = False

        if ev:
            attestation_count = len(ev.headword_entries)
            dict_names = set()
            for e in ev.headword_entries:
                dn = e.get("dict_name_ar", "")
                if dn:
                    dict_names.add(dn)
            dictionary_count = len(dict_names)
            auto_roots = list(ev.roots) if ev.roots else []
            auto_root_sources = list(ev.root_sources) if ev.root_sources else []
            is_loanword = ev.is_loanword

        entry = {
            "lemma": lemma,
            # Auto-populated evidence summary
            "_attestation_count": attestation_count,
            "_dictionary_count": dictionary_count,
            "_roots": auto_roots,
            "_root_sources": auto_root_sources,
            "_is_loanword": is_loanword,
            "_is_mwe": ev.is_multiword if ev else False,
            "_example_count": len(ev.examples) if ev else 0,
            # Linguist fills in:
            "verdict": "",              # accept | remove | modify | add_diacritics
            "modified_form": "",        # vocalized correction (min disambiguating diacritics)
            "root": "",                 # confirmed root, e.g., "ك ت ب"
            "usage": "",               # archaic | modern | common
            "eloquence": "",           # eloquent | neologism | colloquial
            "connotation": "",         # positive | negative | reverential | pejorative | neutral
            "literal_figurative": "",  # literal | figurative
            "figurative_relation": "", # e.g., "العلوّ والتدبير" (only if figurative)
            "nuance_note": "",         # what distinguishes this lemma from co-lemmas
            "typical_collocate": "",   # e.g., "كتاب + مقدّس / نافع"
        }

        # Verb-specific field
        if synset.pos == "v":
            entry["syntactic_frame"] = ""  # [لازم] | [متعدٍ بنفسه] | [متعدٍ بـ حرف]

        # Morphological validation (skip for MWEs — word-level checks don't apply)
        is_mwe = ev.is_multiword if ev else False
        if is_mwe:
            entry["morpho_check"] = {
                "broken_plural_linked": "skip",    # N/A for multi-word expression
                "orthography_normalized": "skip",
                "clitics_stripped": "skip",
            }
        else:
            entry["morpho_check"] = {
                "broken_plural_linked": None,    # true | false | null (N/A)
                "orthography_normalized": None,  # true | false | null
                "clitics_stripped": None,         # true | false | null
            }

        # MT error classification (for algorithmic feedback loop)
        entry["error_type"] = ""  # omission | substitution | dialectal_intrusion | orthographic_error | faux_ami
        entry["source"] = ""      # dictionary that confirms this usage
        entry["notes"] = ""
        entry["flags"] = []       # e.g., [MEANING_MISMATCH]

        lemma_list.append(entry)

    doc["lemmas"] = lemma_list

    # ── Missing lemmas ──
    doc["missing_lemmas"] = []
    # Example (commented in YAML output):
    # - lemma: "سِفْر"
    #   root: "س ف ر"
    #   usage: archaic
    #   eloquence: eloquent
    #   nuance_note: "يختص بالكتاب الكبير أو الديني"
    #   source: "لسان العرب"

    # ── Examples ──
    doc["examples"] = {
        "verdict": "",           # accept | revise | remove | add
        "quality": "",           # authentic_evidence | natural | calque | fabricated
        "revised_examples": [],
        "notes": "",
    }

    # ── Semantic relations ──
    doc["relations"] = {
        "hypernym_correct": None,  # true | false | null (not checked)
        "notes": "",
        "flags": [],
    }

    # ── Cultural fit ──
    doc["cultural_fit"] = {
        "needs_adaptation": False,
        "lexical_gap_type": "",   # none | true_gap | phraset | omission
        "gap_strategy": "",       # descriptive_gloss | mwe_phraset | empty_cili_node | near_synonym
        "cili_alignment": "",     # eq_synonym | eq_near_synonym | eq_has_hypernym | eq_has_hyponym
        "notes": "",
    }

    # ── Overall assessment ──
    doc["overall"] = {
        "quality": "",           # excellent | good | acceptable | poor | rejected
        "confidence": "",        # high | medium | low
        "general_notes": "",
        "flags": [],             # synset-level flags
    }

    return yaml.dump(doc, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_retrieval(conn, synset: SynsetInfo,
                  colbert_model, colbert_index, colbert_meta, colbert_ili) -> dict[str, dict]:
    """Run all 5 strategies on one synset, return raw results keyed by strategy letter."""
    results = {}

    a = strategy_a(conn, synset)
    results["A"] = a

    b = strategy_b(conn, synset, a)
    results["B"] = b

    exclude_ab = a["entry_ids"] | b["entry_ids"]
    c = strategy_c(conn, synset, exclude_ab)
    results["C"] = c

    if colbert_model is not None:
        d = strategy_d(synset, colbert_model, colbert_index, colbert_meta, colbert_ili)
        results["D"] = d

    exclude_abc = exclude_ab | c["entry_ids"]
    e = strategy_e(conn, synset, exclude_abc)
    results["E"] = e

    return results


def generate_for_synset(synset: SynsetInfo,
                        conn, authority_map: dict,
                        colbert_model, colbert_index, colbert_meta, colbert_ili,
                        all_synsets: dict[str, SynsetInfo],
                        relations_map: dict[str, list[dict]],
                        colbert_enabled: bool) -> tuple[str, str]:
    """Generate .md + .yaml content for one synset. Returns (md_str, yaml_str)."""

    # Run retrieval
    strategies = run_retrieval(conn, synset,
                               colbert_model, colbert_index, colbert_meta, colbert_ili)

    # Classify evidence for all entries
    for strat in strategies.values():
        for entry in strat.get("entries", []):
            entry["evidence_types"] = classify_evidence(entry, synset)

    # Merge by lemma
    lemma_ev = merge_evidence_by_lemma(synset, strategies)

    # Fetch dictionary examples for all headword entries
    all_entry_ids: set[int] = set()
    for ev in lemma_ev.values():
        for e in ev.headword_entries:
            eid = e.get("entry_id")
            if eid:
                all_entry_ids.add(eid)
    entry_examples = fetch_examples_for_entries(conn, all_entry_ids)

    # Attach examples to each LemmaEvidence (dedup by text)
    for ev in lemma_ev.values():
        seen_texts: set[str] = set()
        for e in ev.headword_entries:
            eid = e.get("entry_id")
            if eid and eid in entry_examples:
                for ex in entry_examples[eid]:
                    txt = ex["text"].strip()
                    if txt and txt not in seen_texts:
                        seen_texts.add(txt)
                        ev.examples.append(ex)

    # ColBERT-only entries
    colbert_only = identify_colbert_only(strategies)

    # English source
    oewn_data = get_oewn_data(synset.ili)

    # Relations + instance detection
    relations = relations_map.get(synset.id, [])
    is_instance = any(r["relType"] == "instance_hypernym" for r in relations)

    # Render
    md_content = render_md(synset, oewn_data, lemma_ev, colbert_only,
                           relations, all_synsets, authority_map, colbert_enabled,
                           is_instance=is_instance)
    yaml_content = render_yaml(synset, lemma_ev, authority_map,
                               relations_map=relations_map,
                               all_synsets=all_synsets)

    return md_content, yaml_content


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate linguist review documents for AWN4 synsets."
    )
    parser.add_argument("--synset-ids", nargs="+",
                        help="Specific synset IDs")
    parser.add_argument("--count", type=int, default=10,
                        help="Number of diverse synsets to select (default: 10)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for selection (default: 42)")
    parser.add_argument("--output-dir", default=str(SCRIPT_DIR / "output" / "reviews"),
                        help="Output directory (default: output/reviews/)")
    parser.add_argument("--no-colbert", action="store_true",
                        help="Skip ColBERT (faster, SQL-only)")
    parser.add_argument("--device", default="cpu",
                        help="PyTorch device for ColBERT (default: cpu)")
    parser.add_argument("--awn4-xml", default=str(AWN4_XML),
                        help="Path to awn4.xml")
    parser.add_argument("--dict-db", default=str(DICT_DB),
                        help="Path to arabic_dict.db")
    args = parser.parse_args()

    t0 = time.time()

    # Phase 1: Parse AWN4 synsets
    print("[1/6] Loading AWN4 synsets...")
    all_synsets = parse_awn4(Path(args.awn4_xml))

    # Phase 2: Parse AWN4 relations
    print("[2/6] Loading AWN4 relations...")
    relations_map = parse_awn4_relations(Path(args.awn4_xml))

    # Phase 3: Select synsets
    print("[3/6] Selecting synsets...")
    if args.synset_ids:
        selected = [all_synsets[sid] for sid in args.synset_ids if sid in all_synsets]
        missing = [sid for sid in args.synset_ids if sid not in all_synsets]
        if missing:
            print(f"  Warning: not found: {missing}")
    else:
        selected = select_diverse_synsets(all_synsets, count=args.count, seed=args.seed)

    print(f"  Selected {len(selected)} synsets:")
    for s in selected:
        print(f"    {s.id} [{s.pos}] {', '.join(s.lemmas[:3])}")

    # Phase 4: Connect to DB
    print("[4/6] Connecting to dictionary database...")
    conn = get_connection(Path(args.dict_db))
    authority_map = build_authority_map(conn)
    print(f"  {len(authority_map)} dictionaries")

    # Phase 5: Load ColBERT (optional)
    colbert_model, colbert_index, colbert_meta, colbert_ili = None, None, None, None
    colbert_enabled = not args.no_colbert
    if colbert_enabled:
        print("[5/6] Loading ColBERT model and PLAID index...")
        try:
            sys.path.insert(0, str(COLBERT_DIR))
            import colbert_index as ci
            colbert_meta, colbert_ili = ci.load_metadata()
            colbert_model = ci.load_model(device=args.device)
            colbert_index = ci.load_index(backend="plaid")
            print("  ColBERT ready")
        except Exception as e:
            print(f"  ColBERT load failed: {e} — continuing without Strategy D")
            colbert_enabled = False
    else:
        print("[5/6] Skipping ColBERT (--no-colbert)")

    # Phase 6: Generate review documents
    print(f"[6/6] Generating {len(selected)} review documents...\n")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, synset in enumerate(selected, 1):
        print(f"  [{i}/{len(selected)}] {synset.id} — {', '.join(synset.lemmas[:2])}")
        t_syn = time.time()

        md_content, yaml_content = generate_for_synset(
            synset, conn, authority_map,
            colbert_model, colbert_index, colbert_meta, colbert_ili,
            all_synsets, relations_map, colbert_enabled,
        )

        safe_name = synset.id
        md_path = output_dir / f"{safe_name}.md"
        yaml_path = output_dir / f"{safe_name}.yaml"

        md_path.write_text(md_content, encoding="utf-8")
        yaml_path.write_text(yaml_content, encoding="utf-8")

        elapsed_syn = time.time() - t_syn
        print(f"    → {md_path.name} ({md_path.stat().st_size / 1024:.0f} KB) + .yaml ({elapsed_syn:.1f}s)")

    elapsed = time.time() - t0
    print(f"\nDone! {len(selected)} review documents in {elapsed:.1f}s")
    print(f"Output: {output_dir}/")


if __name__ == "__main__":
    main()
