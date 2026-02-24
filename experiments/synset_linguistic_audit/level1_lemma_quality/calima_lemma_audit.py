#!/usr/bin/env python3
"""Level 1 Lemma Quality Audit: validate AWN4 lemmas against CALIMA Star MSA.

Runs 6 automated checks on every unique lemma in AWN4:
  1. CALIMA_NOT_RECOGNIZED — lemma not in CALIMA morphological DB
  2. POS_MISMATCH — AWN4 POS doesn't match any CALIMA analysis POS
  3. DIACRITICS_MISMATCH — AWN4 diacritized form differs from CALIMA canonical
  4. NO_ROOT — recognized but no root extracted
  5. NO_PATTERN — recognized but no morphological pattern extracted
  6. NON_CITATION_FORM — not in expected citation form for its POS

Usage:
    python experiments/synset_linguistic_audit/level1_lemma_quality/calima_lemma_audit.py
    python experiments/synset_linguistic_audit/level1_lemma_quality/calima_lemma_audit.py --limit 100
    python experiments/synset_linguistic_audit/level1_lemma_quality/calima_lemma_audit.py --flags-only
"""

import argparse
import json
import re
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
AWN4_BASE = SCRIPT_DIR.parent.parent.parent  # level1 → synset_linguistic_audit → experiments → arabic-wordnet-v4
AWN4_XML = str(AWN4_BASE / "output" / "awn4.xml")
DEFAULT_OUTPUT = str(SCRIPT_DIR / "output" / "calima_lemma_audit.json")

# ─── Normalization (reused from prefilter_dict.py) ───────────────────────────

DIACRITICS_RE = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')
TRAILING_DIGITS_RE = re.compile(r'\d+$')
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


def clean_form(text):
    """Clean AWN4 lemma form: strip trailing digits and tatweel."""
    t = text.strip()
    t = TRAILING_DIGITS_RE.sub('', t)
    t = t.replace('\u0640', '')  # tatweel
    return t


# ─── POS mapping: AWN4 → CALIMA ──────────────────────────────────────────────

AWN4_TO_CALIMA_POS = {
    'n': {'noun', 'noun_prop', 'noun_num', 'noun_quant'},
    'v': {'verb', 'verb_pseudo'},
    'a': {'adj', 'adj_comp', 'adj_num'},
    'r': {'adv', 'adv_interrog', 'adv_rel'},
}

# Fields to keep from CALIMA analyses (the rest are noise for linguist review)
KEEP_FIELDS = [
    'lex', 'root', 'pattern', 'pos', 'diac', 'gloss',
    'gen', 'num', 'per', 'asp', 'vox', 'stt', 'cas',
    'rat', 'source', 'bw', 'ud',
]

# ─── Phase 1: Initialize CALIMA ──────────────────────────────────────────────


def init_calima(db_name, cache_size):
    """Load CALIMA morphological DB and create Analyzer."""
    try:
        from camel_tools.morphology.database import MorphologyDB
        from camel_tools.morphology.analyzer import Analyzer
    except ImportError:
        print("ERROR: camel_tools not installed. Run: pip install camel_tools")
        print("       Then download data: camel_data -i morphology-db-msa-r13")
        sys.exit(1)

    try:
        db = MorphologyDB.builtin_db(db_name, flags='a')
    except Exception as e:
        print(f"ERROR: Could not load CALIMA DB '{db_name}': {e}")
        print("       Run: camel_data -i morphology-db-msa-r13")
        sys.exit(1)

    analyzer = Analyzer(db, backoff='NONE', cache_size=cache_size)
    return analyzer


# ─── Phase 2: Parse AWN4 XML ─────────────────────────────────────────────────


