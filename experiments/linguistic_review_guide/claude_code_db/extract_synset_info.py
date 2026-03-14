#!/usr/bin/env python3
"""Extract synset_info + masked variant + pre-fetched evidence for Claude Code DB-direct review.

Produces lightweight prepared/{synset_id}/ directories containing:
  - synset_info.yaml       (full synset metadata with lemmas)
  - synset_info_masked.yaml (lemmas removed — for Step 0.5)
  - evidence.json           (pre-fetched DB evidence: headword, enrichment, English bridge)

The evidence.json pre-fetch replaces 3 of the 5 DB queries the reviewer agent would
otherwise run at review time, saving ~3 tool-call round-trips per synset.

Usage:
    python3 extract_synset_info.py awn4-02592253-n               # single synset
    python3 extract_synset_info.py awn4-02592253-n awn4-03070134-n  # multiple
    python3 extract_synset_info.py --batch synset_list.txt        # from file
    python3 extract_synset_info.py --all                          # all AWN4 synsets
    python3 extract_synset_info.py --all --pos n                  # all nouns
    python3 extract_synset_info.py --batch list.txt --db /path/to/arabic_dict.db

Requirements:
    pip install wn pyyaml
    wn database must contain awn4 and oewn:2024.
    Arabic dictionary DB required for --db (evidence pre-fetching).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import wn
except ImportError:
    print("Error: wn package not installed. Run: pip install wn", file=sys.stderr)
    sys.exit(1)

import yaml


# ── YAML Dumper (preserves Arabic text, uses block style for multiline) ──

class ArabicDumper(yaml.Dumper):
    pass


def _str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


ArabicDumper.add_representer(str, _str_representer)


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data, Dumper=ArabicDumper, allow_unicode=True,
        default_flow_style=False, sort_keys=False, width=200,
    )


# ── Arabic Text Normalization (matches headword_norm in DB) ──

_DIACRITIC_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]")
_TATWEEL = "\u0640"
_ALEF_FORMS = {"\u0622", "\u0623", "\u0625"}  # آ أ إ → ا
_ALEF_PLAIN = "\u0627"  # ا
_YA_DOTLESS = "\u0649"  # ى → ي
_YA_DOTTED = "\u064A"  # ي


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text to match headword_norm in the DB."""
    text = _DIACRITIC_RE.sub("", text)
    text = text.replace(_TATWEEL, "")
    for af in _ALEF_FORMS:
        text = text.replace(af, _ALEF_PLAIN)
    text = text.replace(_YA_DOTLESS, _YA_DOTTED)
    return text.strip()


# ── Evidence Pre-fetcher ──

