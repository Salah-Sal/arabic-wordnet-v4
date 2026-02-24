#!/usr/bin/env python3
"""Pre-filter AWN4 synsets against the Arabic dictionary database.

Runs automated checks to flag mechanical errors before expensive LLM review.
Checks: LEMMA_NOT_FOUND, ALL_LEMMAS_MISSING, POS_MISMATCH,
        ROOT_INCONSISTENCY, DIACRITICS_MISMATCH, DUPLICATE_SYNSETS

Usage:
    python experiments/prefilter_dict.py
    python experiments/prefilter_dict.py --output custom_report.json
    python experiments/prefilter_dict.py --include-clean
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

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
AWN4_BASE = SCRIPT_DIR.parent.parent
AWN4_XML = str(AWN4_BASE / "output" / "awn4.xml")
DICT_DB = str(AWN4_BASE.parent / "arabic-dictionaries" / "extraction" / "db" / "arabic_dict.db")
DEFAULT_OUTPUT = str(SCRIPT_DIR / "prefilter_report.json")

# ─── Normalization ────────────────────────────────────────────────────────────

# Arabic diacritics: tashkeel (064B-065F), superscript alef (0670), Quranic marks (06D6-06ED)
DIACRITICS_RE = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')
TRAILING_DIGITS_RE = re.compile(r'\d+$')
ARTICLE_RE = re.compile(r'^ال\u0640?')
ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')


def strip_diacritics(text):
    """Remove Arabic tashkeel diacritics."""
    return DIACRITICS_RE.sub('', text)


def has_diacritics(text):
    """Check if text contains any Arabic diacritics."""
    return bool(DIACRITICS_RE.search(text))


def has_arabic(text):
    """Check if text contains at least one Arabic character."""
    return bool(ARABIC_RE.search(text))


def normalize_canonical(text):
    """Normalize to canonical match form for lookup.

    Applied to both AWN4 lemmas and DB headwords.
    Steps: strip diacritics, normalize alef/ya variants,
    remove tatweel, trailing digits, definite article.
    """
    t = strip_diacritics(text.strip())
    t = TRAILING_DIGITS_RE.sub('', t)
    # Alef normalization: أ إ آ → ا
    t = t.replace('\u0623', '\u0627')
    t = t.replace('\u0625', '\u0627')
    t = t.replace('\u0622', '\u0627')
    # Alef maqsura → ya: ى → ي
    t = t.replace('\u0649', '\u064A')
    # Remove tatweel
    t = t.replace('\u0640', '')
    # Strip definite article
    t = ARTICLE_RE.sub('', t)
    return t.strip()


# ─── POS mapping ──────────────────────────────────────────────────────────────

# AWN4 POS → set of compatible DB POS values
AWN4_TO_DB_POS = {
    'n': {'noun', 'proper_noun'},
    'v': {'verb'},
    'a': {'adj'},
    'r': set(),  # adverbs: skip POS check (not in classical dicts)
}

# ─── Phase 1: Load Dictionary DB ─────────────────────────────────────────────


def load_dictionary(db_path):
    """Load dictionary entries into memory for O(1) lookups.

    Returns:
        db_lookup: canonical_form → [{"headword", "headword_bare", "root_joined", "pos"}]
        db_raw_lookup: headword_bare → [{"headword", "headword_bare", "root_joined", "pos"}]
        stats: {"total_entries", "distinct_headwords"}
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA query_only = ON')

    cursor = conn.execute(
        "SELECT headword, headword_bare, root_joined, pos "
        "FROM entries WHERE headword_bare <> ''"
    )

    db_lookup = defaultdict(list)
    db_raw_lookup = defaultdict(list)
    total = 0

    for row in cursor:
        entry = {
            'headword': row['headword'],
            'headword_bare': row['headword_bare'],
            'root_joined': row['root_joined'],
            'pos': row['pos'],
        }
        total += 1

        canonical = normalize_canonical(row['headword_bare'])
        if canonical:
            db_lookup[canonical].append(entry)

        db_raw_lookup[row['headword_bare']].append(entry)

    conn.close()

    stats = {
        'total_entries': total,
        'distinct_canonical': len(db_lookup),
        'distinct_headwords': len(db_raw_lookup),
    }
    return dict(db_lookup), dict(db_raw_lookup), stats