def parse_awn4_lemmas(xml_path):
    """Stream-parse AWN4 XML to extract unique lemmas and synset index.

    Returns:
        unique_lemmas: dict of (writtenForm, pos) → lemma info dict
        synset_index: dict of synset_id → list of lemma keys
        stats: parse statistics
    """
    # Accumulate lemmas keyed by (writtenForm, pos)
    unique_lemmas = {}
    synset_index = defaultdict(list)

    current_entry = None
    entry_count = 0
    synset_count = 0

    for event, elem in ET.iterparse(xml_path, events=('start', 'end')):
        tag = elem.tag

        if event == 'start':
            if tag == 'LexicalEntry':
                current_entry = {'lemma_raw': '', 'pos': '', 'synset_ids': []}
            elif tag == 'Synset':
                synset_count += 1

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
                key = f"{raw}||{pos}"

                if key not in unique_lemmas:
                    cleaned = clean_form(raw)
                    unique_lemmas[key] = {
                        'writtenForm': raw,
                        'pos': pos,
                        'synset_ids': list(current_entry['synset_ids']),
                        'has_diacritics': has_diacritics(raw),
                        'has_arabic': has_arabic(raw),
                        'is_multiword': ' ' in cleaned,
                        'cleaned_form': cleaned,
                    }
                else:
                    # Same lemma+pos in another LexicalEntry — merge synset IDs
                    for sid in current_entry['synset_ids']:
                        if sid not in unique_lemmas[key]['synset_ids']:
                            unique_lemmas[key]['synset_ids'].append(sid)

                # Build reverse index: synset → lemma keys
                for sid in current_entry['synset_ids']:
                    if key not in synset_index[sid]:
                        synset_index[sid].append(key)

                entry_count += 1
                current_entry = None

            elem.clear()

    stats = {
        'lexical_entries': entry_count,
        'synsets': synset_count,
        'unique_lemma_pos_pairs': len(unique_lemmas),
    }
    return unique_lemmas, dict(synset_index), stats


# ─── Phase 3 & 4: Analyze + Flag ─────────────────────────────────────────────


def strip_lex(lex):
    """Strip sense disambiguator from CALIMA lex field.

    CALIMA returns lex like 'كَتَبَ_1' or 'كِتَاب-1'. We want just the lemma.
    Reimplements camel_tools.morphology.utils.strip_lex to avoid import issues.
    """
    return re.split(r'[_\-]', lex)[0]


def simplify_analyses(analyses, max_per_reading=1):
    """Extract relevant fields and deduplicate CALIMA analyses.

    Deduplicates by (stripped_lex, pos) — each unique lemma+POS reading
    gets at most `max_per_reading` representative analysis entries.
    This collapses case/state inflection variants into a single entry.
    """
    # Group by (stripped_lex, pos) to find distinct readings
    readings = {}  # (stripped_lex, pos) → list of analysis dicts
    for a in analyses:
        lex = strip_lex(a.get('lex', ''))
        pos = a.get('pos', '')
        rkey = (lex, pos)
        if rkey not in readings:
            readings[rkey] = []
        if len(readings[rkey]) < max_per_reading:
            readings[rkey].append({k: a.get(k, '') for k in KEEP_FIELDS})

    # Flatten into a single list
    simplified = []
    for entries in readings.values():
        simplified.extend(entries)
    return simplified


def check_citation_form(awn4_pos, analyses):
    """Check if any analysis matches expected citation form.

    Returns: (is_ok, details_dict)
      - True: at least one analysis is in citation form
      - False: recognized but no citation form found
      - None: can't check (no analyses, or adverb)
    """
    if not analyses:
        return None, {}

    if awn4_pos == 'n':
        # Noun citation: indefinite singular
        noun_analyses = [a for a in analyses if a['pos'].startswith('noun')]
        if not noun_analyses:
            return None, {}
        for a in noun_analyses:
            if a.get('num') == 's' and a.get('stt') == 'i':
                return True, {}
        return False, {
            'expected': 'indefinite singular (num=s, stt=i)',
            'found_num': sorted({a.get('num', '?') for a in noun_analyses}),
            'found_stt': sorted({a.get('stt', '?') for a in noun_analyses}),
        }

    elif awn4_pos == 'v':
        # Verb citation: 3rd person masc singular perfective active
        verb_analyses = [a for a in analyses if a['pos'].startswith('verb')]
        if not verb_analyses:
            return None, {}
        for a in verb_analyses:
            if (a.get('per') == '3' and a.get('asp') == 'p' and
                    a.get('gen') == 'm' and a.get('num') == 's' and
                    a.get('vox') == 'a'):
                return True, {}
        return False, {
            'expected': '3ms perfective active (per=3, asp=p, gen=m, num=s, vox=a)',
            'found_per': sorted({a.get('per', '?') for a in verb_analyses}),
            'found_asp': sorted({a.get('asp', '?') for a in verb_analyses}),
            'found_gen': sorted({a.get('gen', '?') for a in verb_analyses}),
            'found_vox': sorted({a.get('vox', '?') for a in verb_analyses}),
        }

    elif awn4_pos == 'a':
        # Adjective citation: masculine singular
        adj_analyses = [a for a in analyses if a['pos'].startswith('adj')]
        if not adj_analyses:
            return None, {}
        for a in adj_analyses:
            if a.get('gen') == 'm' and a.get('num') == 's':
                return True, {}
        return False, {
            'expected': 'masculine singular (gen=m, num=s)',
            'found_gen': sorted({a.get('gen', '?') for a in adj_analyses}),
            'found_num': sorted({a.get('num', '?') for a in adj_analyses}),
        }

    # Adverbs: no standard citation form convention
    return None, {}


