#!/usr/bin/env python3
"""Shared query construction and synset selection for retrieval evaluation.

Provides reusable functions for loading ground-truth evidence, selecting
test synsets, and building query variants — independent of any retrieval backend.
"""
from __future__ import annotations

import json
import random
import yaml
from pathlib import Path

_LOCAL_PREPARED = Path(__file__).resolve().parent / "prepared"
_PROJECT_PREPARED = (Path(__file__).resolve().parent.parent
                     / "linguistic_review_guide" / "claude_code_db" / "prepared")
PREPARED_DIR = _LOCAL_PREPARED if _LOCAL_PREPARED.is_dir() else _PROJECT_PREPARED


def load_manifest(export_dir: Path) -> tuple[dict, dict]:
    """Load manifest and reverse index (entry_id -> headword_norm)."""
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    reverse = json.loads((export_dir / "entry_id_to_headword.json").read_text(encoding="utf-8"))
    return manifest, reverse


def load_synset_data(synset_dir: Path) -> dict | None:
    """Load evidence.json and synset_info.yaml for a synset."""
    evidence_path = synset_dir / "evidence.json"
    info_path = synset_dir / "synset_info.yaml"

    if not evidence_path.exists() or not info_path.exists():
        return None

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    info = yaml.safe_load(info_path.read_text(encoding="utf-8"))

    return {"evidence": evidence, "info": info, "synset_id": synset_dir.name}


def select_test_synsets(prepared_dir: Path, num: int,
                        offset: int = 0) -> list[dict]:
    """Select synsets that have evidence.json, stratified across levels."""
    candidates = []
    for synset_dir in sorted(prepared_dir.iterdir()):
        if not synset_dir.is_dir():
            continue
        data = load_synset_data(synset_dir)
        if data and data["evidence"].get("headword_entries"):
            candidates.append(data)

    random.seed(42)
    random.shuffle(candidates)
    return candidates[offset:offset + num]


def build_queries(synset_data: dict) -> list[dict]:
    """Build query variants from synset data.

    Returns up to 3 query types:
      - arabic_lemma: space-joined Arabic lemma terms
      - english_bridge: space-joined English translation terms
      - definition_keyword: full Arabic definition verbatim
    """
    evidence = synset_data["evidence"]
    info = synset_data["info"]
    queries = []

    # Query A: Arabic lemma query
    lemma_terms = evidence.get("query_meta", {}).get("lemma_terms", [])
    if lemma_terms:
        bare_terms = [t for t in lemma_terms if not t.startswith("\u0627\u0644")]
        if not bare_terms:
            bare_terms = lemma_terms
        queries.append({
            "type": "arabic_lemma",
            "query": " ".join(bare_terms),
            "ground_truth_entry_ids": [
                e["entry_id"] for e in evidence.get("headword_entries", [])
            ],
        })

    # Query B: English bridge query
    english_terms = evidence.get("query_meta", {}).get("english_terms", [])
    if english_terms:
        queries.append({
            "type": "english_bridge",
            "query": " ".join(english_terms),
            "ground_truth_entry_ids": [
                e["entry_id"] for e in evidence.get("english_bridge", [])
            ],
        })

    # Query C: Definition keyword query
    ar_def = info.get("definition_ar", "")
    if ar_def:
        queries.append({
            "type": "definition_keyword",
            "query": ar_def,
            "ground_truth_entry_ids": list(set(
                [e["entry_id"] for e in evidence.get("headword_entries", [])] +
                [e["entry_id"] for e in evidence.get("english_bridge", [])]
            )),
        })

    return queries
