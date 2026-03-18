#!/usr/bin/env python3
"""Build finetuning dataset for Jina v5 embeddings from trajectories + reviews.

Combines up to three data sources:
  - Trajectory SQL results (what was retrieved): sql_query_dataset_backfilled.jsonl
  - Review YAML decisions (what was relevant): *.review.yaml
  - Pre-fetched evidence.json (headword entries when no trajectory available)

When --trajectory is omitted, builds headword entries solely from evidence.json
in the prepared directory. This enables dataset generation from review sources
(e.g. Gemini reviews) that lack structured trajectory records.

Produces (query, hard_positive, hard_negative) triplets where:
  - Query = synset lemmas + Arabic definition (combined)
  - Hard positive = dictionary entry for a confirmed lemma
  - Hard negative = dictionary entry for a removed lemma (plausible but wrong)

Usage:
    python build_finetuning_data.py                          # full extraction
    python build_finetuning_data.py --synset awn4-00001740-n # single synset (debug)
    python build_finetuning_data.py --verbose                # debug output
    python build_finetuning_data.py --include-soft-negatives # add FTS-retrieved non-matches
    python build_finetuning_data.py --eval-only \\
        --review-dir .../reviews_gemini_db                   # eval-only from Gemini reviews
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ── Diacritics stripping ────────────────────────────────────────────────────

# Arabic combining marks (tashkeel / harakat)
_DIACRITICS_RE = re.compile(
    "[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4"
    "\u06E7\u06E8\u06EA-\u06ED\u08D3-\u08FF]"
)


def strip_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) from text."""
    return _DIACRITICS_RE.sub("", text)


def normalize_for_match(text: str) -> str:
    """Normalize Arabic text for lemma → headword_norm matching.

    Strips diacritics, normalizes alef variants, removes tatweel.
    """
    t = strip_diacritics(text.strip())
    # Normalize alef variants
    t = re.sub("[إأآٱ]", "ا", t)
    # Remove tatweel
    t = t.replace("\u0640", "")
    return t


# ── Document formatting ─────────────────────────────────────────────────────

def format_entry_doc(headword_norm: str, entries: list[dict]) -> str:
    """Format a headword group as a markdown document.

    Adapted from export_entries.format_entry_file() to handle trajectory data
    which may have name_ar but not name_en.
    """
    lines = []
    root = next((e.get("root") for e in entries if e.get("root")), None)
    headword_display = entries[0].get("headword", headword_norm)
    header = f"# {headword_display}"
    if root:
        header += f" (جذر: {root})"
    lines.append(header)
    lines.append("")

    for entry in entries:
        # Prefer name_en, fall back to name_ar
        dict_name = entry.get("name_en") or entry.get("name_ar") or "Unknown"
        lines.append(f"## {dict_name}")
        name_ar = entry.get("name_ar")
        if name_ar and entry.get("name_en"):
            lines.append(f"*{name_ar}*")

        meta_parts = []
        if entry.get("pos"):
            meta_parts.append(f"POS: {entry['pos']}")
        if entry.get("translation_en"):
            meta_parts.append(f"EN: {entry['translation_en']}")
        if meta_parts:
            lines.append(" | ".join(meta_parts))
        lines.append("")

        deftext = entry.get("definitions_text", "")
        if deftext:
            if len(deftext) > 2000:
                deftext = deftext[:2000] + " [...]"
            lines.append(deftext)
            lines.append("")

    return "\n".join(lines)


# ── Review YAML Parser ──────────────────────────────────────────────────────