def analyze_single_word(analyzer, form):
    """Analyze a single word, with ال fallback."""
    analyses = analyzer.analyze(form)
    tried_without_al = False
    if not analyses and form.startswith('ال'):
        analyses = analyzer.analyze(form[2:])
        tried_without_al = True
    return analyses, tried_without_al


def audit_lemma(analyzer, lemma_info):
    """Run all Level 1 checks on a single lemma.

    Returns dict with full results and flags for linguist review.
    """
    form = lemma_info['cleaned_form']
    awn4_pos = lemma_info['pos']
    flags = []
    flag_details = {}

    # Skip non-Arabic lemmas
    if not lemma_info['has_arabic']:
        return {
            **_base_info(lemma_info),
            'calima_recognized': False,
            'flags': ['NON_ARABIC'],
            'flag_details': {},
            'analyses': [],
        }

    # ── Multi-word handling ───────────────────────────────────────────────
    if lemma_info['is_multiword']:
        flags.append('MULTIWORD_LEMMA')
        words = form.split()
        word_results = []
        all_recognized = True

        for w in words:
            w_analyses, _ = analyze_single_word(analyzer, w)
            w_simplified = simplify_analyses(w_analyses)
            recognized = len(w_analyses) > 0
            if not recognized:
                all_recognized = False
            word_results.append({
                'word': w,
                'recognized': recognized,
                'analysis_count': len(w_analyses),
                'deduplicated_count': len(w_simplified),
                'pos_values': sorted({a['pos'] for a in w_simplified}),
                'analyses': w_simplified,
            })

        if not all_recognized:
            flags.append('CALIMA_NOT_RECOGNIZED')
            flag_details['unrecognized_words'] = [
                wr['word'] for wr in word_results if not wr['recognized']
            ]

        return {
            **_base_info(lemma_info),
            'calima_recognized': all_recognized,
            'flags': flags,
            'flag_details': flag_details,
            'multiword_analyses': word_results,
            'analyses': [],  # no combined analysis for MWEs
        }

    # ── Single-word analysis ──────────────────────────────────────────────
    raw_analyses, tried_without_al = analyze_single_word(analyzer, form)
    recognized = len(raw_analyses) > 0

    # Flag 1: CALIMA_NOT_RECOGNIZED
    if not recognized:
        flags.append('CALIMA_NOT_RECOGNIZED')
        return {
            **_base_info(lemma_info),
            'calima_recognized': False,
            'analysis_count': 0,
            'deduplicated_analysis_count': 0,
            'tried_without_al': tried_without_al,
            'flags': flags,
            'flag_details': flag_details,
            'pos_match': None,
            'calima_pos_values': [],
            'roots': [],
            'patterns': [],
            'glosses': [],
            'citation_form_ok': None,
            'analyses': [],
        }

    # ── Extract summary fields from ALL raw analyses (for flag accuracy) ─
    calima_pos_set = {a.get('pos', '') for a in raw_analyses}
    roots = sorted({a.get('root', '') for a in raw_analyses
                    if a.get('root') and a['root'] not in ('', 'DIGIT', 'PUNC', 'FOREIGN')})
    patterns = sorted({a.get('pattern', '') for a in raw_analyses
                       if a.get('pattern') and a['pattern'] not in ('', 'DIGIT', 'PUNC', 'FOREIGN')})
    glosses = sorted({a.get('gloss', '') for a in raw_analyses if a.get('gloss')})
    sources = sorted({a.get('source', '') for a in raw_analyses if a.get('source')})

    # Flag 2: POS_MISMATCH
    expected_pos = AWN4_TO_CALIMA_POS.get(awn4_pos, set())
    pos_match = bool(expected_pos & calima_pos_set)
    if not pos_match and expected_pos:
        flags.append('POS_MISMATCH')
        flag_details['pos_mismatch'] = {
            'awn4_pos': awn4_pos,
            'expected_calima_pos': sorted(expected_pos),
            'actual_calima_pos': sorted(calima_pos_set),
        }

    # Flag 3: DIACRITICS_MISMATCH
    if lemma_info['has_diacritics']:
        awn4_form = form  # already cleaned (trailing digits, tatweel stripped)
        calima_lexes = set()
        for a in raw_analyses:
            lex = a.get('lex', '')
            if lex:
                calima_lexes.add(strip_lex(lex))

        # Compare: does AWN4 diacritized form match any CALIMA lex?
        if calima_lexes and awn4_form not in calima_lexes:
            # Also try stripping diacritics from both sides to confirm same base
            awn4_bare = strip_diacritics(awn4_form)
            calima_matching_base = [cl for cl in calima_lexes
                                    if strip_diacritics(cl) == awn4_bare]
            if calima_matching_base:
                # Same consonant skeleton, different diacritics
                flags.append('DIACRITICS_MISMATCH')
                flag_details['diacritics_mismatch'] = {
                    'awn4_diacritized': awn4_form,
                    'calima_lexes': sorted(calima_matching_base),
                }

    # Flag 4: NO_ROOT
    if not roots:
        flags.append('NO_ROOT')

    # Flag 5: NO_PATTERN
    if not patterns:
        flags.append('NO_PATTERN')

    # Flag 6: NON_CITATION_FORM — uses raw analyses (needs all inflections)
    citation_ok, citation_details = check_citation_form(awn4_pos, raw_analyses)
    if citation_ok is False:
        flags.append('NON_CITATION_FORM')
        flag_details['non_citation_form'] = citation_details

    # ── Build compact output (deduped by lex+pos, 1 per reading) ─────────
    analyses = simplify_analyses(raw_analyses)

    return {
        **_base_info(lemma_info),
        'calima_recognized': True,
        'analysis_count': len(raw_analyses),
        'deduplicated_analysis_count': len(analyses),
        'tried_without_al': tried_without_al,
        'flags': flags,
        'flag_details': flag_details,
        'pos_match': pos_match,
        'calima_pos_values': sorted(calima_pos_set),
        'roots': roots,
        'patterns': patterns,
        'glosses': glosses,
        'sources': sources,
        'citation_form_ok': citation_ok,
        'analyses': analyses,
    }


