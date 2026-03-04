#!/usr/bin/env python3
"""
Prepare OEWN satellite adjective data for Arabic translation.

For each of the ~10,720 satellite adjectives (pos='s') in OEWN 2024,
extracts English lemmas, definition, examples, and head adjective info
(via 'similar' relation) along with the head's existing Arabic translation.

Output: JSON reference files in data/satellite_input/ for use during translation.

Usage:
    python scripts/prepare_satellite_data.py
"""

import json
import math
from pathlib import Path

import wn

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "satellite_input"
AWN4_XML = PROJECT_ROOT / "output" / "awn4.xml.gz"
BATCH_SIZE = 200


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading wordnets...")
    wn.add(str(AWN4_XML))
    en = wn.Wordnet('oewn:2024')
    awn4 = wn.Wordnet('awn4:4.0', expand='')

    # Build AWN4 lookup: oewn_id -> {lemmas, definition}
    print("Building AWN4 translation lookup...")
    awn4_lookup = {}
    awn4_synset_lemmas = {}
    for word in awn4.words():
        lemma = word.lemma()
        for sense in word.senses():
            sid = sense.synset().id
            if sid not in awn4_synset_lemmas:
                awn4_synset_lemmas[sid] = []
            if lemma not in awn4_synset_lemmas[sid]:
                awn4_synset_lemmas[sid].append(lemma)

    for ss in awn4.synsets():
        oewn_id = "oewn-" + ss.id[5:]
        defs = ss.definitions()
        awn4_lookup[oewn_id] = {
            "lemmas_ar": awn4_synset_lemmas.get(ss.id, []),
            "def_ar": defs[0] if defs else "",
        }

    # Collect satellite adjectives
    print("Collecting satellite adjectives from OEWN...")
    satellites = []
    for ss in en.synsets():
        if ss.pos != 's':
            continue

        sid = ss.id
        lemmas = [w.lemma() for w in ss.words()]
        defs = ss.definitions()
        exs = ss.examples()
        ili = ss.ili if ss.ili else None

        # Find head adjective via 'similar' relation
        rels = ss.relations()
        head_info = None
        for tgt in rels.get('similar', []):
            if tgt.pos == 'a':
                head_oewn_id = tgt.id
                head_lemmas_en = [w.lemma() for w in tgt.words()]
                head_def_en = tgt.definitions()[0] if tgt.definitions() else ""
                head_ar = awn4_lookup.get(head_oewn_id, {})
                head_info = {
                    "oewn_id": head_oewn_id,
                    "lemmas_en": head_lemmas_en,
                    "def_en": head_def_en,
                    "lemmas_ar": head_ar.get("lemmas_ar", []),
                    "def_ar": head_ar.get("def_ar", ""),
                }
                break

        satellites.append({
            "id": sid,
            "ili": ili,
            "lemmas_en": lemmas,
            "def_en": defs[0] if defs else "",
            "examples_en": list(exs),
            "head": head_info,
        })

    satellites.sort(key=lambda e: e["id"])
    print(f"Found {len(satellites):,} satellite adjectives")

    # Count how many have head adjective info
    with_head = sum(1 for s in satellites if s["head"] is not None)
    with_head_ar = sum(1 for s in satellites if s["head"] and s["head"]["lemmas_ar"])
    print(f"  With head adjective: {with_head:,}")
    print(f"  With head Arabic translation: {with_head_ar:,}")

    # Write batches
    num_batches = math.ceil(len(satellites) / BATCH_SIZE)
    print(f"Writing {num_batches} reference files ({BATCH_SIZE} per file)...")

    for i in range(num_batches):
        batch = satellites[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        out_file = OUTPUT_DIR / f"satellites_{i:04d}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"satellites": batch}, f, ensure_ascii=False, indent=2)

    print(f"Done. Reference data in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