class ReviewParser:
    """Parse a review YAML file and extract relevance labels per lemma."""

    @classmethod
    def parse(cls, path: Path) -> dict | None:
        """Parse a review YAML and return structured relevance data.

        Returns dict with keys:
            confirmed_lemmas: [{lemma, source, decision_reason, evidence_case}]
            removed_lemmas: [{lemma, source, decision_reason, evidence_case}]
            escalated_lemmas: [{lemma, source}]
            step0_evidence: {lemma: {confirm: [...], contradicts: [...], expands: [...]}}
        """
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not data:
                return None
        except Exception:
            return None

        result = {
            "confirmed_lemmas": [],
            "removed_lemmas": [],
            "escalated_lemmas": [],
            "step0_evidence": {},
        }

        # Parse step0 evidence
        step0 = data.get("step0_evidence", {})
        for pl in step0.get("per_lemma", []):
            lemma = pl.get("lemma", "")
            result["step0_evidence"][lemma] = {
                "confirm": pl.get("confirm", []),
                "contradicts": pl.get("contradicts", []),
                "expands": pl.get("expands", []),
                "peripheral": pl.get("peripheral_observations", []),
                "evidence_status": pl.get("evidence_status"),
            }

        # Parse step1 validation decisions
        step1 = data.get("step1_lemma_validation", {})
        for pl in step1.get("per_lemma", []):
            lemma = pl.get("lemma", "")
            decision = pl.get("decision", "")
            source = pl.get("source", "original")
            entry = {
                "lemma": lemma,
                "source": source,
                "decision_reason": pl.get("decision_reason", ""),
                "evidence_case": (
                    pl.get("evidence_assessment", {}).get("case", "")
                    if isinstance(pl.get("evidence_assessment"), dict) else ""
                ),
                "step05_citation": pl.get("step05_citation", ""),
            }

            if decision == "confirmed":
                result["confirmed_lemmas"].append(entry)
            elif decision == "removed":
                result["removed_lemmas"].append(entry)
            elif decision == "escalated":
                result["escalated_lemmas"].append(entry)

        return result


# ── Lemma → Headword Matcher ────────────────────────────────────────────────

class LemmaMatcher:
    """Match review lemmas to trajectory headword_norms.

    Matching strategy (tried in order, first match wins):
      1. Exact normalized match
      2. With/without definite article (ال)
      3. Ta marbuta (ة) variants
      4. Lemma as a word-boundary substring inside compound headword_norms
         (handles ARABTERM entries like "كائن حي متعض، متعضية")
      5. MWE token match: all tokens of a multi-word lemma found in a headword_norm
    """

    def __init__(self, hw_entries: dict[str, list[dict]]):
        """hw_entries: headword_norm → [entry dicts] from trajectory SQL results."""
        self.hw_entries = hw_entries
        # Build normalized lookup: norm(headword_norm) → headword_norm
        self.norm_lookup: dict[str, str] = {}
        for hw in hw_entries:
            normed = normalize_for_match(hw)
            # Keep the first (typically shortest / most canonical) headword_norm
            if normed not in self.norm_lookup:
                self.norm_lookup[normed] = hw
            # Also index without ال so "الحافز" can match lemma "حافز"
            if normed.startswith("ال") and normed[2:] not in self.norm_lookup:
                self.norm_lookup[normed[2:]] = hw

    def match(self, lemma: str) -> str | None:
        """Find the headword_norm matching a review lemma."""
        normed = normalize_for_match(lemma)

        # 1. Direct match
        if normed in self.norm_lookup:
            return self.norm_lookup[normed]

        # 2. Definite article variants
        if normed.startswith("ال"):
            bare = normed[2:]
            if bare in self.norm_lookup:
                return self.norm_lookup[bare]
        else:
            with_al = "ال" + normed
            if with_al in self.norm_lookup:
                return self.norm_lookup[with_al]

        # 3. Ta marbuta variants
        for variant in [normed.rstrip("ة") + "ة", normed.rstrip("ة")]:
            if variant != normed and variant in self.norm_lookup:
                return self.norm_lookup[variant]

        # 4. Word-boundary substring in compound headword_norms
        #    e.g. lemma "كائن حي" matches hw "كائن حي متعض، متعضية"
        pattern = re.compile(
            r"(?:^|[\s،؛:()])" + re.escape(normed) + r"(?:[\s،؛:()]|$)"
        )
        for hn, hw in self.norm_lookup.items():
            if len(hn) > len(normed) and pattern.search(hn):
                return hw

        # 5. MWE token match: all tokens of a multi-word lemma in some headword_norm
        tokens = normed.split()
        if len(tokens) > 1:
            for hn, hw in self.norm_lookup.items():
                hn_tokens = set(re.split(r"[\s،؛:()]+", hn))
                if all(t in hn_tokens for t in tokens):
                    return hw

        return None