def _base_info(lemma_info):
    """Extract base fields from lemma_info for output."""
    return {
        'writtenForm': lemma_info['writtenForm'],
        'pos': lemma_info['pos'],
        'synset_ids': lemma_info['synset_ids'],
        'synset_count': len(lemma_info['synset_ids']),
        'has_diacritics': lemma_info['has_diacritics'],
        'is_multiword': lemma_info['is_multiword'],
        'cleaned_form': lemma_info['cleaned_form'],
    }


# ─── Phase 5: Summary + Report ───────────────────────────────────────────────


def build_summary(results):
    """Compute aggregate statistics from all lemma audit results."""
    total = len(results)
    recognized = sum(1 for r in results.values() if r.get('calima_recognized'))
    not_recognized = total - recognized

    # Flag counts
    flag_counts = defaultdict(int)
    for r in results.values():
        for f in r.get('flags', []):
            flag_counts[f] += 1

    # POS breakdown
    pos_breakdown = {}
    for pos_val in ('n', 'v', 'a', 'r'):
        pos_lemmas = {k: r for k, r in results.items() if r['pos'] == pos_val}
        pos_recog = sum(1 for r in pos_lemmas.values() if r.get('calima_recognized'))
        pos_flags = defaultdict(int)
        for r in pos_lemmas.values():
            for f in r.get('flags', []):
                pos_flags[f] += 1
        pos_breakdown[pos_val] = {
            'total': len(pos_lemmas),
            'recognized': pos_recog,
            'recognition_pct': round(pos_recog / len(pos_lemmas) * 100, 1) if pos_lemmas else 0,
            'flag_counts': dict(pos_flags),
        }

    # Root coverage
    all_roots = []
    for r in results.values():
        all_roots.extend(r.get('roots', []))
    root_counter = defaultdict(int)
    for root in all_roots:
        root_counter[root] += 1
    top_roots = sorted(root_counter.items(), key=lambda x: -x[1])[:20]

    # Pattern coverage
    all_patterns = []
    for r in results.values():
        all_patterns.extend(r.get('patterns', []))
    pattern_counter = defaultdict(int)
    for pat in all_patterns:
        pattern_counter[pat] += 1
    top_patterns = sorted(pattern_counter.items(), key=lambda x: -x[1])[:20]

    # Diacritics stats
    diac_lemmas = sum(1 for r in results.values() if r.get('has_diacritics'))
    diac_mismatches = flag_counts.get('DIACRITICS_MISMATCH', 0)

    # MWE stats
    mwe_count = sum(1 for r in results.values() if r.get('is_multiword'))

    return {
        'total_checked': total,
        'calima_recognized': recognized,
        'calima_not_recognized': not_recognized,
        'recognition_rate_pct': round(recognized / total * 100, 1) if total else 0,
        'flag_counts': dict(flag_counts),
        'pos_breakdown': pos_breakdown,
        'root_coverage': {
            'lemmas_with_root': sum(1 for r in results.values() if r.get('roots')),
            'unique_roots': len(root_counter),
            'top_20_roots': top_roots,
        },
        'pattern_coverage': {
            'lemmas_with_pattern': sum(1 for r in results.values() if r.get('patterns')),
            'unique_patterns': len(pattern_counter),
            'top_20_patterns': top_patterns,
        },
        'diacritics': {
            'lemmas_with_diacritics': diac_lemmas,
            'diacritics_mismatches': diac_mismatches,
        },
        'multiword': {
            'total_mwe': mwe_count,
        },
    }


