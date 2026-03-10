#!/usr/bin/env python3
"""
collect_evidence.py — جمع الشواهد المعجمية الآلي
Automated Dictionary Evidence Collection for AWN4 Synsets.

Implements the 9-step evidence collection algorithm (v3, ال-aware).
Produces YAML artifacts conforming to EVIDENCE_SCHEMA.yaml.

Usage:
    python3 tools/collect_evidence.py awn4-05162506-n
    python3 tools/collect_evidence.py --batch batches/my_batch.txt
    python3 tools/collect_evidence.py awn4-05162506-n awn4-03466051-n
    python3 tools/collect_evidence.py --output-dir output/evidence awn4-05162506-n
    python3 tools/collect_evidence.py --db data/arabic_dict.db awn4-05162506-n

Requirements:
    pip install wn pyyaml
    wn database must contain awn4 and oewn:2024.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import wn
except ImportError:
    print("Error: wn package not installed. Run: pip install wn", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Arabic Text Utilities (embedded from arabic-dictionaries/extraction/common.py)
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
    """Remove Arabic diacritics (tashkeel) from text."""
    return DIACRITICS_RE.sub("", text)


def normalize_arabic(text: str) -> str:
    """Full Arabic normalization: strip diacritics + normalize alef/hamza/ya/tatweel."""
    text = strip_diacritics(text)
    text = re.sub("[أإآ]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("\u0640", "")
    return text.strip()


def extract_keywords(text: str) -> list[str]:
    """Extract Arabic keywords from text, excluding stopwords and short tokens."""
    text_norm = normalize_arabic(text)
    tokens = ARABIC_TOKEN_RE.findall(text_norm)
    return [t for t in tokens if len(t) > 2 and t not in ARABIC_STOPWORDS]


def al_variants(lemma_norm: str) -> tuple[str, str]:
    """Return (form1, form2) for ال-aware queries.

    If lemma already starts with ال, returns (lemma, stripped).
    Otherwise returns (lemma, 'ال' + lemma).
    Both forms are used in WHERE headword_norm IN (?1, ?2).
    """
    if lemma_norm.startswith("ال"):
        return (lemma_norm, lemma_norm[2:])
    # Avoid generating nonsensical الل... forms for proclitic+article fusions
    if lemma_norm.startswith("لل"):
        return (lemma_norm, lemma_norm)
    return (lemma_norm, "ال" + lemma_norm)


# Proclitic+article fusions: preposition + ال merged into a single prefix.
# These appear in multiword lemma components (e.g. "للتشكيل" = لِ + الـ + تشكيل).
_PROCLITIC_PREFIXES = [
    ("لل",  2),   # لِ + ال  ("for the")
    ("بال", 3),   # بِ + ال  ("with the")
    ("وال", 3),   # وَ + ال  ("and the")
    ("كال", 3),   # كَ + ال  ("like the")
]


def strip_proclitics(word_norm: str) -> str | None:
    """Strip proclitic+article prefix from a normalized Arabic word.

    Returns the bare noun stem, or None if no safe pattern matches.
    Only handles preposition+الـ fusions. Requires stem length >= 3.
    """
    for prefix, prefix_len in _PROCLITIC_PREFIXES:
        if word_norm.startswith(prefix) and len(word_norm) > prefix_len + 2:
            return word_norm[prefix_len:]
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SQL Templates (from evidence_collection/SQL_QUERIES.sql)
# ═══════════════════════════════════════════════════════════════════════════════

_ENTRY_COLUMNS = """
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year"""

SQL_STEP1 = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;
"""

SQL_STEP2 = """
SELECT
    e.id              AS entry_id,
    e.headword,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year,
    def.sense_index,
    def.text          AS definition_text,
    def.is_raw
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions def ON def.entry_id = e.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.death_year ASC NULLS LAST, d.name_en, def.sense_index;
"""

SQL_STEP3A = """
SELECT DISTINCT
    e.root,
    e.root_source,
    e.id AS from_entry_id
FROM entries e
WHERE e.headword_norm IN (?1, ?2)
  AND e.root IS NOT NULL
ORDER BY
    CASE e.root_source
        WHEN 'ocr'  THEN 1
        WHEN 'lane' THEN 2
        WHEN 'camel' THEN 3
        ELSE 4
    END;
"""