# ─── Phase 2: Parse AWN4 XML ─────────────────────────────────────────────────


def parse_awn4(xml_path):
    """Stream-parse AWN4 XML.

    Returns:
        synset_lemmas: synset_id → [{"raw", "pos", "normalized"}]
        synset_data: synset_id → {"pos", "definition"}
    """
    synset_lemmas = defaultdict(list)
    synset_data = {}

    current_entry = None
    current_synset_id = None
    current_synset = None

    entry_count = 0
    synset_count = 0

    for event, elem in ET.iterparse(xml_path, events=('start', 'end')):
        tag = elem.tag

        if event == 'start':
            if tag == 'LexicalEntry':
                current_entry = {'lemma_raw': '', 'pos': '', 'synset_ids': []}
            elif tag == 'Synset':
                current_synset_id = elem.get('id')
                current_synset = {
                    'pos': elem.get('partOfSpeech', ''),
                    'definition': '',
                }

        elif event == 'end':
            if tag == 'Lemma' and current_entry is not None:
                current_entry['lemma_raw'] = elem.get('writtenForm', '')
                current_entry['pos'] = elem.get('partOfSpeech', '')

            elif tag == 'Sense' and current_entry is not None:
                sid = elem.get('synset', '')
                if sid:
                    current_entry['synset_ids'].append(sid)

            elif tag == 'LexicalEntry' and current_entry is not None:
                raw = current_entry['lemma_raw']
                pos = current_entry['pos']
                normalized = normalize_canonical(raw)
                for sid in current_entry['synset_ids']:
                    synset_lemmas[sid].append({
                        'raw': raw,
                        'pos': pos,
                        'normalized': normalized,
                    })
                entry_count += 1
                current_entry = None

            elif tag == 'Definition' and current_synset is not None:
                if not current_synset['definition']:
                    current_synset['definition'] = elem.text or ''

            elif tag == 'Synset' and current_synset is not None:
                synset_data[current_synset_id] = current_synset
                synset_count += 1
                current_synset_id = None
                current_synset = None

            elem.clear()

    stats = {'lexical_entries': entry_count, 'synsets': synset_count}
    return dict(synset_lemmas), synset_data, stats


# ─── Phase 3: Checks ─────────────────────────────────────────────────────────


