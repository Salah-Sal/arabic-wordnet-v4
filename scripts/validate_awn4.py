#!/usr/bin/env python3
"""
AWN4 vs OEWN 2024 Systematic Validation

Loads both wordnets via the wn library and runs 8 systematic checks,
producing a structured report quantifying all discrepancies.

Usage:
    python scripts/validate_awn4.py
    python scripts/validate_awn4.py --save
    python scripts/validate_awn4.py --awn4-xml output/awn4.xml.gz
    python scripts/validate_awn4.py --output output/my_report.txt
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import wn

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_AWN4_XML = PROJECT_ROOT / "output" / "awn4.xml.gz"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "validation_report.txt"

INCLUDED_SYNSET_RELATIONS = {
    'hypernym', 'hyponym',
    'instance_hypernym', 'instance_hyponym',
    'mero_member', 'mero_part', 'mero_substance',
    'holo_member', 'holo_part', 'holo_substance',
    'entails', 'is_entailed_by',
    'causes', 'is_caused_by',
    'similar', 'also', 'attribute',
    'domain_topic', 'domain_region', 'has_domain_topic', 'has_domain_region',
    'exemplifies', 'is_exemplified_by',
}

ARABIC_UNICODE_RANGES = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
)


# ============================================================================
# ID Conversion
# ============================================================================

def oewn_to_awn4(oewn_id: str) -> str:
    return 'awn4-' + oewn_id[5:]


def awn4_to_oewn(awn4_id: str) -> str:
    return 'oewn-' + awn4_id[5:]


# ============================================================================
# Data Loading
# ============================================================================

def load_wordnets(awn4_xml_path: Path):
    """Load AWN4 and OEWN, return shared data structures."""
    print("Loading wordnets...")

    wn.add(str(awn4_xml_path))  # idempotent
    awn4 = wn.Wordnet('awn4:4.0', expand='')   # CRITICAL: expand='' avoids *INFERRED* relations
    oewn = wn.Wordnet('oewn:2024')

    print("  Collecting synset lists...")
    oewn_synsets = list(oewn.synsets())
    awn4_synsets = list(awn4.synsets())

    oewn_ids = {ss.id for ss in oewn_synsets}
    awn4_ids = {ss.id for ss in awn4_synsets}
    awn4_as_oewn = {'oewn-' + sid[5:] for sid in awn4_ids}

    oewn_ili_set = {ss.ili for ss in oewn_synsets if ss.ili is not None}

    print(f"  OEWN 2024: {len(oewn_synsets):,} synsets")
    print(f"  AWN4:      {len(awn4_synsets):,} synsets")
    print()

    return {
        'awn4': awn4,
        'oewn': oewn,
        'oewn_synsets': oewn_synsets,
        'awn4_synsets': awn4_synsets,
        'oewn_ids': oewn_ids,
        'awn4_ids': awn4_ids,
        'awn4_as_oewn': awn4_as_oewn,
        'oewn_ili_set': oewn_ili_set,
    }


# ============================================================================
# Union-Find for Check 8
# ============================================================================

class UnionFind:
    def __init__(self, nodes):
        self.parent = {n: n for n in nodes}
        self.rank = {n: 0 for n in nodes}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def components(self):
        groups = defaultdict(list)
        for node in self.parent:
            groups[self.find(node)].append(node)
        return dict(groups)


# ============================================================================
# Check Implementations
# ============================================================================

def check_1_synset_coverage(data: dict) -> dict:
    """Check 1: Synset Coverage — which OEWN synsets are missing from AWN4."""
    oewn_synsets = data['oewn_synsets']
    awn4_as_oewn = data['awn4_as_oewn']
    oewn_ids = data['oewn_ids']
    awn4_ids = data['awn4_ids']

    missing_oewn_ids = data['oewn_ids'] - awn4_as_oewn
    ghost_ids = awn4_as_oewn - oewn_ids  # AWN4 synsets whose OEWN source doesn't exist

    # POS breakdown
    oewn_pos_counts = Counter(ss.pos for ss in oewn_synsets)
    missing_by_pos = Counter()
    for sid in missing_oewn_ids:
        # Find the synset to get its POS
        pass
    # Build a fast lookup for OEWN synset POS
    oewn_pos_map = {ss.id: ss.pos for ss in oewn_synsets}
    for sid in missing_oewn_ids:
        missing_by_pos[oewn_pos_map[sid]] += 1

    awn4_pos_counts = Counter()
    oewn = data['oewn']
    for sid in awn4_as_oewn:
        if sid in oewn_ids:
            awn4_pos_counts[oewn_pos_map[sid]] += 1

    passed = len(ghost_ids) == 0

    return {
        'passed': passed,
        'oewn_total': len(oewn_synsets),
        'awn4_total': len(data['awn4_synsets']),
        'missing_count': len(missing_oewn_ids),
        'ghost_count': len(ghost_ids),
        'missing_by_pos': dict(missing_by_pos),
        'oewn_pos_counts': dict(oewn_pos_counts),
        'awn4_pos_counts': dict(awn4_pos_counts),
        'ghost_ids_sample': sorted(ghost_ids)[:10],
    }


def check_2_ili_integrity(data: dict) -> dict:
    """Check 2: ILI Integrity — validate ILI mappings."""
    awn4_synsets = data['awn4_synsets']
    oewn_ili_set = data['oewn_ili_set']
    oewn_ids = data['oewn_ids']
    awn4_as_oewn = data['awn4_as_oewn']

    # Build OEWN ILI map for cross-reference
    oewn_ili_map = {ss.id: ss.ili for ss in data['oewn_synsets']}

    invalid_ili = []
    data_loss = []  # AWN4 has no ILI but OEWN counterpart does
    both_no_ili = 0
    ili_values = []

    for ss in awn4_synsets:
        oewn_id = awn4_to_oewn(ss.id)
        awn4_ili = ss.ili

        if awn4_ili is not None:
            ili_values.append(awn4_ili)
            if awn4_ili not in oewn_ili_set:
                invalid_ili.append((ss.id, awn4_ili))
        else:
            # AWN4 has no ILI — check OEWN counterpart
            if oewn_id in oewn_ili_map:
                oewn_ili = oewn_ili_map[oewn_id]
                if oewn_ili is not None:
                    data_loss.append((ss.id, oewn_id, oewn_ili))
                else:
                    both_no_ili += 1

    ili_counter = Counter(ili_values)
    duplicates = {ili: cnt for ili, cnt in ili_counter.items() if cnt > 1}

    passed = len(invalid_ili) == 0 and len(duplicates) == 0 and len(data_loss) == 0

    return {
        'passed': passed,
        'total_with_ili': len(ili_values),
        'total_without_ili': sum(1 for ss in awn4_synsets if ss.ili is None),
        'invalid_ili_count': len(invalid_ili),
        'invalid_ili_sample': invalid_ili[:5],
        'duplicate_count': len(duplicates),
        'duplicate_sample': list(duplicates.items())[:5],
        'data_loss_count': len(data_loss),
        'data_loss_sample': data_loss[:5],
        'both_no_ili': both_no_ili,
    }


def check_3_relation_completeness(data: dict) -> dict:
    """Check 3: Relation Completeness — verify all applicable relations are copied."""
    awn4_synsets = data['awn4_synsets']
    oewn_synsets = data['oewn_synsets']
    awn4_ids = data['awn4_ids']
    awn4_as_oewn = data['awn4_as_oewn']
    oewn_ids = data['oewn_ids']

    print("  Building AWN4 relation index...")
    awn4_rel_index = set()
    bad_targets = []
    for ss in awn4_synsets:
        try:
            rels = ss.relations()
        except Exception:
            continue
        for rel_type, targets in rels.items():
            for tgt in targets:
                awn4_rel_index.add((ss.id, rel_type, tgt.id))
                if tgt.id not in awn4_ids:
                    bad_targets.append((ss.id, rel_type, tgt.id))

    print(f"  AWN4 relation index: {len(awn4_rel_index):,} triples")

    print("  Scanning OEWN for missing relations...")
    translated_oewn_ids = {awn4_to_oewn(sid) for sid in awn4_ids}

    skipped = 0    # target synset not translated into AWN4
    missing = []   # both sides translated but relation absent

    for ss in oewn_synsets:
        if ss.id not in translated_oewn_ids:
            continue
        awn4_src_id = oewn_to_awn4(ss.id)
        try:
            rels = ss.relations()
        except Exception:
            continue
        for rel_type, targets in rels.items():
            if rel_type not in INCLUDED_SYNSET_RELATIONS:
                continue
            for tgt in targets:
                if tgt.id not in translated_oewn_ids:
                    skipped += 1
                else:
                    awn4_tgt_id = oewn_to_awn4(tgt.id)
                    if (awn4_src_id, rel_type, awn4_tgt_id) not in awn4_rel_index:
                        missing.append((awn4_src_id, rel_type, awn4_tgt_id))

    passed = len(missing) == 0 and len(bad_targets) == 0

    return {
        'passed': passed,
        'awn4_relation_count': len(awn4_rel_index),
        'skipped_count': skipped,
        'missing_count': len(missing),
        'missing_sample': missing[:10],
        'bad_targets_count': len(bad_targets),
        'bad_targets_sample': bad_targets[:5],
    }


def check_4_definition_coverage(data: dict) -> dict:
    """Check 4: Definition and Example Coverage by POS."""
    awn4_synsets = data['awn4_synsets']

    pos_stats = defaultdict(lambda: {'total': 0, 'has_def': 0, 'has_ex': 0})
    synsets_no_def = []

    for ss in awn4_synsets:
        pos = ss.pos
        pos_stats[pos]['total'] += 1
        defs = ss.definitions()
        exs = ss.examples()
        if defs:
            pos_stats[pos]['has_def'] += 1
        else:
            synsets_no_def.append(ss.id)
        if exs:
            pos_stats[pos]['has_ex'] += 1

    passed = len(synsets_no_def) == 0

    return {
        'passed': passed,
        'pos_stats': dict(pos_stats),
        'no_def_count': len(synsets_no_def),
        'no_def_sample': synsets_no_def[:10],
    }


def check_5_pos_distribution(data: dict) -> dict:
    """Check 5: POS Distribution Comparison between OEWN and AWN4."""
    oewn_synsets = data['oewn_synsets']
    awn4_synsets = data['awn4_synsets']

    oewn_pos = Counter(ss.pos for ss in oewn_synsets)
    awn4_pos = Counter(ss.pos for ss in awn4_synsets)

    all_pos = sorted(set(oewn_pos) | set(awn4_pos))

    rows = []
    for pos in all_pos:
        oewn_cnt = oewn_pos.get(pos, 0)
        awn4_cnt = awn4_pos.get(pos, 0)
        pct = (awn4_cnt / oewn_cnt * 100) if oewn_cnt > 0 else 0.0
        gap = oewn_cnt - awn4_cnt
        rows.append({
            'pos': pos,
            'oewn': oewn_cnt,
            'awn4': awn4_cnt,
            'coverage_pct': pct,
            'gap': gap,
        })

    # PASS: primary POS {n,v,a,r} all present in AWN4
    primary_pos = {'n', 'v', 'a', 'r'}
    passed = all(awn4_pos.get(p, 0) > 0 for p in primary_pos)

    return {
        'passed': passed,
        'rows': rows,
        'oewn_pos': dict(oewn_pos),
        'awn4_pos': dict(awn4_pos),
    }


def check_6_arabic_text_quality(data: dict) -> dict:
    """Check 6: Arabic text quality — direction markers, non-Arabic lemmas, empty definitions."""
    awn4 = data['awn4']
    awn4_synsets = data['awn4_synsets']

    LRM = '\u200e'
    RLM = '\u200f'
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

    direction_marker_lemmas = []
    control_char_lemmas = []
    non_arabic_lemmas = []

    for word in awn4.words():
        lemma = word.lemma()
        if LRM in lemma or RLM in lemma:
            direction_marker_lemmas.append(lemma)
        if CONTROL_CHARS.search(lemma):
            control_char_lemmas.append(lemma)
        arabic_chars = ARABIC_UNICODE_RANGES.findall(lemma)
        if not arabic_chars:
            non_arabic_lemmas.append(lemma)

    # Check definitions for Arabic content
    defs_no_arabic = []
    for ss in awn4_synsets:
        for defn in ss.definitions():
            arabic_chars = ARABIC_UNICODE_RANGES.findall(defn)
            if not arabic_chars:
                defs_no_arabic.append((ss.id, defn[:80]))

    passed = len(direction_marker_lemmas) == 0 and len(control_char_lemmas) == 0

    return {
        'passed': passed,
        'direction_marker_count': len(direction_marker_lemmas),
        'direction_marker_sample': direction_marker_lemmas[:5],
        'control_char_count': len(control_char_lemmas),
        'control_char_sample': control_char_lemmas[:5],
        'non_arabic_lemma_count': len(non_arabic_lemmas),
        'non_arabic_lemma_sample': non_arabic_lemmas[:10],
        'defs_no_arabic_count': len(defs_no_arabic),
        'defs_no_arabic_sample': defs_no_arabic[:5],
    }


def check_7_id_format(data: dict) -> dict:
    """Check 7: ID Format Validity — verify all IDs match expected patterns."""
    awn4 = data['awn4']
    awn4_synsets = data['awn4_synsets']

    SYNSET_RE = re.compile(r'^awn4-\d{8}-[nvars]$')
    ENTRY_RE = re.compile(r'^awn4-e[a-f0-9]{12}$')
    SENSE_RE = re.compile(r'^awn4-s[a-f0-9]{12}$')

    bad_synset_ids = []
    bad_entry_ids = []
    bad_sense_ids = []

    for ss in awn4_synsets:
        if not SYNSET_RE.match(ss.id):
            bad_synset_ids.append(ss.id)

    for word in awn4.words():
        if not ENTRY_RE.match(word.id):
            bad_entry_ids.append(word.id)
        for sense in word.senses():
            if not SENSE_RE.match(sense.id):
                bad_sense_ids.append(sense.id)

    passed = len(bad_synset_ids) == 0 and len(bad_entry_ids) == 0 and len(bad_sense_ids) == 0

    return {
        'passed': passed,
        'bad_synset_ids_count': len(bad_synset_ids),
        'bad_synset_ids_sample': bad_synset_ids[:5],
        'bad_entry_ids_count': len(bad_entry_ids),
        'bad_entry_ids_sample': bad_entry_ids[:5],
        'bad_sense_ids_count': len(bad_sense_ids),
        'bad_sense_ids_sample': bad_sense_ids[:5],
    }


def check_8_noun_hierarchy(data: dict) -> dict:
    """Check 8: Noun Hierarchy Connectivity using Union-Find."""
    awn4_synsets = data['awn4_synsets']

    print("  Building noun hypernym graph...")
    noun_synsets = [ss for ss in awn4_synsets if ss.pos == 'n']
    noun_ids = {ss.id for ss in noun_synsets}

    uf = UnionFind(noun_ids)
    disconnected_roots = []  # nouns with no hypernym

    for ss in noun_synsets:
        try:
            rels = ss.relations()
        except Exception:
            continue
        has_hypernym = False
        for rel_type in ('hypernym', 'instance_hypernym'):
            for tgt in rels.get(rel_type, []):
                if tgt.id in noun_ids:
                    uf.union(ss.id, tgt.id)
                    has_hypernym = True
        if not has_hypernym:
            disconnected_roots.append(ss.id)

    components = uf.components()
    num_components = len(components)

    # Expected root
    EXPECTED_ROOT = 'awn4-00001740-n'
    root_component = None
    if EXPECTED_ROOT in noun_ids:
        root_rep = uf.find(EXPECTED_ROOT)
        root_component = components.get(root_rep, [])

    # Find the largest component
    largest_component_rep = max(components, key=lambda k: len(components[k]))
    largest_size = len(components[largest_component_rep])

    passed = num_components == 1

    return {
        'passed': passed,
        'noun_total': len(noun_synsets),
        'num_components': num_components,
        'largest_component_size': largest_size,
        'disconnected_roots_count': len(disconnected_roots),
        'disconnected_roots_sample': disconnected_roots[:10],
        'expected_root_present': EXPECTED_ROOT in noun_ids,
        'expected_root': EXPECTED_ROOT,
        'small_components': [
            (len(comps), sorted(comps)[:3])
            for rep, comps in sorted(components.items(), key=lambda kv: len(kv[1]))
            if len(comps) < 5
        ][:10],
    }


# ============================================================================
# Report Formatting
# ============================================================================

def format_report(results: dict) -> str:
    lines = []

    def section(title):
        lines.append('')
        lines.append(f'--- {title} ---')

    def rule():
        lines.append('=' * 60)

    rule()
    lines.append('=== AWN4 vs OEWN 2024 Validation Report ===')
    lines.append(f'Generated: {date.today()}')
    rule()

    # Check 1
    r = results['check_1']
    section('Check 1: Synset Coverage')
    lines.append(f"OEWN 2024 total synsets:  {r['oewn_total']:>10,}")
    lines.append(f"AWN4 total synsets:       {r['awn4_total']:>10,}")
    lines.append(f"Missing from AWN4:        {r['missing_count']:>10,}  "
                 f"({r['missing_count']/r['oewn_total']*100:.1f}%)")
    lines.append(f"Ghost synsets in AWN4:    {r['ghost_count']:>10,}")
    lines.append('')
    lines.append(f"  {'POS':<6} {'OEWN':>8} {'AWN4':>8} {'Missing':>8} {'Cover%':>8}")
    lines.append(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    all_pos = sorted(set(r['oewn_pos_counts']) | set(r['awn4_pos_counts']))
    for pos in all_pos:
        oewn_cnt = r['oewn_pos_counts'].get(pos, 0)
        awn4_cnt = r['awn4_pos_counts'].get(pos, 0)
        miss = r['missing_by_pos'].get(pos, 0)
        pct = (awn4_cnt / oewn_cnt * 100) if oewn_cnt > 0 else 0.0
        lines.append(f"  {pos:<6} {oewn_cnt:>8,} {awn4_cnt:>8,} {miss:>8,} {pct:>7.1f}%")
    if r['ghost_ids_sample']:
        lines.append(f"\n  Ghost IDs (first {len(r['ghost_ids_sample'])}): {r['ghost_ids_sample']}")

    # Check 2
    r = results['check_2']
    section('Check 2: ILI Integrity')
    lines.append(f"AWN4 synsets with ILI:    {r['total_with_ili']:>10,}")
    lines.append(f"AWN4 synsets without ILI: {r['total_without_ili']:>10,}")
    lines.append(f"Both sides lack ILI:      {r['both_no_ili']:>10,}")
    lines.append(f"Invalid ILI values:       {r['invalid_ili_count']:>10,}")
    lines.append(f"Duplicate ILIs:           {r['duplicate_count']:>10,}")
    lines.append(f"ILI data loss (OEWN has, AWN4 missing): {r['data_loss_count']:>4,}")
    if r['invalid_ili_sample']:
        lines.append(f"\n  Invalid ILI sample: {r['invalid_ili_sample']}")
    if r['data_loss_sample']:
        lines.append(f"\n  Data loss sample: {r['data_loss_sample'][:3]}")

    # Check 3
    r = results['check_3']
    section('Check 3: Relation Completeness')
    lines.append(f"AWN4 total relations:     {r['awn4_relation_count']:>10,}")
    lines.append(f"Skipped (target not translated): {r['skipped_count']:>5,}")
    lines.append(f"Truly missing relations:  {r['missing_count']:>10,}")
    lines.append(f"Bad relation targets:     {r['bad_targets_count']:>10,}")
    if r['missing_sample']:
        lines.append(f"\n  Missing sample: {r['missing_sample'][:3]}")
    if r['bad_targets_sample']:
        lines.append(f"\n  Bad targets sample: {r['bad_targets_sample'][:3]}")

    # Check 4
    r = results['check_4']
    section('Check 4: Definition and Example Coverage')
    lines.append(f"  {'POS':<6} {'Total':>8} {'HasDef':>8} {'HasEx':>8} {'Def%':>7} {'Ex%':>7}")
    lines.append(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*7}")
    for pos in sorted(r['pos_stats']):
        s = r['pos_stats'][pos]
        def_pct = s['has_def'] / s['total'] * 100 if s['total'] else 0
        ex_pct = s['has_ex'] / s['total'] * 100 if s['total'] else 0
        lines.append(f"  {pos:<6} {s['total']:>8,} {s['has_def']:>8,} "
                     f"{s['has_ex']:>8,} {def_pct:>6.1f}% {ex_pct:>6.1f}%")
    lines.append(f"\nSynsets without definition: {r['no_def_count']:,}")
    if r['no_def_sample']:
        lines.append(f"  Sample: {r['no_def_sample'][:5]}")

    # Check 5
    r = results['check_5']
    section('Check 5: POS Distribution Comparison')
    lines.append(f"  {'POS':<6} {'OEWN':>8} {'AWN4':>8} {'Cover%':>8} {'Gap':>8}")
    lines.append(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for row in r['rows']:
        note = ' (by design: not translated)' if row['pos'] == 's' and row['awn4'] == 0 else ''
        lines.append(f"  {row['pos']:<6} {row['oewn']:>8,} {row['awn4']:>8,} "
                     f"{row['coverage_pct']:>7.1f}% {row['gap']:>8,}{note}")

    # Check 6
    r = results['check_6']
    section('Check 6: Arabic Text Quality')
    lines.append(f"Direction marker lemmas:  {r['direction_marker_count']:>10,}")
    lines.append(f"Control char lemmas:      {r['control_char_count']:>10,}")
    lines.append(f"Non-Arabic lemmas (info): {r['non_arabic_lemma_count']:>10,}")
    lines.append(f"Defs without Arabic:      {r['defs_no_arabic_count']:>10,}")
    if r['direction_marker_sample']:
        lines.append(f"\n  Direction marker sample: {r['direction_marker_sample']}")
    if r['control_char_sample']:
        lines.append(f"\n  Control char sample: {r['control_char_sample']}")
    if r['non_arabic_lemma_sample']:
        lines.append(f"\n  Non-Arabic lemma sample: {r['non_arabic_lemma_sample'][:5]}")
    if r['defs_no_arabic_sample']:
        lines.append(f"\n  Defs without Arabic sample: {r['defs_no_arabic_sample'][:3]}")

    # Check 7
    r = results['check_7']
    section('Check 7: ID Format Validity')
    lines.append(f"Bad synset IDs:           {r['bad_synset_ids_count']:>10,}")
    lines.append(f"Bad entry IDs:            {r['bad_entry_ids_count']:>10,}")
    lines.append(f"Bad sense IDs:            {r['bad_sense_ids_count']:>10,}")
    if r['bad_synset_ids_sample']:
        lines.append(f"\n  Bad synset IDs: {r['bad_synset_ids_sample']}")
    if r['bad_entry_ids_sample']:
        lines.append(f"\n  Bad entry IDs: {r['bad_entry_ids_sample']}")
    if r['bad_sense_ids_sample']:
        lines.append(f"\n  Bad sense IDs: {r['bad_sense_ids_sample']}")

    # Check 8
    r = results['check_8']
    section('Check 8: Noun Hierarchy Connectivity')
    lines.append(f"Total noun synsets:       {r['noun_total']:>10,}")
    lines.append(f"Connected components:     {r['num_components']:>10,}")
    lines.append(f"Largest component:        {r['largest_component_size']:>10,}")
    lines.append(f"Disconnected roots:       {r['disconnected_roots_count']:>10,}")
    lines.append(f"Expected root present:    {'Yes' if r['expected_root_present'] else 'No':>10}")
    if r['small_components']:
        lines.append(f"\n  Small components (size < 5):")
        for size, sample in r['small_components']:
            lines.append(f"    size={size}: {sample}")

    # Summary
    lines.append('')
    rule()
    lines.append('=== Summary ===')
    check_labels = [
        ('check_1', 'Synset Coverage',
         f"(ghost={results['check_1']['ghost_count']}; "
         f"{results['check_1']['missing_count']:,} missing by design)"),
        ('check_2', 'ILI Integrity', ''),
        ('check_3', 'Relation Completeness', ''),
        ('check_4', 'Definition Coverage', ''),
        ('check_5', 'POS Distribution', ''),
        ('check_6', 'Arabic Text Quality', ''),
        ('check_7', 'ID Format Validity', ''),
        ('check_8', 'Noun Hierarchy Connectivity', ''),
    ]
    all_passed = True
    for key, label, note in check_labels:
        r = results[key]
        status = '[PASS]' if r['passed'] else '[FAIL]'
        if not r['passed']:
            all_passed = False
        lines.append(f"  {status} Check {key[-1]}: {label:<35} {note}")

    lines.append('')
    if all_passed:
        lines.append('Overall: ALL CHECKS PASSED')
    else:
        lines.append('Overall: SOME CHECKS FAILED')
    rule()

    return '\n'.join(lines)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Validate AWN4 against OEWN 2024 with 8 systematic checks.'
    )
    parser.add_argument(
        '--awn4-xml',
        type=Path,
        default=DEFAULT_AWN4_XML,
        help=f'Path to AWN4 XML (default: {DEFAULT_AWN4_XML})',
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help=f'Save report to {DEFAULT_OUTPUT}',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Save report to this path (implies --save)',
    )
    args = parser.parse_args()

    awn4_xml = args.awn4_xml
    if not awn4_xml.exists():
        print(f"ERROR: AWN4 XML not found: {awn4_xml}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or (DEFAULT_OUTPUT if args.save else None)

    # Load data once
    data = load_wordnets(awn4_xml)

    results = {}

    print("Running Check 1: Synset Coverage...")
    results['check_1'] = check_1_synset_coverage(data)

    print("Running Check 2: ILI Integrity...")
    results['check_2'] = check_2_ili_integrity(data)

    print("Running Check 3: Relation Completeness...")
    results['check_3'] = check_3_relation_completeness(data)

    print("Running Check 4: Definition Coverage...")
    results['check_4'] = check_4_definition_coverage(data)

    print("Running Check 5: POS Distribution...")
    results['check_5'] = check_5_pos_distribution(data)

    print("Running Check 6: Arabic Text Quality...")
    results['check_6'] = check_6_arabic_text_quality(data)

    print("Running Check 7: ID Format Validity...")
    results['check_7'] = check_7_id_format(data)

    print("Running Check 8: Noun Hierarchy Connectivity...")
    results['check_8'] = check_8_noun_hierarchy(data)

    print()
    report = format_report(results)
    print(report)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding='utf-8')
        print(f"\nReport saved to: {output_path}")

    all_passed = all(results[f'check_{i}']['passed'] for i in range(1, 9))
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