class EvidencePrefetcher:
    """Pre-fetches deterministic DB evidence (headword + enrichment + English bridge)."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self):
        self._conn.close()

    def prefetch(self, synset_data: dict) -> Optional[dict]:
        """Run Q1 (headword) + Q2 (enrichment) + Q3 (English bridge).

        Returns dict with pre-fetched evidence, or None if no queries possible.
        """
        lemmas_ar = synset_data.get("lemmas", [])
        oewn = synset_data.get("oewn") or {}
        lemmas_en = oewn.get("lemmas_en", [])

        if not lemmas_ar:
            return None

        # Build headword lookup terms: each lemma + ال-prefixed form
        lemma_terms = set()
        for lemma in lemmas_ar:
            norm = normalize_arabic(lemma)
            if not norm:
                continue
            lemma_terms.add(norm)
            # Add definite article form if not already present
            if not norm.startswith("ال"):
                lemma_terms.add("ال" + norm)

        if not lemma_terms:
            return None

        # Q1: Batch headword lookup
        placeholders = ",".join("?" for _ in lemma_terms)
        q1_sql = f"""
            SELECT e.id AS entry_id, e.headword, e.headword_norm,
                   e.root, e.root_source, e.pos,
                   e.definitions_text, e.translation_en, e.domain,
                   d.name_ar, d.name_en, d.source_type, d.period, d.death_year
            FROM entries e
            JOIN dictionaries d ON e.dictionary_id = d.id
            WHERE e.headword_norm IN ({placeholders})
            ORDER BY e.headword_norm, d.source_type,
                     d.death_year ASC NULLS LAST, d.name_ar
        """
        cursor = self._conn.execute(q1_sql, list(lemma_terms))
        headword_entries = [dict(row) for row in cursor.fetchall()]

        # Q2: Enrichment by entry_id (definitions + examples + plurals)
        entry_ids = [e["entry_id"] for e in headword_entries]
        enrichment = []
        if entry_ids:
            id_placeholders = ",".join("?" for _ in entry_ids)
            q2_sql = f"""
                SELECT 'def' AS _table, entry_id, sense_index AS idx,
                       text, NULL AS type, NULL AS attribution
                FROM definitions WHERE entry_id IN ({id_placeholders})
                UNION ALL
                SELECT 'ex' AS _table, entry_id, idx,
                       text, type, attribution
                FROM examples WHERE entry_id IN ({id_placeholders})
                UNION ALL
                SELECT 'pl' AS _table, entry_id, idx,
                       text, NULL, NULL
                FROM plurals WHERE entry_id IN ({id_placeholders})
                ORDER BY entry_id, _table, idx
            """
            cursor = self._conn.execute(q2_sql, entry_ids * 3)
            enrichment = [dict(row) for row in cursor.fetchall()]

        # Q3: English bridge FTS
        english_bridge = []
        if lemmas_en:
            # Build FTS MATCH expression: translation_en:"word1" OR translation_en:"word2"
            match_terms = []
            for en_lemma in lemmas_en:
                # Escape double quotes in lemma
                safe = en_lemma.replace('"', '""')
                match_terms.append(f'translation_en:"{safe}"')
            match_expr = " OR ".join(match_terms)

            q3_sql = """
                SELECT e.id AS entry_id, e.headword, e.headword_norm,
                       e.root, e.root_source, e.pos,
                       e.definitions_text, e.translation_en, e.domain,
                       d.name_ar, d.name_en, d.source_type, d.period
                FROM entries e
                JOIN dictionaries d ON e.dictionary_id = d.id
                WHERE e.id IN (
                    SELECT rowid FROM entries_translations_fts
                    WHERE entries_translations_fts MATCH ?
                    ORDER BY bm25(entries_translations_fts, 5.0, 3.0, 1.0)
                    LIMIT 50
                )
                ORDER BY d.source_type, d.name_ar
            """
            try:
                cursor = self._conn.execute(q3_sql, [match_expr])
                english_bridge = [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                # FTS query may fail on unusual terms; degrade gracefully
                english_bridge = []

        return {
            "headword_entries": headword_entries,
            "enrichment": enrichment,
            "english_bridge": english_bridge,
            "query_meta": {
                "lemma_terms": sorted(lemma_terms),
                "english_terms": lemmas_en,
                "entry_ids": entry_ids,
                "headword_count": len(headword_entries),
                "enrichment_count": len(enrichment),
                "bridge_count": len(english_bridge),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


# ── WordNet Bridge ──

class WNBridge:
    """Bridge to AWN4 and OEWN via the wn Python library."""

    def __init__(self):
        ar_lexicons = [l for l in wn.lexicons() if l.language == "arb"]
        if not ar_lexicons:
            print("Error: AWN4 not loaded in wn. Run:", file=sys.stderr)
            print('  python3 -c "import wn; wn.add(\'path/to/awn4.xml\')"', file=sys.stderr)
            sys.exit(1)
        self._ar_spec = ar_lexicons[0].specifier()
        self._ar_wn = wn.Wordnet(self._ar_spec)

        en_lexicons = [l for l in wn.lexicons() if l.language == "en"]
        if en_lexicons:
            self._en_spec = en_lexicons[0].specifier()
            self._en_wn = wn.Wordnet(self._en_spec)
        else:
            self._en_wn = None

    def get_synset_data(self, synset_id: str) -> dict:
        """Extract synset data for synset_info generation."""
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

    def all_synset_ids(self, pos: Optional[str] = None) -> list[str]:
        """List all synset IDs in AWN4, optionally filtered by POS."""
        synsets = self._ar_wn.synsets()
        if pos:
            synsets = [s for s in synsets if s.pos == pos]
        return [s.id for s in synsets]

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


# ── Synset Info Extraction ──

def extract_synset_info(synset_data: dict) -> str:
    """Format synset data as readable YAML block (with lemmas)."""
    info = {
        "id": synset_data.get("id", ""),
        "ili": synset_data.get("ili", ""),
        "pos": synset_data.get("pos", ""),
        "lemmas": synset_data.get("lemmas", []),
        "definition_ar": synset_data.get("definition_ar", ""),
    }
    oewn = synset_data.get("oewn", {})
    if oewn:
        info["definition_en"] = oewn.get("definition_en", "")
        info["lemmas_en"] = oewn.get("lemmas_en", [])
    chain = synset_data.get("hypernym_chain", {})
    if chain and chain.get("path"):
        parent = chain["path"][0]
        info["direct_hypernym"] = {
            "id": parent.get("id", ""),
            "lemmas": parent.get("lemmas", []),
            "definition_ar": parent.get("definition_ar", ""),
        }
    return dump_yaml(info)


def mask_synset_info(synset_info_yaml: str) -> str:
    """Remove lemma lists for unbiased lemma generation (Step 0.5)."""
    data = yaml.safe_load(synset_info_yaml)
    if not isinstance(data, dict):
        return synset_info_yaml
    data.pop("lemmas", None)
    data.pop("lemmas_en", None)
    hyp = data.get("direct_hypernym", {})
    if isinstance(hyp, dict):
        hyp.pop("lemmas", None)
    return yaml.dump(data, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=200)


# ── Processing ──

def process_one(synset_id: str, wn_bridge: WNBridge, output_dir: Path,
                prefetcher: Optional[EvidencePrefetcher] = None,
                force: bool = False) -> dict:
    """Process a single synset. Returns stats dict."""
    out_dir = output_dir / synset_id
    yaml_exists = (out_dir / "synset_info.yaml").exists()
    evidence_exists = (out_dir / "evidence.json").exists()

    # Skip if all outputs exist (unless forced)
    if not force and yaml_exists and (evidence_exists or prefetcher is None):
        return {"synset_id": synset_id, "status": "skip"}

    try:
        synset_data = wn_bridge.get_synset_data(synset_id)
    except Exception as e:
        return {"synset_id": synset_id, "status": "fail", "error": str(e)}

    out_dir.mkdir(parents=True, exist_ok=True)

    # Write YAML files (skip if already exist and not forced)
    if force or not yaml_exists:
        synset_info = extract_synset_info(synset_data)
        synset_info_masked = mask_synset_info(synset_info)
        (out_dir / "synset_info.yaml").write_text(synset_info, encoding="utf-8")
        (out_dir / "synset_info_masked.yaml").write_text(synset_info_masked, encoding="utf-8")

    # Pre-fetch evidence (skip if already exists and not forced)
    evidence_count = 0
    if prefetcher and (force or not evidence_exists):
        try:
            evidence = prefetcher.prefetch(synset_data)
            if evidence:
                (out_dir / "evidence.json").write_text(
                    json.dumps(evidence, ensure_ascii=False, indent=1),
                    encoding="utf-8",
                )
                evidence_count = evidence["query_meta"]["headword_count"]
        except Exception as e:
            # Evidence prefetch failure is non-fatal; agent can still query DB
            print(f"  WARN: evidence prefetch failed for {synset_id}: {e}", file=sys.stderr)

    return {
        "synset_id": synset_id,
        "status": "ok",
        "lemma_count": len(synset_data.get("lemmas", [])),
        "evidence_entries": evidence_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "synsets", nargs="*",
        help="Synset ID(s) to process (e.g., awn4-02592253-n)",
    )
    parser.add_argument(
        "--batch", type=Path, default=None,
        help="File containing synset IDs (one per line)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Process all AWN4 synsets",
    )
    parser.add_argument(
        "--pos", type=str, default=None,
        help="Filter by POS when using --all (e.g., n, v, a, r)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).resolve().parent / "prepared",
        help="Output directory for prepared files",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="Path to arabic_dict.db for evidence pre-fetching",
    )
    parser.add_argument(
        "--no-prefetch", action="store_true",
        help="Disable evidence pre-fetching (YAML only)",
    )
    args = parser.parse_args()

    # Auto-detect DB path if not specified
    if args.db is None and not args.no_prefetch:
        default_db = Path(__file__).resolve().parent.parent.parent.parent / "arabic-dictionaries" / "db" / "arabic_dict.db"
        if default_db.exists():
            args.db = default_db

    # Initialize WN bridge
    print("Initializing WordNet bridge...")
    wn_bridge = WNBridge()

    # Initialize evidence prefetcher
    prefetcher = None
    if args.db and not args.no_prefetch:
        if args.db.exists():
            prefetcher = EvidencePrefetcher(str(args.db))
            print(f"Evidence DB: {args.db}")
        else:
            print(f"Warning: DB not found at {args.db}, skipping evidence prefetch", file=sys.stderr)

    # Collect synset IDs
    synset_ids = []
    if args.all:
        synset_ids = wn_bridge.all_synset_ids(pos=args.pos)
    elif args.batch:
        synset_ids = [
            line.strip() for line in args.batch.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    elif args.synsets:
        synset_ids = args.synsets
    else:
        parser.print_help()
        sys.exit(1)

    output_dir = args.output_dir
    print(f"Output dir:  {output_dir}")
    print(f"Synsets:     {len(synset_ids)}")
    print()

    ok = skip = fail = 0
    total_evidence = 0
    t0 = time.time()

    for i, sid in enumerate(synset_ids, 1):
        result = process_one(sid, wn_bridge, output_dir,
                             prefetcher=prefetcher, force=args.force)
        if result["status"] == "skip":
            skip += 1
        elif result["status"] == "ok":
            ok += 1
            ev = result.get("evidence_entries", 0)
            total_evidence += ev
            if i <= 5 or i % 1000 == 0:
                ev_str = f", {ev} evidence" if prefetcher else ""
                print(f"[{i}/{len(synset_ids)}] OK: {sid} ({result['lemma_count']} lemmas{ev_str})")
        else:
            fail += 1
            print(f"[{i}/{len(synset_ids)}] FAIL: {sid}: {result.get('error', '?')}")

        if i % 1000 == 0 and i > 5:
            elapsed = time.time() - t0
            rate = i / elapsed
            print(f"  Progress: {i}/{len(synset_ids)} ({rate:.0f}/s)")

    if prefetcher:
        prefetcher.close()

    elapsed = time.time() - t0
    ev_str = f", {total_evidence} evidence entries" if prefetcher else ""
    print(f"\nDone in {elapsed:.1f}s: {ok} ok, {skip} skipped, {fail} failed{ev_str}")


if __name__ == "__main__":
    main()
