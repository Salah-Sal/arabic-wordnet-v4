#!/usr/bin/env python3
"""Export classical Arabic dictionary entries from SQLite → markdown files.

Groups entries by headword_norm (one file per unique headword). Each file
contains all dictionary perspectives on that word from the classical sources.

Prioritizes dictionaries by linguistic importance, stopping when the token
budget is reached.

Usage:
    python export_entries.py --db /path/to/arabic_dict.db --output export/
    python export_entries.py --db /path/to/arabic_dict.db --output export/ --max-tokens 1800000
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Priority-ordered classical dictionaries (most linguistically important first)
PRIORITY_DICT_IDS = [
    103,  # Ibn Manẓūr, Lisān al-ʿArab (d. 1311) — THE classical dictionary
    120,  # Murtaḍa al-Zabīdī, Tāj al-ʿArūs (d. 1790) — most comprehensive
    113,  # Firuzabadi, al-Qāmūs al-Muḥīṭ (d. 1414)
    3,    # Kitab al-Ayn — oldest Arabic dictionary
    145,  # Lane's Lexicon (d. 1876) — gold standard English-Arabic
    152,  # Ibn Sīda, al-Muḥkam (d. 1066)
    151,  # Ibn Fāris, Maqāyīs al-Lugha (d. 1004)
    150,  # al-Jawharī, al-Ṣiḥāḥ (d. 1003)
    153,  # al-Zamakhsharī, Asās al-Balāgha (d. 1143)
    5,    # Mujmal al-Lugha (OCR)
    4,    # Maqayis al-Lugha (OCR)
    128,  # Dozy, Supplément (d. 1883)
    132,  # al-Ṣāḥib bin ʿAbbād, al-Muḥīṭ fī l-Lugha (d. 995)
    105,  # Ibn al-Athīr, al-Nihāya (d. 1210)
    108,  # al-Razī, Mukhtār al-Ṣiḥāḥ (d. 1266)
]

# Characters per token estimate for Arabic text (conservative)
CHARS_PER_TOKEN = 3.0


def estimate_tokens(text: str) -> int:
    """Rough token estimate for Arabic/mixed text."""
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def fetch_entries(db_path: str, dict_ids: list[int]) -> dict:
    """Fetch entries grouped by headword_norm, with definitions and examples."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    placeholders = ",".join("?" * len(dict_ids))

    # Fetch entries from priority dictionaries
    rows = conn.execute(f"""
        SELECT e.id AS entry_id, e.headword, e.headword_norm, e.root,
               e.pos, e.definitions_text, e.translation_en,
               d.name_en, d.name_ar, d.source_type
        FROM entries e
        JOIN dictionaries d ON e.dictionary_id = d.id
        WHERE d.id IN ({placeholders})
        ORDER BY e.headword_norm, d.id
    """, dict_ids).fetchall()

    # Group by headword_norm
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["headword_norm"]].append(dict(row))

    # Fetch examples for these entries
    entry_ids = [r["entry_id"] for r in rows]
    if entry_ids:
        # Batch in chunks of 500
        examples = defaultdict(list)
        for i in range(0, len(entry_ids), 500):
            chunk = entry_ids[i:i + 500]
            ph = ",".join("?" * len(chunk))
            for ex in conn.execute(f"""
                SELECT entry_id, text, type FROM examples
                WHERE entry_id IN ({ph})
                ORDER BY entry_id, idx
            """, chunk):
                examples[ex["entry_id"]].append(
                    f"[{ex['type']}] {ex['text']}" if ex["type"] else ex["text"]
                )

        # Attach examples to entries
        for entries in grouped.values():
            for entry in entries:
                entry["examples"] = examples.get(entry["entry_id"], [])

    conn.close()
    return grouped


def format_entry_file(headword_norm: str, entries: list[dict]) -> str:
    """Format a headword group as a markdown document."""
    lines = []
    root = next((e["root"] for e in entries if e["root"]), None)
    header = f"# {entries[0]['headword']}"
    if root:
        header += f" (جذر: {root})"
    lines.append(header)
    lines.append("")

    for entry in entries:
        lines.append(f"## {entry['name_en']}")
        if entry["name_ar"]:
            lines.append(f"*{entry['name_ar']}*")
        meta_parts = []
        if entry["pos"]:
            meta_parts.append(f"POS: {entry['pos']}")
        if entry["translation_en"]:
            meta_parts.append(f"EN: {entry['translation_en']}")
        if meta_parts:
            lines.append(" | ".join(meta_parts))
        lines.append("")

        if entry["definitions_text"]:
            deftext = entry["definitions_text"]
            if len(deftext) > 2000:
                deftext = deftext[:2000] + " [...]"
            lines.append(deftext)
            lines.append("")

        if entry.get("examples"):
            lines.append("### شواهد")
            for ex in entry["examples"][:5]:  # cap at 5 examples
                lines.append(f"- {ex}")
            lines.append("")

    return "\n".join(lines)


