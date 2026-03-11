#!/usr/bin/env python3
"""Extract synset_info + masked variant for Claude Code DB-direct review.

Produces lightweight prepared/{synset_id}/ directories containing only:
  - synset_info.yaml       (full synset metadata with lemmas)
  - synset_info_masked.yaml (lemmas removed — for Step 0.5)

No dictionary DB dependency — only needs the `wn` Python library with AWN4 + OEWN loaded.

Usage:
    python3 extract_synset_info.py awn4-02592253-n               # single synset
    python3 extract_synset_info.py awn4-02592253-n awn4-03070134-n  # multiple
    python3 extract_synset_info.py --batch synset_list.txt        # from file
    python3 extract_synset_info.py --all                          # all AWN4 synsets
    python3 extract_synset_info.py --all --pos n                  # all nouns

Requirements:
    pip install wn pyyaml
    wn database must contain awn4 and oewn:2024.
"""
from __future__ import annotations

import argparse
import sys
import time
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
                force: bool = False) -> dict:
    """Process a single synset. Returns stats dict."""
    out_dir = output_dir / synset_id
    if not force and (out_dir / "synset_info.yaml").exists():
        return {"synset_id": synset_id, "status": "skip"}

    try:
        synset_data = wn_bridge.get_synset_data(synset_id)
    except Exception as e:
        return {"synset_id": synset_id, "status": "fail", "error": str(e)}

    synset_info = extract_synset_info(synset_data)
    synset_info_masked = mask_synset_info(synset_info)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "synset_info.yaml").write_text(synset_info, encoding="utf-8")
    (out_dir / "synset_info_masked.yaml").write_text(synset_info_masked, encoding="utf-8")

    return {
        "synset_id": synset_id,
        "status": "ok",
        "lemma_count": len(synset_data.get("lemmas", [])),
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
    args = parser.parse_args()

    # Initialize WN bridge
    print("Initializing WordNet bridge...")
    wn_bridge = WNBridge()

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
    t0 = time.time()

    for i, sid in enumerate(synset_ids, 1):
        result = process_one(sid, wn_bridge, output_dir, force=args.force)
        if result["status"] == "skip":
            skip += 1
        elif result["status"] == "ok":
            ok += 1
            if i <= 5 or i % 1000 == 0:
                print(f"[{i}/{len(synset_ids)}] OK: {sid} ({result['lemma_count']} lemmas)")
        else:
            fail += 1
            print(f"[{i}/{len(synset_ids)}] FAIL: {sid}: {result.get('error', '?')}")

        if i % 1000 == 0 and i > 5:
            elapsed = time.time() - t0
            rate = i / elapsed
            print(f"  Progress: {i}/{len(synset_ids)} ({rate:.0f}/s)")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s: {ok} ok, {skip} skipped, {fail} failed")


if __name__ == "__main__":
    main()
