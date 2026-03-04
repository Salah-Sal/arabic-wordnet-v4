#!/usr/bin/env python3
"""
Extract existing Arabic translations from AWN4 XML into batch JSON files.

Reconstructs the batch file format used by convert_to_lmf.py so that
the XML can be regenerated from these files plus any new translations.

Usage:
    python scripts/extract_translations.py
    python scripts/extract_translations.py --input output/awn4.xml.gz --output-dir data/extracted_batches
"""

import argparse
import json
import math
from pathlib import Path

import wn

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = PROJECT_ROOT / "output" / "awn4.xml.gz"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "extracted_batches"
BATCH_SIZE = 750


def main():
    parser = argparse.ArgumentParser(description="Extract translations from AWN4 XML")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading AWN4 from {args.input}...")
    wn.add(str(args.input))
    awn4 = wn.Wordnet('awn4:4.0', expand='')

    synsets = list(awn4.synsets())
    print(f"Found {len(synsets):,} synsets")

    # Build sense→synset mapping for lemma extraction
    # Group lemmas by synset
    synset_lemmas = {}
    for word in awn4.words():
        lemma = word.lemma()
        for sense in word.senses():
            sid = sense.synset().id
            if sid not in synset_lemmas:
                synset_lemmas[sid] = []
            if lemma not in synset_lemmas[sid]:
                synset_lemmas[sid].append(lemma)

    entries = []
    for ss in synsets:
        awn4_id = ss.id
        # Convert awn4-XXXXXXXX-p to oewn-XXXXXXXX-p
        oewn_id = "oewn-" + awn4_id[5:]

        lemmas = synset_lemmas.get(awn4_id, [])
        defs = ss.definitions()
        exs = ss.examples()

        entries.append({
            "id": oewn_id,
            "lem_ar": lemmas,
            "def_ar": defs[0] if defs else "",
            "ex_ar": list(exs),
        })

    # Sort by OEWN ID for deterministic output
    entries.sort(key=lambda e: e["id"])

    # Write batches
    num_batches = math.ceil(len(entries) / args.batch_size)
    print(f"Writing {num_batches} batch files ({args.batch_size} per batch)...")

    for i in range(num_batches):
        batch = entries[i * args.batch_size : (i + 1) * args.batch_size]
        batch_file = args.output_dir / f"batch_{i:04d}.json"
        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump({"translations": batch}, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(entries):,} translations into {num_batches} files in {args.output_dir}")


if __name__ == "__main__":
    main()
