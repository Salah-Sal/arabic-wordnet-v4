#!/usr/bin/env python3
"""Dictionary Evidence Retrieval for AWN4 Synset Review.

Runs 5 retrieval strategies against the Arabic dictionary database for
diverse AWN4 synsets, producing structured reports that show what each
strategy finds, unique contributions, and evidence types.

Strategies:
  A — Headword Match (SQL Tier 1)
  B — Root Family (SQL Tier 2)
  C — Definition Search (FTS5 BM25)
  D — ColBERT Semantic Search (PLAID index)
  E — Translation Cross-reference (ARABTERM via English bridge)

Usage:
  python retrieve_dict_evidence.py                          # 10 diverse synsets, all strategies
  python retrieve_dict_evidence.py --no-colbert             # skip ColBERT (faster)
  python retrieve_dict_evidence.py --synset-ids awn4-06410904-n awn4-00001740-a
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Path setup ───────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
AWN4_BASE = SCRIPT_DIR.parent.parent              # arabic-wordnet-v4/
PROJECT_ROOT = AWN4_BASE.parent                    # wn-project/
DICT_ROOT = PROJECT_ROOT / "arabic-dictionaries"
EXTRACTION_DIR = DICT_ROOT / "extraction"
COLBERT_DIR = AWN4_BASE / "experiments" / "colbertv2 exp"

AWN4_XML = AWN4_BASE / "output" / "awn4.xml"
DICT_DB = DICT_ROOT / "db" / "arabic_dict.db"

# RAG pipeline imports
sys.path.insert(0, str(EXTRACTION_DIR))
from rag.db import get_connection, build_authority_map  # noqa: E402
from rag.retrieval import (                              # noqa: E402
    tier1_lookup,
    tier2_root_family,
    tier3_fts_search,
    extract_arabic_keywords,
    TIER3_TRANSLATION_SQL,
    _ENTRY_COLUMNS,
)
from rag.similarity import definition_similarity, ARABIC_STOPWORDS  # noqa: E402
from common import normalize_arabic, strip_diacritics    # noqa: E402


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class SynsetInfo:
    id: str
    ili: str
    pos: str
    lemmas: list[str]
    definition: str
    examples: list[str]


# ── AWN4 XML parsing ────────────────────────────────────────────────────────

def parse_awn4(xml_path: Path) -> dict[str, SynsetInfo]:
    """Parse AWN4 XML into {synset_id: SynsetInfo} using iterparse."""
    print(f"  Parsing AWN4 XML: {xml_path.name}")
    t0 = time.time()

    lemma_to_synsets: dict[str, list[str]] = defaultdict(list)
    synset_data: dict[str, dict] = {}

    current_entry = None
    current_synset_id = None
    current_synset = None

    for event, elem in ET.iterparse(str(xml_path), events=("start", "end")):
        tag = elem.tag
        if event == "start":
            if tag == "LexicalEntry":
                current_entry = {"lemma": "", "pos": "", "synset_ids": []}
            elif tag == "Synset":
                current_synset_id = elem.get("id")
                current_synset = {
                    "ili": elem.get("ili", ""),
                    "pos": elem.get("partOfSpeech", ""),
                    "definition": "",
                    "examples": [],
                }
        elif event == "end":
            if tag == "Lemma" and current_entry is not None:
                current_entry["lemma"] = elem.get("writtenForm", "")
                current_entry["pos"] = elem.get("partOfSpeech", "")
            elif tag == "Sense" and current_entry is not None:
                sid = elem.get("synset", "")
                if sid:
                    current_entry["synset_ids"].append(sid)
            elif tag == "LexicalEntry" and current_entry is not None:
                lemma = current_entry["lemma"]
                for sid in current_entry["synset_ids"]:
                    lemma_to_synsets[sid].append(lemma)
                current_entry = None
            elif tag == "Definition" and current_synset is not None:
                current_synset["definition"] = elem.text or ""
            elif tag == "Example" and current_synset is not None:
                if elem.text:
                    current_synset["examples"].append(elem.text)
            elif tag == "Synset" and current_synset is not None:
                synset_data[current_synset_id] = current_synset
                current_synset = None
                current_synset_id = None
            elem.clear()

    result = {}
    for sid, data in synset_data.items():
        lemmas = list(dict.fromkeys(lemma_to_synsets.get(sid, [])))
        result[sid] = SynsetInfo(
            id=sid, ili=data["ili"], pos=data["pos"],
            lemmas=lemmas, definition=data["definition"],
            examples=data["examples"],
        )

    print(f"  Parsed {len(result):,} synsets in {time.time() - t0:.1f}s")
    return result


# ── Diverse synset selection ─────────────────────────────────────────────────

_NON_ARABIC_RE = re.compile(r'[a-zA-Z0-9]')

def select_diverse_synsets(synsets: dict[str, SynsetInfo],
                           count: int = 10,
                           seed: int = 42) -> list[SynsetInfo]:
    """Select diverse synsets across POS, complexity, and domain.

    Prefers synsets with single-word Arabic lemmas (more likely to have
    dictionary entries) while still including some multi-word/loanword cases.
    """
    rng = random.Random(seed)

    # Group by POS, filtering to synsets with definitions
    by_pos: dict[str, list[SynsetInfo]] = defaultdict(list)
    for s in synsets.values():
        if s.definition and s.lemmas:
            by_pos[s.pos].append(s)

    # Target distribution: 4n, 2v, 2a, 2r
    pos_targets = [("n", 4), ("v", 2), ("a", 2), ("r", 2)]
    selected = []

    for pos, target_count in pos_targets:
        pool = by_pos.get(pos, [])
        if not pool:
            continue

        # Bucket by profile
        single_word = []   # single-word Arabic lemmas (best for dict lookup)
        multi_lemma = []   # 3+ lemmas (polysemous)
        loanword = []      # contains non-Arabic chars

        for s in pool:
            first_lemma = s.lemmas[0]
            is_loan = bool(_NON_ARABIC_RE.search(first_lemma))
            has_space = " " in first_lemma

            if is_loan:
                loanword.append(s)
            elif len(s.lemmas) >= 3 and not has_space:
                multi_lemma.append(s)
            elif not has_space:
                single_word.append(s)

        # Priority: single-word first (most likely to find dict evidence),
        # then multi-lemma, then loanword (1 max)
        picks = []

        # Most slots go to single-word terms
        sw_count = max(1, target_count - 1)
        if single_word:
            rng.shuffle(single_word)
            picks.extend(single_word[:sw_count])

        # Fill remaining with multi-lemma or loanword
        remaining = target_count - len(picks)
        if remaining > 0 and multi_lemma:
            rng.shuffle(multi_lemma)
            picks.extend(multi_lemma[:remaining])
            remaining = target_count - len(picks)
        if remaining > 0 and loanword:
            rng.shuffle(loanword)
            picks.extend(loanword[:remaining])

        selected.extend(picks[:target_count])

    return selected[:count]


# ── Strategy A: Headword Match (SQL Tier 1) ──────────────────────────────────

def strategy_a(conn: sqlite3.Connection, synset: SynsetInfo) -> dict:
    """Exact headword_norm lookup for each synset lemma.

    Also tries individual words from multi-word lemmas as fallback.
    """
    t0 = time.time()

    # Primary: try full lemmas
    all_terms = list(synset.lemmas)

    # Fallback: for multi-word lemmas, also try individual words
    # (skip Arabic stop words like غير, كل, بعض to avoid noise)
    for lemma in synset.lemmas:
        if " " in lemma:
            for word in lemma.split():
                word = word.strip()
                if (len(word) > 2
                        and word not in ARABIC_STOPWORDS
                        and word not in all_terms):
                    all_terms.append(word)

    results_by_lemma = tier1_lookup(conn, all_terms)

    entries = []
    seen_ids = set()
    for norm_term, rows in results_by_lemma.items():
        for row in rows:
            eid = row["entry_id"]
            if eid not in seen_ids:
                seen_ids.add(eid)
                entries.append(_row_to_dict(row))

    # Prefix-stripping fallback: for lemmas with zero results that start
    # with a single-char proclitic (بـ كـ لـ فـ وـ), try the base form
    _SIMPLE_PROCLITICS = {"ب", "ك", "ل", "ف", "و"}
    prefix_stripped = []
    for lemma in synset.lemmas:
        norm = normalize_arabic(lemma)
        if not results_by_lemma.get(norm) and len(lemma) > 3 and lemma[0] in _SIMPLE_PROCLITICS:
            prefix_stripped.append((lemma, lemma[0], lemma[1:]))

    if prefix_stripped:
        fallback_terms = [t[2] for t in prefix_stripped]
        fallback_results = tier1_lookup(conn, fallback_terms)
        for orig_lemma, prefix, stripped in prefix_stripped:
            norm_stripped = normalize_arabic(stripped)
            for row in fallback_results.get(norm_stripped, []):
                eid = row["entry_id"]
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    d = _row_to_dict(row)
                    d["_prefix_stripped"] = True
                    d["_stripped_prefix"] = prefix
                    d["_original_lemma"] = orig_lemma
                    d["_stripped_form"] = stripped
                    entries.append(d)

    return {
        "strategy": "A",
        "name": "Headword Match (SQL Tier 1)",
        "query": ", ".join(synset.lemmas),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "count": len(entries),
        "entry_ids": seen_ids,
        "entries": entries,
    }


# ── Strategy B: Root Family (SQL Tier 2) ─────────────────────────────────────

def strategy_b(conn: sqlite3.Connection, synset: SynsetInfo,
               tier1_result: dict) -> dict:
    """Root-family expansion using roots from Tier 1 results."""
    t0 = time.time()

    # Extract roots from Tier 1 entries
    roots = set()
    for entry in tier1_result["entries"]:
        if entry.get("root"):
            roots.add(entry["root"])

    # Fallback: query DB directly for roots if Tier 1 found entries but no roots
    if not roots and tier1_result["entries"]:
        for lemma in synset.lemmas:
            norm = normalize_arabic(lemma)
            row = conn.execute(
                "SELECT DISTINCT root FROM entries WHERE headword_norm = ? AND root IS NOT NULL LIMIT 5",
                (norm,)
            ).fetchall()
            for r in row:
                if r["root"]:
                    roots.add(r["root"])

    tier1_ids = tier1_result["entry_ids"]
    rows = tier2_root_family(conn, roots, tier1_ids)

    entries = []
    seen_ids = set()
    for row in rows:
        eid = row["entry_id"]
        if eid not in seen_ids:
            seen_ids.add(eid)
            entries.append(_row_to_dict(row))
            if len(entries) >= 200:  # cap total across all roots
                break

    return {
        "strategy": "B",
        "name": "Root Family (SQL Tier 2)",
        "query": "root=" + ",".join(sorted(roots)) if roots else "(no root found)",
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "count": len(entries),
        "entry_ids": seen_ids,
        "entries": entries,
    }


# ── Strategy C: Definition Search (FTS5 BM25) ───────────────────────────────

def strategy_c(conn: sqlite3.Connection, synset: SynsetInfo,
               exclude_ids: set[int]) -> dict:
    """FTS5 definition-text search using synset definition keywords."""
    t0 = time.time()

    keywords = extract_arabic_keywords(synset.definition)
    if not keywords:
        return {
            "strategy": "C", "name": "Definition Search (FTS5 BM25)",
            "query": "(no keywords extracted)", "elapsed_ms": 0,
            "count": 0, "entry_ids": set(), "entries": [],
        }

    rows = tier3_fts_search(conn, keywords, exclude_ids)

    entries = []
    seen_ids = set()
    for row in rows:
        eid = row["entry_id"]
        if eid not in seen_ids:
            seen_ids.add(eid)
            entries.append(_row_to_dict(row))

    return {
        "strategy": "C",
        "name": "Definition Search (FTS5 BM25)",
        "query": " OR ".join(keywords),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "count": len(entries),
        "entry_ids": seen_ids,
        "entries": entries,
    }


# ── Strategy D: ColBERT Semantic Search ──────────────────────────────────────

def strategy_d(synset: SynsetInfo, model, index, metadata, ili_map) -> dict:
    """ColBERT semantic search with 3 sub-queries (lemma, definition, combined)."""
    t0 = time.time()

    ci = sys.modules.get("colbert_index")
    if ci is None:
        return {
            "strategy": "D", "name": "ColBERT Semantic Search",
            "query": "(not loaded)", "elapsed_ms": 0,
            "count": 0, "entry_ids": set(), "entries": [],
        }

    merged: dict[int, dict] = {}  # entry_id → best result

    # Sub-query D1: lemma(s)
    lemma_q = "; ".join(synset.lemmas)
    d1 = ci.search(lemma_q, model, index, metadata, ili_map, k=20)
    for r in d1:
        _merge_colbert(merged, r, "D1:lemma")

    # Sub-query D2: definition
    def_q = synset.definition[:200]
    d2 = ci.search(def_q, model, index, metadata, ili_map, k=20)
    for r in d2:
        _merge_colbert(merged, r, "D2:definition")

    # Sub-query D3: combined
    combined_q = f"{lemma_q} | {synset.definition[:150]}"
    d3 = ci.search(combined_q, model, index, metadata, ili_map, k=20)
    for r in d3:
        _merge_colbert(merged, r, "D3:combined")

    entries = sorted(merged.values(), key=lambda x: x.get("colbert_score", 0), reverse=True)
    seen_ids = {e["entry_id"] for e in entries if e["entry_id"] > 0}

    return {
        "strategy": "D",
        "name": "ColBERT Semantic Search",
        "query": f"D1:'{lemma_q}' | D2:def | D3:combined",
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "count": len(entries),
        "entry_ids": seen_ids,
        "entries": entries,
    }


def _merge_colbert(merged: dict, result: dict, sub_query: str):
    """Merge a ColBERT result into the merged dict, keeping best score."""
    doc_id = result.get("synset_id", "")
    # Extract numeric entry_id from "dict-{key}-{id}" format
    parts = doc_id.rsplit("-", 1)
    entry_id = int(parts[-1]) if len(parts) >= 2 and parts[-1].isdigit() else -1

    score = result.get("score", 0.0)

    if entry_id in merged and merged[entry_id].get("colbert_score", 0) >= score:
        return

    merged[entry_id] = {
        "entry_id": entry_id,
        "headword": "; ".join(result.get("lemmas", [])),
        "headword_bare": "",
        "root": None,
        "pos": result.get("pos"),
        "definitions_text": result.get("definition", ""),
        "translation_en": None,
        "dict_key": doc_id.split("-")[1] if "-" in doc_id else "",
        "dict_name_en": "",
        "source_type": result.get("source_type", ""),
        "period": None,
        "colbert_score": round(score, 2),
        "colbert_sub_query": sub_query,
    }


# ── Strategy E: Translation Cross-reference ──────────────────────────────────

def strategy_e(conn: sqlite3.Connection, synset: SynsetInfo,
               exclude_ids: set[int]) -> dict:
    """Search ARABTERM entries via English translation bridge using ILI."""
    t0 = time.time()

    if not synset.ili:
        return {
            "strategy": "E", "name": "Translation Cross-reference",
            "query": "(no ILI mapping)", "elapsed_ms": 0,
            "count": 0, "entry_ids": set(), "entries": [],
        }

    # Get English lemmas via the wn library
    en_lemmas = _get_english_lemmas(synset.ili)
    if not en_lemmas:
        return {
            "strategy": "E", "name": "Translation Cross-reference",
            "query": f"ILI={synset.ili} (no English equivalent found)",
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
            "count": 0, "entry_ids": set(), "entries": [],
        }

    # Build FTS5 MATCH for English terms
    match_expr = " OR ".join(f'"{t}"' for t in en_lemmas[:5])
    id_list = list(exclude_ids) if exclude_ids else [0]
    placeholders = ",".join("?" * len(id_list))
    sql = TIER3_TRANSLATION_SQL.format(placeholders=placeholders)

    rows = conn.execute(sql, [match_expr] + id_list).fetchall()

    entries = []
    seen_ids = set()
    for row in rows:
        eid = row["entry_id"]
        if eid not in seen_ids:
            seen_ids.add(eid)
            entries.append(_row_to_dict(row))

    return {
        "strategy": "E",
        "name": "Translation Cross-reference",
        "query": f"EN: {', '.join(en_lemmas[:5])}",
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "count": len(entries),
        "entry_ids": seen_ids,
        "entries": entries,
    }


def _get_english_lemmas(ili: str) -> list[str]:
    """Look up English lemmas for an ILI via the wn library."""
    try:
        import wn
        oewn_synsets = wn.synsets(ili=ili, lang="en")
        lemmas = []
        for ss in oewn_synsets:
            for w in ss.words():
                lemma = w.lemma()
                if lemma not in lemmas:
                    lemmas.append(lemma)
        return lemmas
    except Exception:
        return []


# ── Helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with standard fields."""
    return {
        "entry_id": row["entry_id"],
        "headword": row["headword"],
        "headword_bare": row["headword_bare"],
        "root": row["root"],
        "pos": row["pos"],
        "definitions_text": (row["definitions_text"] or "")[:300],
        "translation_en": row["translation_en"],
        "dict_key": row["dict_key"],
        "dict_name_en": row["dict_name_en"],
        "source_type": row["source_type"],
        "period": row["period"],
    }