def check_synset(synset_id, lemmas, synset_info, db_lookup, db_raw_lookup):
    """Run all checks on one synset. Returns (flags, lemma_results, details)."""
    flags = []
    details = []
    lemma_results = []

    # Classify lemmas
    checkable = []
    for lem in lemmas:
        raw = lem['raw']
        normalized = lem['normalized']
        is_arabic = has_arabic(raw)

        if not normalized or not is_arabic:
            lemma_results.append({
                'raw': raw,
                'normalized': normalized,
                'found_in_db': False,
                'db_match_count': 0,
                'skipped': True,
            })
            continue

        # Check 1: LEMMA_NOT_FOUND
        db_entries = db_lookup.get(normalized, [])
        found = len(db_entries) > 0

        lemma_results.append({
            'raw': raw,
            'normalized': normalized,
            'found_in_db': found,
            'db_match_count': len(db_entries),
            'skipped': False,
        })

        if not found:
            details.append({
                'flag': 'LEMMA_NOT_FOUND',
                'lemma': normalized,
                'lemma_raw': raw,
            })

        checkable.append({
            'raw': raw,
            'normalized': normalized,
            'pos': lem['pos'],
            'found': found,
            'db_entries': db_entries,
        })

    # Check 2: ALL_LEMMAS_MISSING / NO_ARABIC_LEMMAS
    if not checkable:
        flags.append('NO_ARABIC_LEMMAS')
        details.append({'flag': 'NO_ARABIC_LEMMAS'})
    elif all(not c['found'] for c in checkable):
        flags.append('ALL_LEMMAS_MISSING')
        details.append({'flag': 'ALL_LEMMAS_MISSING'})

    # Check 3: POS_MISMATCH
    synset_pos = synset_info.get('pos', '')
    expected_db_pos = AWN4_TO_DB_POS.get(synset_pos, set())

    if expected_db_pos:
        for c in checkable:
            if not c['found']:
                continue
            db_pos_set = {e['pos'] for e in c['db_entries']}
            if not (expected_db_pos & db_pos_set):
                flags.append('POS_MISMATCH')
                details.append({
                    'flag': 'POS_MISMATCH',
                    'lemma': c['normalized'],
                    'lemma_raw': c['raw'],
                    'awn4_pos': synset_pos,
                    'expected_db_pos': sorted(expected_db_pos),
                    'actual_db_pos': sorted(db_pos_set),
                })

    # Check 4: ROOT_INCONSISTENCY
    roots_by_lemma = {}
    for c in checkable:
        if not c['found']:
            continue
        roots = {e['root_joined'] for e in c['db_entries'] if e['root_joined']}
        if roots:
            roots_by_lemma[c['normalized']] = roots

    if len(roots_by_lemma) >= 2:
        all_root_sets = list(roots_by_lemma.values())
        common = all_root_sets[0].copy()
        for s in all_root_sets[1:]:
            common &= s
        if not common:
            flags.append('ROOT_INCONSISTENCY')
            details.append({
                'flag': 'ROOT_INCONSISTENCY',
                'roots_by_lemma': {k: sorted(v) for k, v in roots_by_lemma.items()},
            })

    # Check 5: DIACRITICS_MISMATCH
    for c in checkable:
        if not has_diacritics(c['raw']):
            continue

        # Look up by bare form (diacritics stripped, no alef normalization)
        bare = strip_diacritics(c['raw'].strip())
        bare = TRAILING_DIGITS_RE.sub('', bare)
        bare = bare.replace('\u0640', '')

        raw_entries = db_raw_lookup.get(bare, [])
        if not raw_entries and not bare.startswith('ال'):
            raw_entries = db_raw_lookup.get('ال' + bare, [])

        if not raw_entries:
            continue

        db_diacritized = {e['headword'] for e in raw_entries if has_diacritics(e['headword'])}
        if not db_diacritized:
            continue

        # Compare AWN4 form against all DB diacritized forms
        awn4_clean = c['raw'].strip()
        awn4_clean = TRAILING_DIGITS_RE.sub('', awn4_clean)
        awn4_no_article = ARTICLE_RE.sub('', strip_diacritics(awn4_clean))

        matched = False
        for db_form in db_diacritized:
            db_no_article = ARTICLE_RE.sub('', strip_diacritics(db_form))
            if strip_diacritics(awn4_clean) == strip_diacritics(db_form):
                # Same base form — compare diacritized versions
                if awn4_clean == db_form:
                    matched = True
                    break
                # Also try stripping article from both
                awn4_stripped = ARTICLE_RE.sub('', awn4_clean)
                db_stripped = ARTICLE_RE.sub('', db_form)
                if awn4_stripped == db_stripped:
                    matched = True
                    break

        if not matched:
            flags.append('DIACRITICS_MISMATCH')
            details.append({
                'flag': 'DIACRITICS_MISMATCH',
                'lemma_raw': c['raw'],
                'awn4_form': awn4_clean,
                'db_forms': sorted(db_diacritized)[:5],
            })

    # Deduplicate flags (POS_MISMATCH and DIACRITICS_MISMATCH can appear multiple times)
    unique_flags = list(dict.fromkeys(flags))

    return unique_flags, lemma_results, details


# ─── Phase 4: Duplicate Detection ────────────────────────────────────────────


def find_duplicate_synsets(synset_lemmas, synset_data):
    """Find synsets with identical normalized lemma sets."""
    fingerprint_to_synsets = defaultdict(list)

    for synset_id, lemmas in synset_lemmas.items():
        canonical_set = frozenset(
            lem['normalized'] for lem in lemmas if lem['normalized'] and has_arabic(lem['raw'])
        )
        if not canonical_set:
            continue
        pos = synset_data.get(synset_id, {}).get('pos', '?')
        fingerprint_to_synsets[(canonical_set, pos)].append(synset_id)

    duplicates = []
    for (fingerprint, pos), synset_ids in fingerprint_to_synsets.items():
        if len(synset_ids) > 1:
            duplicates.append({
                'synset_ids': sorted(synset_ids),
                'lemma_set': sorted(fingerprint),
                'pos': pos,
                'count': len(synset_ids),
            })

    duplicates.sort(key=lambda d: -d['count'])
    return duplicates