# Step 3b uses dynamic excluded_ids — built at runtime
SQL_STEP3B_TEMPLATE = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE (e.root = ?1 OR e.headword_norm = ?1)
  AND e.id NOT IN ({{excluded_ids}})
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en
LIMIT 200;
"""

SQL_STEP6 = """
SELECT
    ex.entry_id,
    e.headword,
    d.key             AS dict_key,
    d.name_en         AS dict_name_en,
    d.name_ar         AS dict_name_ar,
    ex.idx,
    ex.type,
    ex.text           AS example_text,
    ex.attribution
FROM examples ex
JOIN entries e ON ex.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY
    CASE ex.type
        WHEN 'quran'   THEN 1
        WHEN 'hadith'  THEN 2
        WHEN 'poetry'  THEN 3
        WHEN 'prose'   THEN 4
        WHEN 'usage'   THEN 5
        ELSE 6
    END,
    ex.idx;
"""

SQL_STEP7 = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.death_year ASC NULLS LAST;
"""

# Step 8 uses lemma for FTS, lemma_norm variants for exclusion
SQL_STEP8 = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH '{{headword headword_bare definitions_text}}:' || ?1
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 100
)
AND e.headword_norm NOT IN (?2, ?3)
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;
"""

# Step 4 uses dynamic excluded_ids
SQL_STEP4_TEMPLATE = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH ?1
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 50
)
AND e.id NOT IN ({{excluded_ids}})
ORDER BY d.source_type, d.name_en;
"""

# Step 5 uses dynamic excluded_ids
SQL_STEP5_TEMPLATE = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_translations_fts
    WHERE entries_translations_fts MATCH 'translation_en:' || ?1
    ORDER BY bm25(entries_translations_fts, 5.0, 3.0, 1.0)
    LIMIT 30
)
AND e.id NOT IN ({{excluded_ids}})
ORDER BY d.source_type, d.name_en;
"""

SQL_STEP9A = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = ?
  AND e.pos = ?
ORDER BY d.source_type, d.name_en;
"""

SQL_STEP9B = f"""
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.domain = ?
  AND e.headword_norm != ?
  AND d.source_type = 'arabterm'
ORDER BY d.name_en
LIMIT 30;
"""

SQL_DB_STATS = """
SELECT
    (SELECT COUNT(*) FROM entries) AS total_entries,
    (SELECT COUNT(*) FROM dictionaries) AS total_dictionaries;
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Database Layer
# ═══════════════════════════════════════════════════════════════════════════════

def _in_clause(n: int) -> str:
    """Generate ?,?,... for SQL IN clause with n parameters."""
    if n == 0:
        return "-1"  # impossible ID — NOT IN (-1) is always true
    return ",".join(["?"] * n)


def _row_to_entry(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row from a main entry query to a dict."""
    return {
        "entry_id": row["entry_id"],
        "dictionary_id": row["dictionary_id"],
        "headword": row["headword"],
        "headword_bare": row["headword_bare"],
        "headword_norm": row["headword_norm"],
        "root": row["root"],
        "root_source": row["root_source"],
        "pos": row["pos"],
        "form": row["form"],
        "is_partial": row["is_partial"],
        "definitions_text": row["definitions_text"],
        "translation_en": row["translation_en"],
        "translation_fr": row["translation_fr"],
        "domain": row["domain"],
        "external_id": row["external_id"],
        "dict_key": row["dict_key"],
        "dict_name_ar": row["dict_name_ar"],
        "dict_name_en": row["dict_name_en"],
        "dict_source_type": row["dict_source_type"],
        "dict_period": row["dict_period"],
        "dict_author": row["dict_author"],
        "dict_death_year": row["dict_death_year"],
        # Child tables — populated by enrich_entries()
        "definitions": [],
        "examples": [],
        "plurals": [],
        "derived_forms": [],
        "cross_refs": [],
        "provenance": None,
    }