# ── Evidence classification ──────────────────────────────────────────────────

# POS compatibility for synonym candidate filtering
_POS_COMPAT = {
    "n": {"noun", "proper_noun"},
    "v": {"verb"},
    "a": {"adj"},
}

def _pos_compatible(synset_pos: str, entry_pos: str) -> bool:
    """Check if an entry's POS is compatible with the synset's POS.

    Returns True if compatible or uncertain (no POS data, ambiguous POS).
    Only filters when both sides have clear, conflicting POS.
    """
    if not entry_pos or not synset_pos:
        return True
    allowed = _POS_COMPAT.get(synset_pos)
    if not allowed:
        return True  # no map for this synset POS (e.g., adverb)
    if entry_pos not in {"noun", "verb", "adj", "proper_noun"}:
        return True  # ambiguous entry POS (phrase/other/particle)
    return entry_pos in allowed


def classify_evidence(entry: dict, synset: SynsetInfo) -> list[str]:
    """Classify the evidence type of a dictionary entry for a synset."""
    types = []
    hw_norm = normalize_arabic(entry.get("headword_bare") or entry.get("headword", ""))
    lemma_norms = {normalize_arabic(l) for l in synset.lemmas}

    # Lemma match
    if hw_norm in lemma_norms:
        types.append("lemma_match")

    # Definition support / synonym candidate
    entry_def = entry.get("definitions_text", "")
    if entry_def and synset.definition:
        sim = definition_similarity(entry_def, synset.definition)
        if sim > 0.30:
            if hw_norm not in lemma_norms:
                # POS filter: skip synonym candidates with clearly mismatching POS
                entry_pos = (entry.get("pos") or "").strip().lower()
                if _pos_compatible(synset.pos, entry_pos):
                    types.append("synonym_candidate")
            else:
                types.append("definition_support")
        elif sim > 0.15:
            types.append("definition_support")

    # Morphological kin (same root, different headword)
    if entry.get("root") and hw_norm not in lemma_norms:
        types.append("morphological_kin")

    # Translation bridge
    if entry.get("translation_en"):
        types.append("translation_bridge")

    if not types:
        types.append("contextual")

    return types


