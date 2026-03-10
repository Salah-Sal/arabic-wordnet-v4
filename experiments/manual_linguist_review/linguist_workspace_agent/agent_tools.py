"""
tools.py — Host-side tool functions for the RLM evidence collection agent.

Each tool wraps DictDB/WNBridge methods from collect_evidence.py and returns
dict/list types that the RLM sandbox receives as real Python objects via
the JSON-RPC bridge.

Usage:
    from tools import build_tools
    tools = build_tools(db, wn_bridge)
    # Pass to dspy.RLM(tools=tools)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

# Import from existing automated pipeline
_PIPELINE_DIR = str(Path(__file__).resolve().parent.parent / "linguist_workspace" / "tools")
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from collect_evidence import (
    DictDB,
    WNBridge,
    strip_diacritics,
    normalize_arabic,
    al_variants,
    extract_keywords,
)


def build_tools(db: DictDB, wn_bridge: WNBridge) -> dict[str, Callable]:
    """Build tool dict with closures over db and wn_bridge.

    Returns a dict of {tool_name: callable} suitable for dspy.RLM(tools=...).
    """

    def lookup_headword(lemma: str) -> dict:
        """Look up dictionary entries by exact headword match (al-aware). Handles multiword lemmas by also searching each component."""
        lemma_norm = normalize_arabic(strip_diacritics(lemma))
        base, al_form = al_variants(lemma_norm)
        entries = db.step1_headword(base, al_form)
        db.enrich_entries(entries)

        result = {
            "al_variants_searched": [base, al_form],
            "result_count": len(entries),
            "entries": entries,
        }

        # Handle multiword lemmas
        if " " in lemma:
            by_component = {}
            for word in lemma.split():
                w_norm = normalize_arabic(strip_diacritics(word))
                w_base, w_al = al_variants(w_norm)
                comp_entries = db.step1_headword(w_base, w_al)
                db.enrich_entries(comp_entries)
                by_component[word] = {
                    "al_variants_searched": [w_base, w_al],
                    "result_count": len(comp_entries),
                    "entries": comp_entries,
                }
            result["by_component"] = by_component

        return result

    def lookup_definitions(lemma: str) -> dict:
        """Get structured per-sense definitions for a lemma (al-aware). Returns entries grouped by dictionary with sense breakdowns."""
        lemma_norm = normalize_arabic(strip_diacritics(lemma))
        base, al_form = al_variants(lemma_norm)
        entries_with_senses = db.step2_definitions(base, al_form)

        return {
            "result_count": len(entries_with_senses),
            "entries_with_senses": entries_with_senses,
        }

    def lookup_root_family(lemma: str, excluded_ids: str = "[]") -> dict:
        """Infer roots for a lemma, then fetch all root-family entries. excluded_ids is a JSON array of entry IDs to skip."""
        lemma_norm = normalize_arabic(strip_diacritics(lemma))
        base, al_form = al_variants(lemma_norm)

        # Step 3a: root inference
        roots_found = db.step3a_roots(base, al_form)

        # Parse excluded IDs
        try:
            excl = set(json.loads(excluded_ids))
        except (json.JSONDecodeError, TypeError):
            excl = set()

        # Step 3b: family lookup per root
        by_root = {}
        for root_info in roots_found:
            root = root_info["root"]
            if root in by_root:
                continue
            family_entries = db.step3b_root_family(root, excl)
            db.enrich_entries(family_entries)
            by_root[root] = {
                "root_source": root_info["root_source"],
                "from_entry_id": root_info["from_entry_id"],
                "result_count": len(family_entries),
                "entries": family_entries,
            }

        return {
            "roots_found": roots_found,
            "by_root": by_root,
        }

    def lookup_examples(lemma: str) -> dict:
        """Get usage examples for a lemma (al-aware), ordered by type: Quran > Hadith > Poetry > Prose > Usage."""
        lemma_norm = normalize_arabic(strip_diacritics(lemma))
        base, al_form = al_variants(lemma_norm)
        examples = db.step6_examples(base, al_form)

        return {
            "result_count": len(examples),
            "examples": examples,
        }

    def fts_search(query: str, search_type: str, excluded_ids: str = "[]") -> dict:
        """Full-text search. search_type='arabic' searches entries_fts, 'english' searches translations_fts. excluded_ids is a JSON array of entry IDs to skip."""
        try:
            excl = set(json.loads(excluded_ids))
        except (json.JSONDecodeError, TypeError):
            excl = set()

        if search_type == "english":
            entries = db.step5_english_bridge(query, excl)
        else:
            entries = db.step4_fts_keyword(query, excl)
        db.enrich_entries(entries)

        return {
            "search_type": search_type,
            "query": query,
            "result_count": len(entries),
            "entries": entries,
        }

    def reverse_lookup(lemma: str) -> dict:
        """Find entries that mention this lemma in their headword/definitions text but have a different headword. Uses FTS reverse search."""
        lemma_bare = strip_diacritics(lemma)
        lemma_norm = normalize_arabic(lemma)
        base, al_form = al_variants(lemma_norm)
        entries = db.step8_reverse_lookup(lemma_bare, base, al_form)
        db.enrich_entries(entries)

        return {
            "result_count": len(entries),
            "entries": entries,
        }

    def get_synset_info(synset_id: str) -> dict:
        """Get full synset data from AWN4: lemmas, Arabic/English definitions, hypernym chain, relations."""
        return wn_bridge.get_synset_data(synset_id)

    def normalize_lemma(lemma: str) -> dict:
        """Normalize an Arabic lemma: strip diacritics, normalize alef/hamza/ya, compute al-variants and multiword info."""
        bare = strip_diacritics(lemma)
        norm = normalize_arabic(lemma)
        base, al_form = al_variants(norm)
        is_multiword = " " in lemma
        components = lemma.split() if is_multiword else []

        return {
            "lemma": lemma,
            "bare": bare,
            "norm": norm,
            "base": base,
            "al_form": al_form,
            "is_multiword": is_multiword,
            "components": components,
        }

    def extract_arabic_keywords(text: str) -> list:
        """Extract Arabic keywords from text, removing stopwords and short tokens. Useful for building FTS queries."""
        return extract_keywords(text)

    def get_db_stats() -> dict:
        """Return database statistics: total entries and total dictionaries."""
        return db.get_stats()

    return {
        "lookup_headword": lookup_headword,
        "lookup_definitions": lookup_definitions,
        "lookup_root_family": lookup_root_family,
        "lookup_examples": lookup_examples,
        "fts_search": fts_search,
        "reverse_lookup": reverse_lookup,
        "get_synset_info": get_synset_info,
        "normalize_lemma": normalize_lemma,
        "extract_arabic_keywords": extract_arabic_keywords,
        "get_db_stats": get_db_stats,
    }