def load_ground_truth_headwords(evidence_dir: Path) -> set[str]:
    """Extract headword_norm values from evidence.json files for prioritization."""
    gt_headwords = set()
    if not evidence_dir.is_dir():
        return gt_headwords
    for edir in evidence_dir.iterdir():
        efile = edir / "evidence.json"
        if efile.exists():
            try:
                data = json.loads(efile.read_text(encoding="utf-8"))
                for entry in data.get("headword_entries", []):
                    if entry.get("headword_norm"):
                        gt_headwords.add(entry["headword_norm"])
                for entry in data.get("english_bridge", []):
                    if entry.get("headword_norm"):
                        gt_headwords.add(entry["headword_norm"])
            except (json.JSONDecodeError, KeyError):
                continue
    return gt_headwords


def main():
    import random
    random.seed(42)

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="Path to arabic_dict.db")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--max-tokens", type=int, default=1_800_000,
                        help="Token budget (default: 1.8M, leaving 200K buffer)")
    parser.add_argument("--max-files", type=int, default=10_000,
                        help="Max files (Mixedbread Store limit)")
    parser.add_argument("--evidence-dir", type=Path, default=None,
                        help="Path to prepared/ dir with evidence.json for prioritization")
    args = parser.parse_args()

    output_dir = Path(args.output) / "entries"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching entries from {len(PRIORITY_DICT_IDS)} priority dictionaries...",
          file=sys.stderr)
    grouped = fetch_entries(args.db, PRIORITY_DICT_IDS)
    print(f"Found {len(grouped)} unique headwords, "
          f"{sum(len(v) for v in grouped.values())} total entries", file=sys.stderr)

    # Load ground truth headwords for prioritization
    gt_headwords = set()
    if args.evidence_dir:
        gt_headwords = load_ground_truth_headwords(args.evidence_dir)
        print(f"Ground truth headwords from evidence: {len(gt_headwords)}", file=sys.stderr)

    # Priority order: (1) ground truth headwords, (2) random sample of the rest
    # This ensures evaluation coverage while sampling across the full alphabet
    gt_in_export = [hw for hw in grouped if hw in gt_headwords]
    rest = [hw for hw in grouped if hw not in gt_headwords]
    random.shuffle(rest)
    sorted_headwords = gt_in_export + rest
    print(f"Priority headwords: {len(gt_in_export)} (ground truth) + "
          f"{len(rest)} (random sample)", file=sys.stderr)

    manifest = {}  # headword_norm → {filename, entry_ids}
    total_tokens = 0
    file_count = 0
    entry_count = 0

    for hw in sorted_headwords:
        if file_count >= args.max_files:
            print(f"Hit file limit ({args.max_files})", file=sys.stderr)
            break

        entries = grouped[hw]
        content = format_entry_file(hw, entries)
        tokens = estimate_tokens(content)

        if total_tokens + tokens > args.max_tokens:
            print(f"Hit token budget at {total_tokens:,} tokens", file=sys.stderr)
            break

        # Sanitize filename (use entry_id of first entry as unique key)
        first_id = entries[0]["entry_id"]
        filename = f"hw_{first_id:07d}.md"
        filepath = output_dir / filename

        filepath.write_text(content, encoding="utf-8")

        entry_ids = [e["entry_id"] for e in entries]
        manifest[hw] = {
            "filename": filename,
            "entry_ids": entry_ids,
            "headword": entries[0]["headword"],
            "root": next((e["root"] for e in entries if e["root"]), None),
            "token_estimate": tokens,
        }

        total_tokens += tokens
        file_count += 1
        entry_count += len(entries)

    # Save manifest
    manifest_path = Path(args.output) / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Save reverse index: entry_id → headword_norm
    reverse_index = {}
    for hw, info in manifest.items():
        for eid in info["entry_ids"]:
            reverse_index[str(eid)] = hw
    reverse_path = Path(args.output) / "entry_id_to_headword.json"
    reverse_path.write_text(
        json.dumps(reverse_index, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\nExport complete:", file=sys.stderr)
    print(f"  Files:   {file_count:,}", file=sys.stderr)
    print(f"  Entries: {entry_count:,}", file=sys.stderr)
    print(f"  Tokens:  ~{total_tokens:,}", file=sys.stderr)
    print(f"  Output:  {output_dir}", file=sys.stderr)
    print(f"  Manifest: {manifest_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