class DictDB:
    """Read-only connection to arabic_dict.db with evidence collection queries."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA cache_size = -64000")
        self.conn.execute("PRAGMA mmap_size = 3000000000")

    def close(self):
        self.conn.close()

    def get_stats(self) -> dict:
        row = self.conn.execute(SQL_DB_STATS).fetchone()
        return {
            "total_entries": row["total_entries"],
            "total_dictionaries": row["total_dictionaries"],
        }

    def step1_headword(self, base: str, al_form: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP1, (base, al_form)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step2_definitions(self, base: str, al_form: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP2, (base, al_form)).fetchall()
        # Group by entry_id to build entries_with_senses
        entries: dict[int, dict] = {}
        for r in rows:
            eid = r["entry_id"]
            if eid not in entries:
                entries[eid] = {
                    "entry_id": eid,
                    "headword": r["headword"],
                    "dict_key": r["dict_key"],
                    "dict_name_en": r["dict_name_en"],
                    "dict_name_ar": r["dict_name_ar"],
                    "dict_source_type": r["dict_source_type"],
                    "dict_period": r["dict_period"],
                    "dict_death_year": r["dict_death_year"],
                    "dict_author": r["dict_author"],
                    "senses": [],
                }
            entries[eid]["senses"].append({
                "sense_index": r["sense_index"],
                "text": r["definition_text"],
                "is_raw": r["is_raw"],
            })
        return list(entries.values())

    def step3a_roots(self, base: str, al_form: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP3A, (base, al_form)).fetchall()
        return [{"root": r["root"], "root_source": r["root_source"],
                 "from_entry_id": r["from_entry_id"]} for r in rows]

    def step3b_root_family(self, root: str, excluded_ids: set[int]) -> list[dict]:
        excl = sorted(excluded_ids) if excluded_ids else []
        sql = SQL_STEP3B_TEMPLATE.replace("{excluded_ids}", _in_clause(len(excl)))
        rows = self.conn.execute(sql, (root, *excl)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step6_examples(self, base: str, al_form: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP6, (base, al_form)).fetchall()
        return [{
            "entry_id": r["entry_id"],
            "headword": r["headword"],
            "dict_key": r["dict_key"],
            "dict_name_en": r["dict_name_en"],
            "type": r["type"],
            "text": r["example_text"],
            "attribution": r["attribution"],
        } for r in rows]

    def step7_chronological(self, base: str, al_form: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP7, (base, al_form)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step8_reverse_lookup(self, lemma_bare: str, base: str, al_form: str) -> list[dict]:
        # Quote the term for FTS5 safety (handles dots, hyphens, etc.)
        safe_term = '"' + lemma_bare.replace('"', '""') + '"'
        rows = self.conn.execute(SQL_STEP8, (safe_term, base, al_form)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step4_fts_keyword(self, fts_expr: str, excluded_ids: set[int]) -> list[dict]:
        excl = sorted(excluded_ids) if excluded_ids else []
        sql = SQL_STEP4_TEMPLATE.replace("{excluded_ids}", _in_clause(len(excl)))
        rows = self.conn.execute(sql, (fts_expr, *excl)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step5_english_bridge(self, english_term: str, excluded_ids: set[int]) -> list[dict]:
        excl = sorted(excluded_ids) if excluded_ids else []
        sql = SQL_STEP5_TEMPLATE.replace("{excluded_ids}", _in_clause(len(excl)))
        # Quote the term for FTS5 safety (handles dots, hyphens, etc.)
        safe_term = '"' + english_term.replace('"', '""') + '"'
        rows = self.conn.execute(sql, (safe_term, *excl)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step9a_pos_filter(self, root: str, pos: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP9A, (root, pos)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def step9b_domain_filter(self, domain: str, headword_norm: str) -> list[dict]:
        rows = self.conn.execute(SQL_STEP9B, (domain, headword_norm)).fetchall()
        return [_row_to_entry(r) for r in rows]

    def enrich_entries(self, entries: list[dict]) -> None:
        """Batch-enrich entries with all 6 child tables."""
        if not entries:
            return
        ids = [e["entry_id"] for e in entries]
        ph = _in_clause(len(ids))
        by_id = {e["entry_id"]: e for e in entries}

        # Definitions
        rows = self.conn.execute(
            f"SELECT entry_id, sense_index, text, is_raw FROM definitions "
            f"WHERE entry_id IN ({ph}) ORDER BY entry_id, sense_index", ids
        ).fetchall()
        for r in rows:
            by_id[r["entry_id"]]["definitions"].append({
                "sense_index": r["sense_index"],
                "text": r["text"],
                "is_raw": r["is_raw"],
            })

        # Examples
        rows = self.conn.execute(
            f"SELECT entry_id, idx, type, text, attribution FROM examples "
            f"WHERE entry_id IN ({ph}) ORDER BY entry_id, idx", ids
        ).fetchall()
        for r in rows:
            by_id[r["entry_id"]]["examples"].append({
                "idx": r["idx"],
                "type": r["type"],
                "text": r["text"],
                "attribution": r["attribution"],
            })

        # Plurals
        rows = self.conn.execute(
            f"SELECT entry_id, idx, text FROM plurals "
            f"WHERE entry_id IN ({ph}) ORDER BY entry_id, idx", ids
        ).fetchall()
        for r in rows:
            by_id[r["entry_id"]]["plurals"].append({
                "idx": r["idx"],
                "text": r["text"],
            })

        # Derived forms
        rows = self.conn.execute(
            f"SELECT entry_id, idx, text FROM derived_forms "
            f"WHERE entry_id IN ({ph}) ORDER BY entry_id, idx", ids
        ).fetchall()
        for r in rows:
            by_id[r["entry_id"]]["derived_forms"].append({
                "idx": r["idx"],
                "text": r["text"],
            })

        # Cross refs
        rows = self.conn.execute(
            f"SELECT entry_id, idx, text FROM cross_refs "
            f"WHERE entry_id IN ({ph}) ORDER BY entry_id, idx", ids
        ).fetchall()
        for r in rows:
            by_id[r["entry_id"]]["cross_refs"].append({
                "idx": r["idx"],
                "text": r["text"],
            })

        # Provenance
        rows = self.conn.execute(
            f"SELECT entry_id, page_number, page_file, entry_index, volume, "
            f"hawramani_post_id, hawramani_slug, source_uri FROM provenance "
            f"WHERE entry_id IN ({ph})", ids
        ).fetchall()
        for r in rows:
            by_id[r["entry_id"]]["provenance"] = {
                "page_number": r["page_number"],
                "page_file": r["page_file"],
                "entry_index": r["entry_index"],
                "volume": r["volume"],
                "hawramani_post_id": r["hawramani_post_id"],
                "hawramani_slug": r["hawramani_slug"],
                "source_uri": r["source_uri"],
            }


# ═══════════════════════════════════════════════════════════════════════════════
# WordNet Bridge (AWN4 + OEWN via wn library)
# ═══════════════════════════════════════════════════════════════════════════════

class WNBridge:
    """Bridge to AWN4 and OEWN via the wn Python library."""

    def __init__(self):
        # Find AWN4 lexicon
        ar_lexicons = [l for l in wn.lexicons() if l.language == "arb"]
        if not ar_lexicons:
            print("Error: AWN4 not loaded in wn. Run:", file=sys.stderr)
            print("  python3 -c \"import wn; wn.add('path/to/awn4.xml')\"", file=sys.stderr)
            sys.exit(1)
        self._ar_spec = ar_lexicons[0].specifier()
        self._ar_wn = wn.Wordnet(self._ar_spec)

        # Find OEWN lexicon (optional)
        en_lexicons = [l for l in wn.lexicons() if l.language == "en"]
        if en_lexicons:
            self._en_spec = en_lexicons[0].specifier()
            self._en_wn = wn.Wordnet(self._en_spec)
        else:
            self._en_wn = None

    def get_synset_data(self, synset_id: str) -> dict:
        """Extract full synset data conforming to schema's synset section."""
        ss = self._ar_wn.synset(synset_id)
        lemmas = [w.lemma() for w in ss.words()]

        return {
            "id": ss.id,
            "ili": ss.ili or None,
            "pos": ss.pos,
            "lemmas": lemmas,
            "definition_ar": ss.definition() or "",
            "examples_ar": ss.examples() or [],
            "oewn": self._get_oewn_data(ss),
            "hypernym_chain": self._get_hypernym_chain(ss),
            "relations": self._get_relations(ss),
        }

    def _get_oewn_data(self, ss) -> Optional[dict]:
        if not self._en_wn or not ss.ili:
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

    def _get_hypernym_chain(self, ss) -> dict:
        """Build shortest hypernym chain to root.

        hypernym_paths() returns paths NOT including the synset itself —
        each path starts from the immediate hypernym up to the root.
        """
        paths = ss.hypernym_paths()
        if not paths:
            return {"depth": 0, "path": []}

        shortest = min(paths, key=len)
        chain = []
        for ancestor in shortest:
            oewn = self._get_oewn_for_synset(ancestor)
            chain.append({
                "id": ancestor.id,
                "lemmas": [w.lemma() for w in ancestor.words()],
                "definition_ar": ancestor.definition() or "",
                "oewn_definition_en": oewn["def"] if oewn else None,
                "oewn_lemmas_en": oewn["lemmas"] if oewn else None,
            })
        return {"depth": len(chain), "path": chain}

    def _get_relations(self, ss) -> list[dict]:
        result = []
        for rel_type, targets in ss.relations().items():
            for target in targets:
                oewn = self._get_oewn_for_synset(target)
                result.append({
                    "rel_type": rel_type,
                    "target_id": target.id,
                    "target_lemmas": [w.lemma() for w in target.words()],
                    "target_definition_ar": target.definition() or "",
                    "target_oewn_definition_en": oewn["def"] if oewn else None,
                    "target_oewn_lemmas_en": oewn["lemmas"] if oewn else None,
                })
        return result

    def _get_oewn_for_synset(self, ss) -> Optional[dict]:
        if not self._en_wn or not ss.ili:
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
# Evidence Collection Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