def print_summary(summary, metadata, output_path):
    """Print formatted summary to stdout."""
    s = summary

    print()
    print('=' * 70)
    print('  AWN4 LEMMA QUALITY AUDIT (CALIMA STAR MSA)')
    print('=' * 70)
    print(f"  AWN4 lexical entries:  {metadata['total_lexical_entries']:>10,}")
    print(f"  Unique lemma+POS:      {metadata['unique_lemma_pos_pairs']:>10,}")
    print(f"  CALIMA database:       {metadata['calima_db']:>10}")
    print()
    print(f"  Recognized by CALIMA:  {s['calima_recognized']:>10,}  "
          f"({s['recognition_rate_pct']}%)")
    print(f"  Not recognized:        {s['calima_not_recognized']:>10,}  "
          f"({100 - s['recognition_rate_pct']:.1f}%)")
    print()
    print('  Flag breakdown:')
    for flag, count in sorted(s['flag_counts'].items(), key=lambda x: -x[1]):
        print(f"    {flag:<28s} {count:>8,}")
    print()
    print('  POS breakdown:')
    for pos, data in s['pos_breakdown'].items():
        t = data['total']
        r = data['recognized']
        pct = data['recognition_pct']
        print(f"    {pos}: {t:>8,} total, {r:>8,} recognized ({pct}%)")
    print()
    print(f"  Root coverage:     {s['root_coverage']['lemmas_with_root']:>8,} lemmas, "
          f"{s['root_coverage']['unique_roots']:>5,} unique roots")
    print(f"  Pattern coverage:  {s['pattern_coverage']['lemmas_with_pattern']:>8,} lemmas, "
          f"{s['pattern_coverage']['unique_patterns']:>5,} unique patterns")
    print(f"  Diacritized:       {s['diacritics']['lemmas_with_diacritics']:>8,} lemmas, "
          f"{s['diacritics']['diacritics_mismatches']:>5,} mismatches")
    print(f"  Multi-word:        {s['multiword']['total_mwe']:>8,} lemmas")
    print()
    print(f"  Elapsed: {metadata['elapsed_seconds']:.1f}s")
    print(f"  Report:  {output_path}")
    print('=' * 70)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description='Level 1 Lemma Quality Audit: validate AWN4 lemmas against CALIMA Star MSA.'
    )
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT,
                        help='Output JSON report path')
    parser.add_argument('--awn4-xml', default=AWN4_XML,
                        help='Path to awn4.xml')
    parser.add_argument('--calima-db', default='calima-msa-r13',
                        help='CALIMA database name (default: calima-msa-r13)')
    parser.add_argument('--cache-size', type=int, default=100000,
                        help='Analyzer LFU cache size (default: 100000)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Process only first N unique lemmas (for testing)')
    parser.add_argument('--flags-only', action='store_true',
                        help='Only include lemmas with at least one flag in output')
    args = parser.parse_args()

    t0 = time.time()

    # Phase 1: Initialize CALIMA
    print('Phase 1: Initializing CALIMA analyzer...')
    analyzer = init_calima(args.calima_db, args.cache_size)
    print(f'  Loaded {args.calima_db} (backoff=NONE, cache={args.cache_size:,})')

    # Phase 2: Parse AWN4 XML
    print('Phase 2: Parsing AWN4 XML...')
    unique_lemmas, synset_index, parse_stats = parse_awn4_lemmas(args.awn4_xml)
    print(f'  {parse_stats["lexical_entries"]:,} lexical entries, '
          f'{parse_stats["synsets"]:,} synsets, '
          f'{parse_stats["unique_lemma_pos_pairs"]:,} unique lemma+POS pairs')

    # Apply limit
    lemma_keys = list(unique_lemmas.keys())
    if args.limit:
        lemma_keys = lemma_keys[:args.limit]
        print(f'  --limit {args.limit}: processing first {len(lemma_keys)} lemmas')

    # Phase 3 & 4: Analyze + compute flags
    print(f'Phase 3-4: Analyzing {len(lemma_keys):,} lemmas against CALIMA...')
    results = {}
    for key in tqdm(lemma_keys, desc='Analyzing', unit='lemma'):
        lemma_info = unique_lemmas[key]
        results[key] = audit_lemma(analyzer, lemma_info)

    # Phase 5: Build summary + write report
    elapsed = time.time() - t0
    print('Phase 5: Building summary and writing report...')

    summary = build_summary(results)

    metadata = {
        'script': 'calima_lemma_audit.py',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'awn4_xml': args.awn4_xml,
        'calima_db': args.calima_db,
        'total_lexical_entries': parse_stats['lexical_entries'],
        'unique_lemma_pos_pairs': parse_stats['unique_lemma_pos_pairs'],
        'lemmas_audited': len(lemma_keys),
        'elapsed_seconds': round(elapsed, 1),
    }

    # Filter output if requested
    if args.flags_only:
        output_lemmas = {k: r for k, r in results.items() if r.get('flags')}
    else:
        output_lemmas = results

    # Filter synset_index to only audited synsets
    if args.limit:
        audited_synsets = set()
        for k in lemma_keys:
            for sid in unique_lemmas[k]['synset_ids']:
                audited_synsets.add(sid)
        filtered_index = {sid: keys for sid, keys in synset_index.items()
                          if sid in audited_synsets}
    else:
        filtered_index = synset_index

    report = {
        'metadata': metadata,
        'summary': summary,
        'synset_index': filtered_index,
        'lemmas': output_lemmas,
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    report_size = Path(args.output).stat().st_size / (1024 * 1024)
    metadata['report_size_mb'] = round(report_size, 1)

    print_summary(summary, metadata, args.output)

    if args.flags_only:
        print(f'\n  (--flags-only: {len(output_lemmas):,} of {len(results):,} lemmas in output)')


if __name__ == '__main__':
    main()