# ── Summary computation ─────────────────────────────────────────────────────

def compute_summary(strategies: list[dict]) -> dict:
    """Compute per-strategy unique contributions and source breakdown."""
    all_ids: dict[str, set[int]] = {}
    for s in strategies:
        all_ids[s["strategy"]] = s["entry_ids"]

    union_ids = set()
    for ids in all_ids.values():
        union_ids |= ids

    # Unique contributions: entries found ONLY by this strategy
    unique_per = {}
    for key, ids in all_ids.items():
        others = set()
        for k2, ids2 in all_ids.items():
            if k2 != key:
                others |= ids2
        unique_per[key] = len(ids - others)

    # Source breakdown across all entries
    source_counts: dict[str, int] = defaultdict(int)
    for s in strategies:
        for e in s["entries"]:
            src = e.get("source_type", "unknown")
            source_counts[src] += 1

    return {
        "total_unique": len(union_ids),
        "unique_per_strategy": unique_per,
        "source_breakdown": dict(source_counts),
    }


# ── Process one synset ───────────────────────────────────────────────────────

def process_synset(conn, synset: SynsetInfo,
                   colbert_model, colbert_index, colbert_meta, colbert_ili) -> dict:
    """Run all 5 strategies on one synset."""
    t0 = time.time()
    results = []

    # A: Headword match
    a = strategy_a(conn, synset)
    results.append(a)
    print(f"    A: {a['count']} entries ({a['elapsed_ms']:.0f}ms)")

    # B: Root family
    b = strategy_b(conn, synset, a)
    results.append(b)
    print(f"    B: {b['count']} entries ({b['elapsed_ms']:.0f}ms)")

    # C: Definition FTS5
    exclude_ab = a["entry_ids"] | b["entry_ids"]
    c = strategy_c(conn, synset, exclude_ab)
    results.append(c)
    print(f"    C: {c['count']} entries ({c['elapsed_ms']:.0f}ms)")

    # D: ColBERT (optional)
    if colbert_model is not None:
        d = strategy_d(synset, colbert_model, colbert_index, colbert_meta, colbert_ili)
        results.append(d)
        print(f"    D: {d['count']} entries ({d['elapsed_ms']:.0f}ms)")

    # E: Translation cross-reference
    exclude_abc = exclude_ab | c["entry_ids"]
    e = strategy_e(conn, synset, exclude_abc)
    results.append(e)
    print(f"    E: {e['count']} entries ({e['elapsed_ms']:.0f}ms)")

    # Classify evidence for top entries per strategy
    for s in results:
        for entry in s["entries"][:20]:
            entry["evidence_types"] = classify_evidence(entry, synset)

    summary = compute_summary(results)

    return {
        "synset": {
            "id": synset.id, "ili": synset.ili, "pos": synset.pos,
            "lemmas": synset.lemmas, "definition": synset.definition,
            "examples": synset.examples,
        },
        "strategies": {s["strategy"]: _serialize_strategy(s) for s in results},
        "summary": summary,
        "elapsed_total_ms": round((time.time() - t0) * 1000, 1),
    }