# ─── Phase 5: Report ─────────────────────────────────────────────────────────


def build_summary(results, synset_data, parse_stats, db_stats, duplicates):
    """Build summary statistics from check results."""
    total = len(synset_data)
    flagged = sum(1 for r in results.values() if r['flags'])
    clean = total - flagged

    # Count per-flag
    flag_counts = defaultdict(int)
    for r in results.values():
        for f in r['flags']:
            flag_counts[f] += 1
    # Also count per-lemma flags
    lemma_flag_counts = defaultdict(int)
    for r in results.values():
        for d in r['details']:
            lemma_flag_counts[d['flag']] += 1

    # Lemma coverage
    total_lemmas = 0
    found_lemmas = 0
    skipped_lemmas = 0
    for r in results.values():
        for lem in r['lemmas']:
            if lem.get('skipped'):
                skipped_lemmas += 1
            else:
                total_lemmas += 1
                if lem['found_in_db']:
                    found_lemmas += 1
    not_found = total_lemmas - found_lemmas

    # POS breakdown
    pos_breakdown = {}
    for pos_val in ('n', 'v', 'a', 'r'):
        pos_synsets = {sid for sid, sd in synset_data.items() if sd.get('pos') == pos_val}
        pos_flagged = sum(1 for sid in pos_synsets if sid in results and results[sid]['flags'])
        pos_breakdown[pos_val] = {
            'total_synsets': len(pos_synsets),
            'with_flags': pos_flagged,
        }

    return {
        'total_synsets': total,
        'synsets_with_flags': flagged,
        'synsets_clean': clean,
        'flag_counts_per_synset': dict(flag_counts),
        'flag_counts_per_instance': dict(lemma_flag_counts),
        'duplicate_groups': len(duplicates),
        'duplicate_synsets_total': sum(d['count'] for d in duplicates),
        'lemma_coverage': {
            'total_checkable': total_lemmas,
            'found_in_db': found_lemmas,
            'not_found': not_found,
            'skipped_non_arabic': skipped_lemmas,
            'coverage_pct': round(found_lemmas / total_lemmas * 100, 1) if total_lemmas else 0,
        },
        'pos_breakdown': pos_breakdown,
    }