def collect_evidence(synset_id: str, db: DictDB, wn_bridge: WNBridge) -> dict:
    """Run all 9 steps and return a schema-conformant artifact dict."""

    # § _meta
    artifact = {
        "_meta": {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "db_path": db.db_path,
            "db_stats": db.get_stats(),
        },
    }

    # § synset
    synset_data = wn_bridge.get_synset_data(synset_id)
    artifact["synset"] = synset_data

    # § per_lemma (Steps 1, 2, 3, 6, 7, 8)
    all_entry_ids: set[int] = set()
    per_lemma: dict[str, dict] = {}

    for lemma in synset_data["lemmas"]:
        lemma_bare = strip_diacritics(lemma)
        lemma_norm = normalize_arabic(lemma)
        is_multiword = " " in lemma
        components = lemma.split() if is_multiword else []

        base, al_form = al_variants(lemma_norm)
        al_searched = [base, al_form]

        lemma_data: dict[str, Any] = {
            "identity": {
                "lemma": lemma,
                "lemma_bare": lemma_bare,
                "lemma_norm": lemma_norm,
                "is_multiword": is_multiword,
                "components": components,
            },
        }

        # ── Step 1: Exact Headword Lookup (ال-aware) ──────────────────
        entries_1 = db.step1_headword(base, al_form)
        db.enrich_entries(entries_1)

        step1_data: dict[str, Any] = {
            "al_variants_searched": al_searched,
            "sql_template": SQL_STEP1.strip(),
            "query_params": al_searched,
            "result_count": len(entries_1),
            "entries": entries_1,
            "by_component": None,
        }

        # Multi-word decomposition (with proclitic fallback)
        if is_multiword:
            by_component: dict[str, dict] = {}
            for word in components:
                word_norm = normalize_arabic(word)
                w_base, w_al = al_variants(word_norm)
                comp_entries = db.step1_headword(w_base, w_al)
                db.enrich_entries(comp_entries)

                comp_data: dict[str, Any] = {
                    "sql_template": SQL_STEP1.strip(),
                    "query_params": [w_base, w_al],
                    "result_count": len(comp_entries),
                    "entries": comp_entries,
                }

                # Fallback: strip proclitic+article prefix when standard search returns 0
                if not comp_entries:
                    stem = strip_proclitics(word_norm)
                    if stem is not None:
                        s_base, s_al = al_variants(stem)
                        stem_entries = db.step1_headword(s_base, s_al)
                        db.enrich_entries(stem_entries)
                        comp_data["proclitic_stripped"] = {
                            "original": word_norm,
                            "stem": stem,
                            "query_params": [s_base, s_al],
                            "result_count": len(stem_entries),
                            "entries": stem_entries,
                        }
                        comp_entries = stem_entries

                # Track component entry IDs for downstream deduplication
                all_entry_ids.update(e["entry_id"] for e in comp_entries)
                by_component[word] = comp_data
            step1_data["by_component"] = by_component

        lemma_data["step1_headword"] = step1_data
        all_entry_ids.update(e["entry_id"] for e in entries_1)

        # ── Step 2: Structured Definitions (ال-aware) ─────────────────
        entries_2 = db.step2_definitions(base, al_form)
        lemma_data["step2_definitions"] = {
            "sql_template": SQL_STEP2.strip(),
            "query_params": al_searched,
            "result_count": sum(len(e["senses"]) for e in entries_2),
            "entries_with_senses": entries_2,
        }

        # ── Step 3: Root Family (Enhanced) ────────────────────────────
        # 3a: Root inference from full phrase
        roots_found = db.step3a_roots(base, al_form)

        # 3a-fallback: Per-component root inference for multiword lemmas
        component_roots_used = False
        if is_multiword and not roots_found:
            seen_roots: set[str] = set()
            for word in components:
                word_norm = normalize_arabic(word)
                w_base, w_al = al_variants(word_norm)
                w_roots = db.step3a_roots(w_base, w_al)
                # Also try proclitic-stripped form
                if not w_roots:
                    stem = strip_proclitics(word_norm)
                    if stem is not None:
                        s_base, s_al = al_variants(stem)
                        w_roots = db.step3a_roots(s_base, s_al)
                for r in w_roots:
                    if r["root"] not in seen_roots:
                        seen_roots.add(r["root"])
                        r["from_component"] = word
                        roots_found.append(r)
            component_roots_used = bool(roots_found)

        step1_ids = {e["entry_id"] for e in entries_1}

        # 3b: Root family per root
        by_root: dict[str, dict] = {}
        for root_rec in roots_found:
            root_str = root_rec["root"]
            if root_str in by_root:
                continue  # already queried this root
            family = db.step3b_root_family(root_str, step1_ids)
            db.enrich_entries(family)

            excl_list = sorted(step1_ids)
            sql_built = SQL_STEP3B_TEMPLATE.replace(
                "{excluded_ids}", _in_clause(len(excl_list))
            ).strip()
            by_root[root_str] = {
                "sql_template": sql_built,
                "query_params": [root_str] + excl_list,
                "result_count": len(family),
                "entries": family,
            }
            all_entry_ids.update(e["entry_id"] for e in family)

        lemma_data["step3_root_family"] = {
            "roots_found": roots_found,
            "roots_from_components": component_roots_used,
            "by_root": by_root,
        }

        # ── Step 6: Examples (ال-aware) ───────────────────────────────
        examples_6 = db.step6_examples(base, al_form)
        lemma_data["step6_examples"] = {
            "sql_template": SQL_STEP6.strip(),
            "query_params": al_searched,
            "result_count": len(examples_6),
            "examples": examples_6,
        }

        # ── Step 7: Chronological Ordering (ال-aware) ─────────────────
        entries_7 = db.step7_chronological(base, al_form)
        db.enrich_entries(entries_7)
        lemma_data["step7_chronological"] = {
            "sql_template": SQL_STEP7.strip(),
            "query_params": al_searched,
            "result_count": len(entries_7),
            "entries": entries_7,
        }

        # ── Step 8: Reverse Lookup (Enhanced FTS) ─────────────────────
        entries_8 = db.step8_reverse_lookup(lemma_bare, base, al_form)
        db.enrich_entries(entries_8)
        lemma_data["step8_reverse_lookup"] = {
            "sql_template": SQL_STEP8.strip(),
            "query_params": [lemma_bare, base, al_form],
            "result_count": len(entries_8),
            "entries": entries_8,
        }
        all_entry_ids.update(e["entry_id"] for e in entries_8)

        per_lemma[lemma] = lemma_data

    artifact["per_lemma"] = per_lemma

    # § per_synset (Steps 4, 5, 9)
    per_synset: dict[str, Any] = {}

    # ── Step 4: FTS Keyword Search ────────────────────────────────────
    keywords = extract_keywords(synset_data["definition_ar"])
    if keywords:
        fts_expr = " OR ".join(f'"{kw}"' for kw in keywords)
        entries_4 = db.step4_fts_keyword(fts_expr, all_entry_ids)
        db.enrich_entries(entries_4)
        excl_sorted = sorted(all_entry_ids)
        sql_built = SQL_STEP4_TEMPLATE.replace(
            "{excluded_ids}", _in_clause(len(excl_sorted))
        ).strip()
        per_synset["step4_fts_keyword"] = {
            "keywords_extracted": keywords,
            "sql_template": sql_built,
            "query_params": [fts_expr] + excl_sorted,
            "excluded_entry_ids": excl_sorted,
            "result_count": len(entries_4),
            "entries": entries_4,
        }
        all_entry_ids.update(e["entry_id"] for e in entries_4)
    else:
        per_synset["step4_fts_keyword"] = {
            "keywords_extracted": [],
            "sql_template": SQL_STEP4_TEMPLATE.strip(),
            "query_params": [],
            "excluded_entry_ids": sorted(all_entry_ids),
            "result_count": 0,
            "entries": [],
        }

    # ── Step 5: English Bridge (ARABTERM) ─────────────────────────────
    oewn = synset_data.get("oewn")
    if oewn and oewn.get("lemmas_en"):
        all_entries_5: list[dict] = []
        english_terms = oewn["lemmas_en"]
        for en_term in english_terms:
            entries_5 = db.step5_english_bridge(en_term, all_entry_ids)
            all_entries_5.extend(entries_5)
        # Deduplicate by entry_id
        seen_5: set[int] = set()
        deduped_5: list[dict] = []
        for e in all_entries_5:
            if e["entry_id"] not in seen_5:
                seen_5.add(e["entry_id"])
                deduped_5.append(e)
        db.enrich_entries(deduped_5)

        excl_sorted = sorted(all_entry_ids)
        sql_built = SQL_STEP5_TEMPLATE.replace(
            "{excluded_ids}", _in_clause(len(excl_sorted))
        ).strip()
        per_synset["step5_english_bridge"] = {
            "english_terms_used": english_terms,
            "sql_template": sql_built,
            "query_params": english_terms + excl_sorted,
            "excluded_entry_ids": excl_sorted,
            "result_count": len(deduped_5),
            "entries": deduped_5,
        }
        all_entry_ids.update(e["entry_id"] for e in deduped_5)
    else:
        per_synset["step5_english_bridge"] = {
            "english_terms_used": [],
            "sql_template": SQL_STEP5_TEMPLATE.strip(),
            "query_params": [],
            "excluded_entry_ids": sorted(all_entry_ids),
            "result_count": 0,
            "entries": [],
        }

    # ── Step 9: Specialized Filtering ─────────────────────────────────
    filters_applied: list[dict] = []

    # 9a: POS filtering — if any root was found and synset has a POS
    all_roots = set()
    for ld in per_lemma.values():
        for rf in ld["step3_root_family"]["roots_found"]:
            all_roots.add(rf["root"])

    synset_pos = synset_data["pos"]
    pos_map = {"n": "noun", "v": "verb", "a": "adj", "r": "adv"}
    db_pos = pos_map.get(synset_pos)

    if db_pos and all_roots:
        for root_str in all_roots:
            entries_9a = db.step9a_pos_filter(root_str, db_pos)
            db.enrich_entries(entries_9a)
            filters_applied.append({
                "filter_type": "pos",
                "description": f"Root '{root_str}' filtered by POS '{db_pos}'",
                "sql_template": SQL_STEP9A.strip(),
                "query_params": [root_str, db_pos],
                "result_count": len(entries_9a),
                "entries": entries_9a,
            })

    # 9b: Domain filtering — if any ARABTERM entry had a domain
    domains_seen: set[str] = set()
    for ld in per_lemma.values():
        for e in ld["step1_headword"]["entries"]:
            if e.get("domain") and e["dict_source_type"] == "arabterm":
                domains_seen.add(e["domain"])

    for domain in domains_seen:
        # Use first lemma's norm for exclusion
        first_lemma = synset_data["lemmas"][0]
        hn = normalize_arabic(first_lemma)
        entries_9b = db.step9b_domain_filter(domain, hn)
        db.enrich_entries(entries_9b)
        filters_applied.append({
            "filter_type": "domain",
            "description": f"Domain '{domain}' from ARABTERM",
            "sql_template": SQL_STEP9B.strip(),
            "query_params": [domain, hn],
            "result_count": len(entries_9b),
            "entries": entries_9b,
        })

    per_synset["step9_specialized"] = {
        "filters_applied": filters_applied,
    }

    artifact["per_synset"] = per_synset

    return artifact