def _serialize_strategy(s: dict) -> dict:
    """Prepare a strategy result for JSON serialization."""
    return {
        "name": s["name"],
        "query": s["query"],
        "elapsed_ms": s["elapsed_ms"],
        "count": s["count"],
        "entries": s["entries"][:20],  # cap at 20 for readability
    }


# ── Output writers ───────────────────────────────────────────────────────────

def write_json(reports: list[dict], metadata: dict, path: Path):
    """Write machine-readable JSON output."""
    output = {"metadata": metadata, "synsets": reports}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"  JSON: {path} ({path.stat().st_size / 1024:.0f} KB)")


def write_markdown(reports: list[dict], metadata: dict, path: Path):
    """Write human-readable Markdown report."""
    lines = [
        "# Dictionary Evidence Retrieval Report\n",
        f"**Date:** {metadata['timestamp']}  ",
        f"**Synsets:** {metadata['synset_count']}  ",
        f"**Total time:** {metadata['total_elapsed_s']:.1f}s  ",
        f"**Strategies:** A (Headword), B (Root Family), C (FTS5), D (ColBERT), E (Translation)\n",
        "---\n",
    ]

    for i, report in enumerate(reports, 1):
        syn = report["synset"]
        lines.append(f"## {i}. `{syn['id']}` — {', '.join(syn['lemmas'][:3])}\n")
        lines.append(f"- **POS:** {syn['pos']}")
        lines.append(f"- **Lemmas ({len(syn['lemmas'])}):** {' ، '.join(syn['lemmas'])}")
        lines.append(f"- **Definition:** {syn['definition'][:200]}")
        if syn["examples"]:
            lines.append(f"- **Examples:** {' | '.join(syn['examples'][:3])}")
        lines.append("")

        for key in ["A", "B", "C", "D", "E"]:
            strat = report["strategies"].get(key)
            if not strat:
                continue

            lines.append(f"### Strategy {key} — {strat['name']}")
            lines.append(f"*Query: {strat['query'][:100]} ({strat['elapsed_ms']:.0f}ms, {strat['count']} results)*\n")

            top = strat["entries"][:10]
            if top:
                lines.append("| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |")
                lines.append("|---|----------|------------|--------|----------|---------------------|")
                for j, e in enumerate(top, 1):
                    hw = e.get("headword", "")[:20]
                    dk = e.get("dict_key", "")[:20] or e.get("dict_name_en", "")[:20]
                    src = e.get("source_type", "")
                    ev = ", ".join(e.get("evidence_types", []))[:30]
                    defn = (e.get("definitions_text", "") or "")[:60].replace("|", "\\|").replace("\n", " ")
                    lines.append(f"| {j} | {hw} | {dk} | {src} | {ev} | {defn} |")
                lines.append("")
            else:
                lines.append("*No results*\n")

        # Summary
        summary = report["summary"]
        lines.append("### Summary")
        lines.append(f"- **Total unique entries:** {summary['total_unique']}")
        uniq = summary["unique_per_strategy"]
        uniq_str = ", ".join(f"{k}={v}" for k, v in sorted(uniq.items()))
        lines.append(f"- **Unique contributions:** {uniq_str}")
        src_str = ", ".join(f"{k}: {v}" for k, v in sorted(summary["source_breakdown"].items()))
        lines.append(f"- **Sources:** {src_str}")
        lines.append(f"- **Time:** {report['elapsed_total_ms']:.0f}ms")
        lines.append("\n---\n")

    # Global summary
    lines.append("## Global Summary\n")
    total_uniq = [r["summary"]["total_unique"] for r in reports]
    lines.append(f"- **Avg entries per synset:** {sum(total_uniq) / len(total_uniq):.0f}")
    for key in ["A", "B", "C", "D", "E"]:
        vals = [r["summary"]["unique_per_strategy"].get(key, 0) for r in reports]
        if any(v > 0 for v in vals):
            lines.append(f"- **Strategy {key} avg unique:** {sum(vals) / len(vals):.1f}")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Markdown: {path} ({path.stat().st_size / 1024:.0f} KB)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Retrieve dictionary evidence for AWN4 synsets."
    )
    parser.add_argument("--synset-ids", nargs="+",
                        help="Specific synset IDs (overrides --count)")
    parser.add_argument("--count", type=int, default=10,
                        help="Number of diverse synsets to select (default: 10)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for selection (default: 42)")
    parser.add_argument("--output-dir", default=str(SCRIPT_DIR / "output"),
                        help="Output directory")
    parser.add_argument("--no-colbert", action="store_true",
                        help="Skip ColBERT (faster, SQL-only)")
    parser.add_argument("--device", default="cpu",
                        help="PyTorch device for ColBERT (default: cpu)")
    parser.add_argument("--awn4-xml", default=str(AWN4_XML),
                        help="Path to awn4.xml")
    parser.add_argument("--dict-db", default=str(DICT_DB),
                        help="Path to arabic_dict.db")
    args = parser.parse_args()

    t0_global = time.time()

    # Phase 1: Parse AWN4
    print("[1/5] Loading AWN4 synsets...")
    synsets = parse_awn4(Path(args.awn4_xml))

    # Phase 2: Select synsets
    print("[2/5] Selecting synsets...")
    if args.synset_ids:
        selected = [synsets[sid] for sid in args.synset_ids if sid in synsets]
        missing = [sid for sid in args.synset_ids if sid not in synsets]
        if missing:
            print(f"  Warning: {len(missing)} synset IDs not found: {missing}")
    else:
        selected = select_diverse_synsets(synsets, count=args.count, seed=args.seed)

    print(f"  Selected {len(selected)} synsets:")
    for s in selected:
        print(f"    {s.id} [{s.pos}] {', '.join(s.lemmas[:3])}")

    # Phase 3: Connect to DB
    print("[3/5] Connecting to dictionary database...")
    conn = get_connection(Path(args.dict_db))
    authority_map = build_authority_map(conn)
    print(f"  {len(authority_map)} dictionaries loaded")

    # Phase 4: Load ColBERT (optional)
    colbert_model, colbert_index, colbert_meta, colbert_ili = None, None, None, None
    if not args.no_colbert:
        print("[4/5] Loading ColBERT model and PLAID index...")
        try:
            sys.path.insert(0, str(COLBERT_DIR))
            import colbert_index as ci
            colbert_meta, colbert_ili = ci.load_metadata()
            colbert_model = ci.load_model(device=args.device)
            colbert_index = ci.load_index(backend="plaid")
            print("  ColBERT ready")
        except Exception as e:
            print(f"  ColBERT load failed: {e} — continuing without Strategy D")
    else:
        print("[4/5] Skipping ColBERT (--no-colbert)")

    # Phase 5: Run strategies
    print(f"[5/5] Running retrieval on {len(selected)} synsets...\n")
    reports = []
    for i, synset in enumerate(selected, 1):
        print(f"  [{i}/{len(selected)}] {synset.id} — {', '.join(synset.lemmas[:2])}")
        report = process_synset(conn, synset,
                                colbert_model, colbert_index,
                                colbert_meta, colbert_ili)
        reports.append(report)
        print()

    # Write outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    elapsed = time.time() - t0_global
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "synset_count": len(reports),
        "total_elapsed_s": round(elapsed, 1),
        "db_path": str(args.dict_db),
        "colbert_enabled": not args.no_colbert,
        "strategies": ["A", "B", "C"] + (["D"] if not args.no_colbert else []) + ["E"],
    }

    print("Writing outputs...")
    write_json(reports, meta, output_dir / "results.json")
    write_markdown(reports, meta, output_dir / "report.md")

    print(f"\nDone! {len(reports)} synsets in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
