#!/usr/bin/env python3
"""Build polysemy evidence packages for AWN4 duplicate-synset groups.

Stage 4A of the AWN4 review pipeline. Takes the duplicate_synsets list from
the prefilter report and assembles rich evidence packages combining AWN4
synset data (definitions, examples, relations, hypernym context) with
dictionary evidence (headwords, roots, definitions, examples).

Usage:
    python experiments/polysemy_reviews/polysemy_packages.py
    python experiments/polysemy_reviews/polysemy_packages.py --top 100
    python experiments/polysemy_reviews/polysemy_packages.py --min-count 5
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = SCRIPT_DIR.parent
AWN4_BASE = EXPERIMENTS_DIR.parent
AWN4_XML = str(AWN4_BASE / "output" / "awn4.xml")
DICT_DB = str(AWN4_BASE.parent / "arabic-dictionaries" / "extraction" / "db" / "arabic_dict.db")
PREFILTER_REPORT = str(EXPERIMENTS_DIR / "prefilter" / "prefilter_report.json")
DEFAULT_OUTPUT = str(SCRIPT_DIR / "polysemy_packages.json")

# ─── Normalization (copied from prefilter_dict.py for self-containment) ──────

DIACRITICS_RE = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')
TRAILING_DIGITS_RE = re.compile(r'\d+$')
ARTICLE_RE = re.compile(r'^ال\u0640?')


def strip_diacritics(text):
    """Remove Arabic tashkeel diacritics."""
    return DIACRITICS_RE.sub('', text)


def normalize_canonical(text):
    """Normalize to canonical match form for lookup."""
    t = strip_diacritics(text.strip())
    t = TRAILING_DIGITS_RE.sub('', t)
    t = t.replace('\u0623', '\u0627')  # أ → ا
    t = t.replace('\u0625', '\u0627')  # إ → ا
    t = t.replace('\u0622', '\u0627')  # آ → ا
    t = t.replace('\u0649', '\u064A')  # ى → ي
    t = t.replace('\u0640', '')         # tatweel
    t = ARTICLE_RE.sub('', t)
    return t.strip()


# ─── Source name mapping (from web/app.py) ───────────────────────────────────

SOURCE_NAMES = {
    'Al_Waseet': 'المعجم الوسيط',
    'Kitab_Al_Ayn': 'كتاب العين',
}
# المعجم الكبير volumes
for i in range(1, 19):
    SOURCE_NAMES[f'Vol_{i}'] = f'المعجم الكبير - المجلد {i}'


def friendly_source(raw_source):
    """Convert raw DB source name to Arabic display name."""
    return SOURCE_NAMES.get(raw_source, raw_source)


# ─── Phase 1: Load Prefilter Report ─────────────────────────────────────────

def load_prefilter(report_path, top_n=None, min_count=None):
    """Load duplicate_synsets from prefilter report and apply filters.

    Returns:
        groups: list of {synset_ids, lemma_set, pos, count}
        target_synset_ids: set of all synset IDs needing full data
        target_lemmas: set of all normalized lemmas across groups
    """
    print(f"Phase 1: Loading prefilter report...")
    report = json.load(open(report_path, encoding='utf-8'))
    groups = report['duplicate_synsets']
    total_before = len(groups)

    # Apply filters (groups are already sorted desc by count)
    if min_count is not None:
        groups = [g for g in groups if g['count'] >= min_count]
    if top_n is not None:
        groups = groups[:top_n]

    target_synset_ids = set()
    target_lemmas = set()
    for g in groups:
        target_synset_ids.update(g['synset_ids'])
        target_lemmas.update(g['lemma_set'])

    print(f"  Total groups in report: {total_before}")
    if min_count is not None or top_n is not None:
        print(f"  After filters (top={top_n}, min_count={min_count}): {len(groups)}")
    print(f"  Target synsets: {len(target_synset_ids)}")
    print(f"  Target lemmas: {len(target_lemmas)}")
    return groups, target_synset_ids, target_lemmas


# ─── Phase 2: Parse AWN4 XML ────────────────────────────────────────────────

def parse_awn4_targeted(xml_path, target_synset_ids):
    """Stream-parse AWN4 XML, capturing full data for target synsets
    and minimal data (definition + lemmas) for all synsets (for hypernym lookups).

    Returns:
        synset_full: synset_id → {ili, pos, definitions, examples, relations, lemmas}
            (only for target synsets)
        synset_mini: synset_id → {definition, lemmas_raw}
            (for ALL synsets — used for hypernym context)
    """
    print(f"Phase 2: Parsing AWN4 XML (targeted)...")

    # Accumulate lemma→synset mappings during LexicalEntry parsing
    entry_lemmas = defaultdict(list)  # synset_id → [(raw, pos)]

    current_entry = None
    current_synset_id = None
    current_synset = None

    synset_count = 0
    entry_count = 0

    # First, collect all synset data + entry→synset mappings
    synset_raw = {}  # synset_id → {ili, pos, definitions, examples, relations}

    for event, elem in ET.iterparse(xml_path, events=('start', 'end')):
        tag = elem.tag

        if event == 'start':
            if tag == 'LexicalEntry':
                current_entry = {'lemma_raw': '', 'pos': '', 'synset_ids': []}
            elif tag == 'Synset':
                current_synset_id = elem.get('id')
                current_synset = {
                    'ili': elem.get('ili', ''),
                    'pos': elem.get('partOfSpeech', ''),
                    'definitions': [],
                    'examples': [],
                    'relations': [],
                }

        elif event == 'end':
            if tag == 'Lemma' and current_entry is not None:
                current_entry['lemma_raw'] = elem.get('writtenForm', '')
                current_entry['pos'] = elem.get('partOfSpeech', '')
            elif tag == 'Sense' and current_entry is not None:
                current_entry['synset_ids'].append(elem.get('synset', ''))
            elif tag == 'LexicalEntry' and current_entry is not None:
                entry_count += 1
                raw = current_entry['lemma_raw']
                pos = current_entry['pos']
                for sid in current_entry['synset_ids']:
                    entry_lemmas[sid].append((raw, pos))
                current_entry = None
            elif tag == 'Definition' and current_synset is not None:
                current_synset['definitions'].append(elem.text or '')
            elif tag == 'Example' and current_synset is not None:
                current_synset['examples'].append(elem.text or '')
            elif tag == 'SynsetRelation' and current_synset is not None:
                current_synset['relations'].append({
                    'relType': elem.get('relType', ''),
                    'target': elem.get('target', ''),
                })
            elif tag == 'Synset' and current_synset is not None:
                synset_count += 1
                synset_raw[current_synset_id] = current_synset
                current_synset_id = None
                current_synset = None

            elem.clear()

    # Now build the two output dicts
    synset_full = {}   # target synsets: full data
    synset_mini = {}   # all synsets: minimal data for hypernym lookups

    for sid, data in synset_raw.items():
        lemmas = entry_lemmas.get(sid, [])
        lemmas_raw = [raw for raw, pos in lemmas]
        first_def = data['definitions'][0] if data['definitions'] else ''

        # Mini version for all synsets (hypernym context)
        synset_mini[sid] = {
            'definition': first_def,
            'lemmas_raw': lemmas_raw,
        }

        # Full version only for targets
        if sid in target_synset_ids:
            synset_full[sid] = {
                'ili': data['ili'],
                'pos': data['pos'],
                'definitions': data['definitions'],
                'examples': data['examples'],
                'relations': data['relations'],
                'lemmas': [{'raw': raw, 'pos': pos} for raw, pos in lemmas],
            }

    print(f"  Parsed {entry_count} entries, {synset_count} synsets")
    print(f"  Full data for {len(synset_full)} target synsets")
    print(f"  Mini data for {len(synset_mini)} synsets (hypernym context)")
    return synset_full, synset_mini


# ─── Phase 3: Load Dictionary Evidence ──────────────────────────────────────

def load_dict_evidence(db_path, target_lemmas):
    """Load dictionary entries for target lemmas.

    Returns:
        dict_evidence: normalized_lemma → [entry dicts]
        stats: {total_queried, total_matched, total_entries}
    """
    print(f"Phase 3: Loading dictionary evidence...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA query_only = ON')

    cursor = conn.execute(
        "SELECT headword, headword_bare, root_joined, pos, definitions, examples, source "
        "FROM entries WHERE headword_bare <> ''"
    )

    # Build canonical → entries lookup
    db_lookup = defaultdict(list)
    total_rows = 0

    for row in cursor:
        total_rows += 1
        canonical = normalize_canonical(row['headword_bare'])
        if canonical and canonical in target_lemmas:
            defs = []
            if row['definitions']:
                try:
                    defs = json.loads(row['definitions'])
                except (json.JSONDecodeError, TypeError):
                    pass

            examples = []
            if row['examples']:
                try:
                    examples = json.loads(row['examples'])
                except (json.JSONDecodeError, TypeError):
                    pass

            db_lookup[canonical].append({
                'headword': row['headword'],
                'root': row['root_joined'] or '',
                'pos': row['pos'] or '',
                'source': friendly_source(row['source']),
                'definitions': defs[:5],    # cap at 5 definitions
                'examples': examples[:3],   # cap at 3 examples
            })

    conn.close()

    matched = sum(1 for l in target_lemmas if l in db_lookup)
    stats = {
        'total_db_rows': total_rows,
        'lemmas_queried': len(target_lemmas),
        'lemmas_matched': matched,
        'total_entries_returned': sum(len(v) for v in db_lookup.values()),
    }

    print(f"  DB rows scanned: {total_rows}")
    print(f"  Target lemmas with DB evidence: {matched}/{len(target_lemmas)} "
          f"({100*matched/max(len(target_lemmas),1):.1f}%)")
    return dict(db_lookup), stats


# ─── Phase 4: Assemble Evidence Packages ────────────────────────────────────

def assemble_packages(groups, synset_full, synset_mini, dict_evidence):
    """Assemble evidence packages for each polysemy group.

    Returns:
        packages: list of package dicts
        stats: assembly statistics
    """
    print(f"Phase 4: Assembling {len(groups)} evidence packages...")

    packages = []
    missing_synsets = 0
    hypernym_hits = 0
    hypernym_misses = 0

    for idx, group in enumerate(groups):
        synsets_data = []

        for sid in group['synset_ids']:
            full = synset_full.get(sid)
            if full is None:
                missing_synsets += 1
                continue

            # Find hypernym context
            hypernym_info = None
            for rel in full['relations']:
                if rel['relType'] == 'hypernym':
                    hyp_id = rel['target']
                    hyp_mini = synset_mini.get(hyp_id)
                    if hyp_mini:
                        hypernym_hits += 1
                        hypernym_info = {
                            'id': hyp_id,
                            'definition': hyp_mini['definition'],
                            'lemmas_raw': hyp_mini['lemmas_raw'],
                        }
                    else:
                        hypernym_misses += 1
                    break  # take first hypernym only

            synsets_data.append({
                'id': sid,
                'ili': full['ili'],
                'definitions': full['definitions'],
                'examples': full['examples'],
                'lemmas_raw': [l['raw'] for l in full['lemmas']],
                'hypernym': hypernym_info,
            })

        # Dictionary evidence for each lemma in the group
        group_dict_evidence = {}
        group_roots = set()
        for lemma in group['lemma_set']:
            entries = dict_evidence.get(lemma, [])
            if entries:
                group_dict_evidence[lemma] = entries
                for e in entries:
                    if e['root']:
                        group_roots.add(e['root'])

        packages.append({
            'group_id': idx,
            'lemma_set': group['lemma_set'],
            'pos': group['pos'],
            'count': group['count'],
            'synsets': synsets_data,
            'dictionary_evidence': group_dict_evidence,
            'root_family': sorted(group_roots),
        })

    stats = {
        'total_packages': len(packages),
        'missing_synsets': missing_synsets,
        'hypernym_hits': hypernym_hits,
        'hypernym_misses': hypernym_misses,
        'packages_with_dict_evidence': sum(
            1 for p in packages if p['dictionary_evidence']
        ),
    }

    print(f"  Packages assembled: {len(packages)}")
    print(f"  Synsets missing from XML: {missing_synsets}")
    print(f"  Hypernym context found: {hypernym_hits}, missing: {hypernym_misses}")
    print(f"  Packages with dictionary evidence: {stats['packages_with_dict_evidence']}")
    return packages, stats


# ─── Phase 5: Write Output ──────────────────────────────────────────────────

def write_output(packages, metadata, output_path):
    """Write the final JSON output."""
    print(f"Phase 5: Writing output...")

    output = {
        'metadata': metadata,
        'packages': packages,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=1)

    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"  Written to: {output_path}")
    print(f"  File size: {size_mb:.1f} MB")


# ─── Summary ─────────────────────────────────────────────────────────────────

def print_summary(packages, metadata):
    """Print a formatted summary of results."""
    print()
    print("=" * 60)
    print("POLYSEMY EVIDENCE PACKAGES — SUMMARY")
    print("=" * 60)

    m = metadata
    print(f"\nGroups processed:         {m['total_groups']:>8}")
    print(f"Total synsets covered:    {m['total_synsets']:>8}")
    print(f"Packages with dict data:  {m['packages_with_dict_evidence']:>8}"
          f"  ({100*m['packages_with_dict_evidence']/max(m['total_groups'],1):.1f}%)")
    print(f"Hypernym context found:   {m['hypernym_hits']:>8}"
          f"  ({100*m['hypernym_hits']/max(m['hypernym_hits']+m['hypernym_misses'],1):.1f}%)")
    print(f"Elapsed:                  {m['elapsed_seconds']:.1f}s")

    if m.get('filters_applied', {}).get('top') or m.get('filters_applied', {}).get('min_count'):
        f = m['filters_applied']
        print(f"\nFilters: top={f.get('top')}, min_count={f.get('min_count')}")

    # Show top 10 worst offenders
    print(f"\nTop 10 polysemy groups:")
    print(f"{'#':>3}  {'Count':>5}  {'POS':>3}  {'Dict?':>5}  Lemma(s)")
    print("-" * 60)
    for pkg in packages[:10]:
        has_dict = "Yes" if pkg['dictionary_evidence'] else "No"
        lemmas = ', '.join(pkg['lemma_set'])
        print(f"{pkg['group_id']:>3}  {pkg['count']:>5}  {pkg['pos']:>3}  {has_dict:>5}  {lemmas}")

    # Show a sample package for inspection
    if packages:
        print(f"\n--- Sample package (group 0) ---")
        pkg = packages[0]
        print(f"Lemma set: {pkg['lemma_set']}")
        print(f"POS: {pkg['pos']}, Count: {pkg['count']}")
        print(f"Roots: {pkg['root_family']}")
        for i, s in enumerate(pkg['synsets'][:3]):
            defs = s['definitions']
            def_preview = (defs[0][:80] + '...') if defs and len(defs[0]) > 80 else (defs[0] if defs else '(no def)')
            hyp = s['hypernym']
            hyp_str = f" → {hyp['lemmas_raw']}" if hyp else ""
            print(f"  [{i}] {s['id']}: {def_preview}{hyp_str}")
        if len(pkg['synsets']) > 3:
            print(f"  ... and {len(pkg['synsets']) - 3} more synsets")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build polysemy evidence packages for AWN4 duplicate-synset groups."
    )
    parser.add_argument('--prefilter', default=PREFILTER_REPORT,
                        help='Path to prefilter_report.json')
    parser.add_argument('--awn4-xml', default=AWN4_XML,
                        help='Path to AWN4 XML file')
    parser.add_argument('--dict-db', default=DICT_DB,
                        help='Path to Arabic dictionary SQLite DB')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help='Output JSON file path')
    parser.add_argument('--top', type=int, default=None,
                        help='Only process top N groups (by synset count)')
    parser.add_argument('--min-count', type=int, default=None,
                        help='Only process groups with >= N synsets')
    args = parser.parse_args()

    start = time.time()

    # Phase 1
    groups, target_synset_ids, target_lemmas = load_prefilter(
        args.prefilter, top_n=args.top, min_count=args.min_count
    )

    if not groups:
        print("No groups to process after filtering. Exiting.")
        sys.exit(0)

    # Phase 2
    synset_full, synset_mini = parse_awn4_targeted(args.awn4_xml, target_synset_ids)

    # Phase 3
    dict_evidence, dict_stats = load_dict_evidence(args.dict_db, target_lemmas)

    # Phase 4
    packages, assembly_stats = assemble_packages(
        groups, synset_full, synset_mini, dict_evidence
    )

    elapsed = time.time() - start

    # Build metadata
    metadata = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_groups': len(groups),
        'total_synsets': sum(g['count'] for g in groups),
        'filters_applied': {
            'top': args.top,
            'min_count': args.min_count,
        },
        'dict_stats': dict_stats,
        'packages_with_dict_evidence': assembly_stats['packages_with_dict_evidence'],
        'hypernym_hits': assembly_stats['hypernym_hits'],
        'hypernym_misses': assembly_stats['hypernym_misses'],
        'missing_synsets': assembly_stats['missing_synsets'],
        'elapsed_seconds': round(elapsed, 1),
    }

    # Phase 5
    write_output(packages, metadata, args.output)
    print_summary(packages, metadata)


if __name__ == '__main__':
    main()