# ── Dataset Builder ──────────────────────────────────────────────────────────

class FinetuningDataBuilder:
    """Build finetuning triplets from trajectory + review data."""

    def __init__(
        self,
        trajectory_path: Path | None,
        review_dir: Path,
        prepared_dir: Path,
        include_soft_negatives: bool = False,
        eval_only: bool = False,
        verbose: bool = False,
    ):
        self.trajectory_path = trajectory_path
        self.review_dir = review_dir
        self.prepared_dir = prepared_dir
        self.include_soft_negatives = include_soft_negatives
        self.eval_only = eval_only
        self.verbose = verbose

        # Load trajectory records keyed by synset_id
        self.trajectory: dict[str, dict] = {}
        if trajectory_path:
            with open(trajectory_path, encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    self.trajectory[rec["synset_id"]] = rec

    def _build_hw_entries(self, record: dict, synset_id: str) -> dict[str, list[dict]]:
        """Build headword_norm → [entry dicts] from trajectory + evidence.json.

        Merges two sources (deduped by entry_id):
          1. Trajectory SQL results (headword_lookup, fts_keyword, english_bridge)
          2. Pre-fetched evidence.json headword_entries (fallback for entries the
             worker verified but didn't re-query via SQL)
        """
        hw_entries: dict[str, list[dict]] = defaultdict(list)
        seen_eids: set = set()

        # Source 1: trajectory SQL results
        for query in record.get("sql_queries", []):
            if not query.get("result_parsed"):
                continue
            if query["query_type"] not in (
                "headword_lookup", "fts_keyword", "english_bridge", "headword_like"
            ):
                continue

            for row in query["result_parsed"]:
                hw = row.get("headword_norm")
                eid = row.get("entry_id")
                if not hw:
                    continue
                if eid and eid in seen_eids:
                    continue
                if eid:
                    seen_eids.add(eid)
                hw_entries[hw].append(row)

        # Source 2: evidence.json (pre-fetched headword entries)
        evi_path = self.prepared_dir / synset_id / "evidence.json"
        if evi_path.exists():
            try:
                evi = json.loads(evi_path.read_text(encoding="utf-8"))
                for entry in evi.get("headword_entries", []):
                    hw = entry.get("headword_norm")
                    eid = entry.get("entry_id")
                    if not hw:
                        continue
                    if eid and eid in seen_eids:
                        continue
                    if eid:
                        seen_eids.add(eid)
                    hw_entries[hw].append(entry)
            except (json.JSONDecodeError, OSError):
                pass

        return dict(hw_entries)

    def _build_hw_entries_from_evidence(self, synset_id: str) -> dict[str, list[dict]]:
        """Build headword_norm → [entry dicts] from evidence.json only.

        Used when no trajectory record is available for a synset.
        """
        evi_path = self.prepared_dir / synset_id / "evidence.json"
        if not evi_path.exists():
            return {}
        hw_entries: dict[str, list[dict]] = defaultdict(list)
        seen_eids: set = set()
        try:
            evi = json.loads(evi_path.read_text(encoding="utf-8"))
            for entry in evi.get("headword_entries", []):
                hw = entry.get("headword_norm")
                eid = entry.get("entry_id")
                if not hw:
                    continue
                if eid and eid in seen_eids:
                    continue
                if eid:
                    seen_eids.add(eid)
                hw_entries[hw].append(entry)
        except (json.JSONDecodeError, OSError):
            pass
        return dict(hw_entries)

    def _load_synset_info(self, synset_id: str) -> dict | None:
        """Load synset_info from prepared YAML when no trajectory record."""
        info_path = self.prepared_dir / synset_id / "synset_info.yaml"
        if not info_path.exists():
            return None
        try:
            return yaml.safe_load(info_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _build_query(self, synset_info: dict) -> str:
        """Construct the combined query: lemmas — definition."""
        lemmas = " ".join(synset_info.get("lemmas", []))
        defn = synset_info.get("definition_ar", "")
        return f"Query: {lemmas} — {defn}"

    def _build_doc(self, headword_norm: str, entries: list[dict]) -> str:
        """Build a Document: prefixed markdown string from DB entries."""
        md = format_entry_doc(headword_norm, entries)
        return f"Document: {md}"

    def process_synset(self, synset_id: str) -> dict | None:
        """Process one synset → return dict with triplets, pairs, and metadata."""
        # Load review YAML
        review_path = self.review_dir / f"{synset_id}.review.yaml"
        if not review_path.exists():
            if self.verbose:
                print(f"  SKIP {synset_id}: no review YAML", file=sys.stderr)
            return None

        review = ReviewParser.parse(review_path)
        if not review:
            if self.verbose:
                print(f"  SKIP {synset_id}: review parse failed", file=sys.stderr)
            return None

        # Build headword → entries map and load synset info
        trec = self.trajectory.get(synset_id)
        if trec:
            # Primary path: trajectory SQL results + evidence.json supplement
            hw_entries = self._build_hw_entries(trec, synset_id)
            synset_info = trec["synset_info"]
        else:
            # Evidence-only path: no trajectory, use evidence.json + synset_info.yaml
            hw_entries = self._build_hw_entries_from_evidence(synset_id)
            synset_info = self._load_synset_info(synset_id)
            if synset_info is None:
                if self.verbose:
                    print(f"  SKIP {synset_id}: no synset_info.yaml in prepared dir", file=sys.stderr)
                return None

        if not hw_entries:
            if self.verbose:
                print(f"  SKIP {synset_id}: no headword entries found", file=sys.stderr)
            return None

        matcher = LemmaMatcher(hw_entries)
        query = self._build_query(synset_info)

        # Match confirmed lemmas to headwords
        positive_hws: list[dict] = []
        for cl in review["confirmed_lemmas"]:
            hw = matcher.match(cl["lemma"])
            if hw:
                positive_hws.append({
                    "headword_norm": hw,
                    "lemma": cl["lemma"],
                    "source": cl["source"],
                    "decision_reason": cl["decision_reason"],
                })
            elif self.verbose:
                print(
                    f"  WARN {synset_id}: confirmed lemma '{cl['lemma']}' "
                    f"not found in trajectory headwords",
                    file=sys.stderr,
                )

        # Match removed lemmas to headwords
        negative_hws: list[dict] = []
        for rl in review["removed_lemmas"]:
            hw = matcher.match(rl["lemma"])
            if hw:
                negative_hws.append({
                    "headword_norm": hw,
                    "lemma": rl["lemma"],
                    "source": rl["source"],
                    "decision_reason": rl["decision_reason"],
                })
            elif self.verbose:
                print(
                    f"  WARN {synset_id}: removed lemma '{rl['lemma']}' "
                    f"not found in trajectory headwords",
                    file=sys.stderr,
                )

        # Soft negatives: headwords retrieved but not confirmed/removed
        soft_negative_hws: list[dict] = []
        if self.include_soft_negatives:
            confirmed_set = {h["headword_norm"] for h in positive_hws}
            removed_set = {h["headword_norm"] for h in negative_hws}
            escalated_set = set()
            for el in review.get("escalated_lemmas", []):
                hw = matcher.match(el["lemma"])
                if hw:
                    escalated_set.add(hw)

            for hw in hw_entries:
                if hw not in confirmed_set and hw not in removed_set and hw not in escalated_set:
                    soft_negative_hws.append({
                        "headword_norm": hw,
                        "lemma": "",
                        "source": "soft_negative",
                        "decision_reason": "Retrieved by SQL but not mentioned in review",
                    })

        if not positive_hws:
            if self.verbose:
                print(f"  SKIP {synset_id}: no positive headwords matched", file=sys.stderr)
            return None

        # Build documents
        positive_docs = []
        for ph in positive_hws:
            entries = hw_entries[ph["headword_norm"]]
            doc = self._build_doc(ph["headword_norm"], entries)
            positive_docs.append({**ph, "doc": doc, "entry_count": len(entries)})

        all_negative_hws = negative_hws + soft_negative_hws
        negative_docs = []
        for nh in all_negative_hws:
            entries = hw_entries.get(nh["headword_norm"], [])
            if not entries:
                continue
            doc = self._build_doc(nh["headword_norm"], entries)
            negative_docs.append({**nh, "doc": doc, "entry_count": len(entries)})

        # Assemble triplets (skip when positive and negative share the same headword)
        triplets = []
        for pd in positive_docs:
            for nd in negative_docs:
                if pd["headword_norm"] == nd["headword_norm"]:
                    continue
                triplets.append({
                    "anchor": query,
                    "positive": pd["doc"],
                    "negative": nd["doc"],
                    "_meta": {
                        "synset_id": synset_id,
                        "positive_lemma": pd["lemma"],
                        "positive_headword": pd["headword_norm"],
                        "positive_source": pd["source"],
                        "positive_entries": pd["entry_count"],
                        "negative_lemma": nd["lemma"],
                        "negative_headword": nd["headword_norm"],
                        "negative_source": nd["source"],
                        "negative_reason": nd["decision_reason"],
                        "negative_entries": nd["entry_count"],
                    },
                })

        # Assemble positive-only pairs
        pairs = []
        for pd in positive_docs:
            pairs.append({
                "anchor": query,
                "positive": pd["doc"],
                "_meta": {
                    "synset_id": synset_id,
                    "positive_lemma": pd["lemma"],
                    "positive_headword": pd["headword_norm"],
                    "positive_source": pd["source"],
                    "positive_entries": pd["entry_count"],
                },
            })

        return {
            "synset_id": synset_id,
            "triplets": triplets,
            "pairs": pairs,
            "confirmed_count": len(positive_hws),
            "removed_count": len(negative_hws),
            "soft_negative_count": len(soft_negative_hws),
            "total_headwords": len(hw_entries),
        }

    def build(
        self, synset_filter: str | None = None, seed: int = 42
    ) -> dict:
        """Build the full dataset across all synsets.

        Returns a dict with:
            triplets, pairs: full lists
            train_triplets, eval_triplets: 80/20 split by synset (or all-eval if eval_only)
            train_pairs, eval_pairs: 80/20 split by synset (or all-eval if eval_only)
            stats: aggregate statistics
        """
        # Determine which synsets to process
        if synset_filter:
            synset_ids = [synset_filter]
        elif self.trajectory:
            # Process all synsets that have both trajectory + review
            synset_ids = sorted(
                sid for sid in self.trajectory
                if (self.review_dir / f"{sid}.review.yaml").exists()
            )
        else:
            # No trajectory: enumerate synsets from review directory
            synset_ids = sorted(
                p.name.removesuffix(".review.yaml")
                for p in self.review_dir.glob("*.review.yaml")
            )

        all_triplets = []
        all_pairs = []
        synset_results = []
        skipped = 0

        for sid in synset_ids:
            result = self.process_synset(sid)
            if result is None:
                skipped += 1
                continue
            all_triplets.extend(result["triplets"])
            all_pairs.extend(result["pairs"])
            synset_results.append(result)

        # Train/eval split by synset
        processed_sids = [r["synset_id"] for r in synset_results]

        if self.eval_only:
            # All data goes to eval (no training split)
            train_triplets = []
            eval_triplets = all_triplets
            train_pairs = []
            eval_pairs = all_pairs
        else:
            rng = random.Random(seed)
            rng.shuffle(processed_sids)
            split_idx = int(len(processed_sids) * 0.8)
            train_sids = set(processed_sids[:split_idx])
            eval_sids = set(processed_sids[split_idx:])

            train_triplets = [t for t in all_triplets if t["_meta"]["synset_id"] in train_sids]
            eval_triplets = [t for t in all_triplets if t["_meta"]["synset_id"] in eval_sids]
            train_pairs = [p for p in all_pairs if p["_meta"]["synset_id"] in train_sids]
            eval_pairs = [p for p in all_pairs if p["_meta"]["synset_id"] in eval_sids]

        # Compute stats
        stats = self._compute_stats(
            synset_results, all_triplets, all_pairs,
            train_triplets, eval_triplets,
            train_pairs, eval_pairs,
            len(synset_ids), skipped,
        )

        return {
            "triplets": all_triplets,
            "pairs": all_pairs,
            "train_triplets": train_triplets,
            "eval_triplets": eval_triplets,
            "train_pairs": train_pairs,
            "eval_pairs": eval_pairs,
            "synset_results": synset_results,
            "stats": stats,
        }

    def _compute_stats(
        self, results, triplets, pairs,
        train_trip, eval_trip, train_pairs, eval_pairs,
        total_attempted, skipped,
    ) -> dict:
        confirmed_counts = [r["confirmed_count"] for r in results]
        removed_counts = [r["removed_count"] for r in results]
        soft_counts = [r["soft_negative_count"] for r in results]
        triplets_per = [len(r["triplets"]) for r in results]

        # Source distribution
        pos_sources = Counter(t["_meta"]["positive_source"] for t in triplets)
        neg_sources = Counter(t["_meta"]["negative_source"] for t in triplets)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "synsets_attempted": total_attempted,
            "synsets_processed": len(results),
            "synsets_skipped": skipped,
            "total_triplets": len(triplets),
            "total_pairs": len(pairs),
            "train_triplets": len(train_trip),
            "eval_triplets": len(eval_trip),
            "train_pairs": len(train_pairs),
            "eval_pairs": len(eval_pairs),
            "confirmed_per_synset": {
                "mean": round(statistics.mean(confirmed_counts), 1) if confirmed_counts else 0,
                "median": statistics.median(confirmed_counts) if confirmed_counts else 0,
                "max": max(confirmed_counts) if confirmed_counts else 0,
            },
            "removed_per_synset": {
                "mean": round(statistics.mean(removed_counts), 1) if removed_counts else 0,
                "median": statistics.median(removed_counts) if removed_counts else 0,
                "max": max(removed_counts) if removed_counts else 0,
            },
            "soft_negatives_per_synset": {
                "mean": round(statistics.mean(soft_counts), 1) if soft_counts else 0,
                "median": statistics.median(soft_counts) if soft_counts else 0,
                "max": max(soft_counts) if soft_counts else 0,
            },
            "triplets_per_synset": {
                "mean": round(statistics.mean(triplets_per), 1) if triplets_per else 0,
                "median": statistics.median(triplets_per) if triplets_per else 0,
                "max": max(triplets_per) if triplets_per else 0,
            },
            "positive_source_distribution": dict(pos_sources),
            "negative_source_distribution": dict(neg_sources),
        }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    script_dir = Path(__file__).resolve().parent
    default_trajectory = (
        script_dir.parent / "trajectory_dataset" / "output" / "sql_query_dataset_backfilled.jsonl"
    )
    default_reviews = (
        script_dir.parent / "linguistic_review_guide" / "output" / "reviews_claude_db"
    )
    default_prepared = (
        script_dir.parent / "linguistic_review_guide" / "claude_code_db" / "prepared"
    )
    default_output = script_dir / "finetuning_data"

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--trajectory", type=Path, default=None,
        help="Path to trajectory JSONL (optional; uses evidence.json if omitted)",
    )
    parser.add_argument(
        "--review-dir", type=Path, default=default_reviews,
        help=f"Directory with *.review.yaml files (default: {default_reviews})",
    )
    parser.add_argument(
        "--prepared-dir", type=Path, default=default_prepared,
        help=f"Directory with prepared/{{synset_id}}/ dirs (default: {default_prepared})",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=default_output,
        help=f"Output directory (default: {default_output})",
    )
    parser.add_argument(
        "--synset", type=str, default=None,
        help="Process a single synset (for debugging)",
    )
    parser.add_argument(
        "--include-soft-negatives", action="store_true",
        help="Include FTS-retrieved headwords not mentioned in review as soft negatives",
    )
    parser.add_argument(
        "--eval-only", action="store_true",
        help="Output all triplets as eval (no train/eval split)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print progress and debug info",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for train/eval split (default: 42)",
    )
    args = parser.parse_args()

    # Validate inputs
    if args.trajectory and not args.trajectory.exists():
        print(f"Error: trajectory file not found: {args.trajectory}", file=sys.stderr)
        sys.exit(1)
    if not args.review_dir.is_dir():
        print(f"Error: review directory not found: {args.review_dir}", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    builder = FinetuningDataBuilder(
        trajectory_path=args.trajectory,
        review_dir=args.review_dir,
        prepared_dir=args.prepared_dir,
        include_soft_negatives=args.include_soft_negatives,
        eval_only=args.eval_only,
        verbose=args.verbose,
    )

    print(f"Trajectory: {args.trajectory or '(none — using evidence.json only)'}")
    print(f"Reviews:    {args.review_dir}")
    print(f"Prepared:   {args.prepared_dir}")
    print(f"Output:     {args.output_dir}")
    if args.include_soft_negatives:
        print("Including soft negatives from FTS results")
    if args.eval_only:
        print("Eval-only mode: all triplets go to eval (no train/eval split)")
    print()

    dataset = builder.build(synset_filter=args.synset, seed=args.seed)

    # Write output files
    def write_jsonl(path: Path, records: list[dict]):
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    write_jsonl(args.output_dir / "triplets.jsonl", dataset["triplets"])
    write_jsonl(args.output_dir / "pairs.jsonl", dataset["pairs"])
    write_jsonl(args.output_dir / "triplets_train.jsonl", dataset["train_triplets"])
    write_jsonl(args.output_dir / "triplets_eval.jsonl", dataset["eval_triplets"])
    write_jsonl(args.output_dir / "pairs_train.jsonl", dataset["train_pairs"])
    write_jsonl(args.output_dir / "pairs_eval.jsonl", dataset["eval_pairs"])

    stats = dataset["stats"]
    with open(args.output_dir / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"Synsets processed: {stats['synsets_processed']} / {stats['synsets_attempted']}")
    print(f"  Skipped: {stats['synsets_skipped']}")
    print()
    print(f"Total triplets: {stats['total_triplets']}")
    print(f"  Train: {stats['train_triplets']}")
    print(f"  Eval:  {stats['eval_triplets']}")
    print()
    print(f"Total pairs: {stats['total_pairs']}")
    print(f"  Train: {stats['train_pairs']}")
    print(f"  Eval:  {stats['eval_pairs']}")
    print()
    print(f"Confirmed per synset: mean={stats['confirmed_per_synset']['mean']}, "
          f"median={stats['confirmed_per_synset']['median']}")
    print(f"Removed per synset:   mean={stats['removed_per_synset']['mean']}, "
          f"median={stats['removed_per_synset']['median']}")
    print(f"Triplets per synset:  mean={stats['triplets_per_synset']['mean']}, "
          f"median={stats['triplets_per_synset']['median']}")
    print()
    print(f"Positive sources: {dict(stats['positive_source_distribution'])}")
    print(f"Negative sources: {dict(stats['negative_source_distribution'])}")
    print()
    print(f"Output: {args.output_dir}/")


if __name__ == "__main__":
    main()