def print_summary(summary, metadata, output_path):
    """Print formatted summary to stdout."""
    s = summary
    lc = s['lemma_coverage']

    print()
    print('=' * 70)
    print('  AWN4 DICTIONARY PRE-FILTER REPORT')
    print('=' * 70)
    print(f"  AWN4 synsets:          {metadata['awn4_synsets']:>10,}")
    print(f"  AWN4 lexical entries:  {metadata['awn4_lexical_entries']:>10,}")
    print(f"  Dictionary headwords:  {metadata['dict_distinct_headwords']:>10,}")
    print()
    print(f"  Synsets with flags:    {s['synsets_with_flags']:>10,}  "
          f"({s['synsets_with_flags']/s['total_synsets']*100:.1f}%)")
    print(f"  Synsets clean:         {s['synsets_clean']:>10,}  "
          f"({s['synsets_clean']/s['total_synsets']*100:.1f}%)")
    print()
    print('  Flag breakdown (per-synset):')
    for flag, count in sorted(s['flag_counts_per_synset'].items(), key=lambda x: -x[1]):
        print(f"    {flag:<28s} {count:>8,}")
    print()
    print('  Flag breakdown (per-instance):')
    for flag, count in sorted(s['flag_counts_per_instance'].items(), key=lambda x: -x[1]):
        print(f"    {flag:<28s} {count:>8,}")
    if s['duplicate_groups']:
        print(f"\n  Duplicate synset groups:   {s['duplicate_groups']:>6,}")
        print(f"  Synsets in duplicate groups:{s['duplicate_synsets_total']:>6,}")
    print()
    print('  Lemma coverage:')
    print(f"    Total checkable:       {lc['total_checkable']:>10,}")
    print(f"    Found in dictionary:   {lc['found_in_db']:>10,}  ({lc['coverage_pct']}%)")
    print(f"    Not found:             {lc['not_found']:>10,}  "
          f"({100-lc['coverage_pct']:.1f}%)")
    print(f"    Skipped (non-Arabic):  {lc['skipped_non_arabic']:>10,}")
    print()
    print('  POS breakdown:')
    for pos, data in s['pos_breakdown'].items():
        t = data['total_synsets']
        f = data['with_flags']
        pct = f / t * 100 if t else 0
        print(f"    {pos}: {t:>8,} total, {f:>8,} flagged ({pct:.1f}%)")
    print()
    print(f"  Elapsed: {metadata['elapsed_seconds']:.1f}s")
    print(f"  Report:  {output_path}")
    print('=' * 70)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description='Pre-filter AWN4 synsets against the Arabic dictionary database.'
    )
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT,
                        help='Output JSON report path')
    parser.add_argument('--awn4-xml', default=AWN4_XML,
                        help='Path to awn4.xml')
    parser.add_argument('--dict-db', default=DICT_DB,
                        help='Path to arabic_dict.db')
    parser.add_argument('--include-clean', action='store_true',
                        help='Include synsets with no flags in output')
    args = parser.parse_args()

    t0 = time.time()

    # Phase 1: Load dictionary
    print('Phase 1: Loading dictionary database...')
    db_lookup, db_raw_lookup, db_stats = load_dictionary(args.dict_db)
    print(f'  {db_stats["total_entries"]:,} entries, '
          f'{db_stats["distinct_canonical"]:,} canonical forms, '
          f'{db_stats["distinct_headwords"]:,} bare headwords')

    # Phase 2: Parse AWN4
    print('Phase 2: Parsing AWN4 XML...')
    synset_lemmas, synset_data, parse_stats = parse_awn4(args.awn4_xml)
    print(f'  {parse_stats["lexical_entries"]:,} lexical entries, '
          f'{parse_stats["synsets"]:,} synsets')

    # Phase 3: Run checks
    print('Phase 3: Running checks on synsets...')
    results = {}
    synset_ids = list(synset_data.keys())
    for sid in tqdm(synset_ids, desc='Checking', unit='synset'):
        lemmas = synset_lemmas.get(sid, [])
        synset_info = synset_data[sid]
        flags, lemma_results, details = check_synset(
            sid, lemmas, synset_info, db_lookup, db_raw_lookup
        )
        results[sid] = {
            'pos': synset_info.get('pos', ''),
            'flags': flags,
            'lemmas': lemma_results,
            'details': details,
        }

    # Phase 4: Duplicate detection
    print('Phase 4: Checking for duplicate synsets...')
    duplicates = find_duplicate_synsets(synset_lemmas, synset_data)

    # Phase 5: Build and write report
    elapsed = time.time() - t0

    metadata = {
        'script': 'prefilter_dict.py',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'awn4_xml': args.awn4_xml,
        'dict_db': args.dict_db,
        'awn4_synsets': parse_stats['synsets'],
        'awn4_lexical_entries': parse_stats['lexical_entries'],
        'dict_entries': db_stats['total_entries'],
        'dict_distinct_headwords': db_stats['distinct_headwords'],
        'elapsed_seconds': round(elapsed, 1),
    }

    summary = build_summary(results, synset_data, parse_stats, db_stats, duplicates)

    # Filter output
    if args.include_clean:
        synsets_output = results
    else:
        synsets_output = {sid: r for sid, r in results.items() if r['flags']}

    report = {
        'metadata': metadata,
        'summary': summary,
        'duplicate_synsets': duplicates,
        'synsets': synsets_output,
    }

    print(f'Phase 5: Writing report to {args.output}...')
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    report_size = Path(args.output).stat().st_size / (1024 * 1024)
    metadata['report_size_mb'] = round(report_size, 1)

    print_summary(summary, metadata, args.output)


if __name__ == '__main__':
    main()