# ═══════════════════════════════════════════════════════════════════════════════
# YAML Output
# ═══════════════════════════════════════════════════════════════════════════════

class _ArabicDumper(yaml.Dumper):
    """Custom YAML dumper that handles Arabic text cleanly."""
    pass


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Use literal block style for multi-line strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_ArabicDumper.add_representer(str, _str_representer)


def write_artifact(artifact: dict, output_path: Path) -> None:
    """Write evidence artifact as YAML."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            artifact,
            f,
            Dumper=_ArabicDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="جمع الشواهد المعجمية — Collect dictionary evidence for AWN4 synsets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s awn4-05162506-n
  %(prog)s --batch batches/my_batch.txt
  %(prog)s awn4-05162506-n awn4-03466051-n --output-dir output/evidence
""",
    )
    parser.add_argument("synset_ids", nargs="*", help="Synset IDs (e.g., awn4-05162506-n)")
    parser.add_argument("--batch", metavar="FILE", help="Read synset IDs from file (one per line)")
    parser.add_argument("--output-dir", default="output/evidence",
                        help="Output directory (default: output/evidence)")
    parser.add_argument("--db", default="data/arabic_dict.db",
                        help="Path to arabic_dict.db (default: data/arabic_dict.db)")

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
                # Handle YAML compact format from extract_synset_wn.py --compact
                m = re.search(r'synset_id:\s*(awn4-\S+)', line)
                if m:
                    target_ids.append(m.group(1))
                    continue
                # Plain text: first token is synset ID (must look like awn4-...)
                token = line.split()[0].lstrip("-").strip()
                if token.startswith("awn4-"):
                    target_ids.append(token)

    if not target_ids:
        parser.print_help()
        sys.exit(1)

    # Resolve paths relative to linguist_workspace/
    workspace = Path(__file__).resolve().parent.parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = workspace / args.db
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = workspace / args.output_dir

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        print("Run ./setup.sh first.", file=sys.stderr)
        sys.exit(1)

    # Initialize
    db = DictDB(str(db_path))
    wn_bridge = WNBridge()

    success = 0
    errors = 0

    for i, sid in enumerate(target_ids, 1):
        print(f"[{i}/{len(target_ids)}] {sid}...", end=" ", file=sys.stderr, flush=True)
        try:
            artifact = collect_evidence(sid, db, wn_bridge)
            output_path = output_dir / f"{sid}.evidence.yaml"
            write_artifact(artifact, output_path)

            # Summary stats
            n_lemmas = len(artifact["per_lemma"])
            total_entries = sum(
                ld["step1_headword"]["result_count"]
                for ld in artifact["per_lemma"].values()
            )
            print(f"{n_lemmas} lemmas, {total_entries} headword entries -> {output_path.name}",
                  file=sys.stderr)
            success += 1
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            errors += 1

    db.close()
    print(f"\nDone. {success} succeeded, {errors} failed.", file=sys.stderr)
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
