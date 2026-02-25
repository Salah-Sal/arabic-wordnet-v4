#!/usr/bin/env python3
"""Farasa Cross-Validation: independent second opinion on CALIMA audit flags.

Reads the CALIMA lemma audit JSON and runs Farasa NLP tools on flagged lemmas
to produce three-way verdicts (AWN4 vs CALIMA vs Farasa).

Three phases:
  A — Classify CALIMA_NOT_RECOGNIZED lemmas (stemmer + POS tagger + NER)
  B — Cross-validate DIACRITICS_MISMATCH (diacritizer as tie-breaker)
  C — Cross-validate POS_MISMATCH (POS tagger for three-way comparison)

Usage:
    python farasa_cross_validation.py --calima-results output/calima_lemma_audit.json
    python farasa_cross_validation.py --calima-results output/calima_lemma_audit.json --limit 10 --phase A
    python farasa_cross_validation.py --calima-results output/calima_lemma_audit.json --phase B C
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPOS_DIR = SCRIPT_DIR.parent / 'repos'
FARASAPY_DIR = REPOS_DIR / 'farasapy'
DEFAULT_CALIMA = str(SCRIPT_DIR / 'output' / 'calima_lemma_audit.json')
DEFAULT_OUTPUT = str(SCRIPT_DIR / 'output' / 'farasa_cross_validation.json')

# Ensure Java is on PATH (Homebrew keg-only install)
JAVA_HOMEBREW = '/opt/homebrew/opt/openjdk/bin'
if os.path.isdir(JAVA_HOMEBREW) and JAVA_HOMEBREW not in os.environ.get('PATH', ''):
    os.environ['PATH'] = JAVA_HOMEBREW + ':' + os.environ.get('PATH', '')

# ─── Normalization (reused from calima_lemma_audit.py) ────────────────────────

DIACRITICS_RE = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')
ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')
VERB_FINAL_FATHA_RE = re.compile(r'\u064E$')

ALEF_VARIANTS = {
    '\u0622': '\u0627',  # آ → ا
    '\u0623': '\u0627',  # أ → ا
    '\u0625': '\u0627',  # إ → ا
    '\u0671': '\u0627',  # ٱ → ا
}


def strip_diacritics(text):
    return DIACRITICS_RE.sub('', text)


def has_diacritics(text):
    return bool(DIACRITICS_RE.search(text))


def normalize_nfc(text):
    return unicodedata.normalize('NFC', text)


def normalize_alef(text):
    result = text
    for v, r in ALEF_VARIANTS.items():
        result = result.replace(v, r)
    return result


def strip_verb_final_fatha(form, pos):
    """Strip final fatha from verb citation forms (AWN4→CALIMA convention)."""
    if pos != 'v':
        return form, False
    if VERB_FINAL_FATHA_RE.search(form):
        return VERB_FINAL_FATHA_RE.sub('', form), True
    return form, False


# ─── Farasa POS → AWN4 POS mapping ───────────────────────────────────────────

FARASA_POS_TO_AWN4 = {
    # Farasa native tagset (interactive mode): CATEGORY[-features]
    # Features encode gender (M/F), number (S/P/D), etc.
    'NOUN': 'n', 'PROP': 'n', 'DET+NOUN': 'n', 'DET+PROP': 'n',
    'NUM': 'n',
    'V': 'v',
    'ADJ': 'a', 'DET+ADJ': 'a',
    'ADV': 'r',
    # Function words → None
    'PREP': None, 'CONJ': None, 'PART': None, 'PRON': None,
    'DET': None, 'PUNC': None, 'ABBREV': None,
    'S': None, 'E': None,  # sentence boundary markers
    # ATB-style tags (standalone mode fallback)
    'NN': 'n', 'NNS': 'n', 'NNP': 'n', 'NNPS': 'n',
    'DTNN': 'n', 'DTNNS': 'n', 'DTNNP': 'n', 'DTNNPS': 'n',
    'CD': 'n',
    'VB': 'v', 'VBD': 'v', 'VBN': 'v', 'VBP': 'v', 'VBG': 'v',
    'JJ': 'a', 'JJR': 'a', 'JJS': 'a', 'DTJJ': 'a', 'DTJJR': 'a',
    'RB': 'r', 'RBR': 'r', 'RBS': 'r', 'WRB': 'r',
    'IN': None, 'CC': None, 'PRP': None, 'PRP$': None,
    'WP': None, 'RP': None, 'UH': None,
}

PROPER_NOUN_TAGS = {'NNP', 'NNPS', 'DTNNP', 'DTNNPS', 'PROP', 'DET+PROP'}


def extract_primary_tag(raw_tag):
    """Extract primary POS from Farasa tag like 'NOUN-MS' or 'VBP+PVSUFF_SUBJ:3MS'.

    Farasa native tags: 'NOUN-MS' → 'NOUN', 'ADJ-FS' → 'ADJ', 'V' → 'V'
    ATB-style tags: 'VBP+PVSUFF_SUBJ:3MS' → 'VBP'
    """
    # Strip morphological features after '-' (native tagset: NOUN-MS → NOUN)
    tag = raw_tag.split('-')[0] if '-' in raw_tag else raw_tag
    # Strip compound suffixes after '+' (ATB: VBP+PVSUFF → VBP)
    tag = tag.split('+')[0]
    # Strip subtags after ':' (ATB: PVSUFF_SUBJ:3MS → PVSUFF_SUBJ)
    tag = tag.split(':')[0]
    return tag


def map_farasa_pos(raw_tag):
    """Map Farasa POS tag → (awn4_pos, is_proper_noun)."""
    primary = extract_primary_tag(raw_tag)
    return FARASA_POS_TO_AWN4.get(primary), primary in PROPER_NOUN_TAGS


# ─── Farasa output parsers ────────────────────────────────────────────────────

# Sentence boundary markers to filter out of POS output
_POS_BOUNDARY = {'<S>', '</S>', 'S/S', 'E/E'}


def parse_pos_output(raw):
    """Parse Farasa POS output → primary POS tag string.

    Handles two formats:
      Interactive: 'S/S token/TAG E/E'
      Standalone:  '<S> token/TAG </S>'
    """
    if not raw or not raw.strip():
        return None
    tokens = raw.strip().split()
    # Filter boundary markers and find tagged tokens
    tagged = [t for t in tokens if '/' in t and t not in _POS_BOUNDARY]
    if not tagged:
        return None
    # For single-word input, take the first real tagged token
    parts = tagged[0].rsplit('/', 1)
    return parts[1] if len(parts) == 2 else None


def parse_ner_output(raw):
    """Parse 'token/B-PER token/O ...' → first entity tag or 'O'."""
    if not raw or not raw.strip():
        return 'O'
    for tok in raw.strip().split():
        if '/' in tok:
            tag = tok.rsplit('/', 1)[1]
            if tag.startswith('B-') or tag.startswith('I-'):
                return tag
    return 'O'


# ─── FarasaToolManager ────────────────────────────────────────────────────────

class FarasaToolManager:
    """Lazy-initializing manager for Farasa interactive-mode tools."""

    def __init__(self, cache_dir=None):
        self._cache_dir = cache_dir
        self._stemmer = None
        self._pos_tagger = None
        self._ner = None
        self._diacritizer = None
        self._path_added = False

    def _ensure_path(self):
        if not self._path_added:
            fpath = str(FARASAPY_DIR)
            if fpath not in sys.path:
                sys.path.insert(0, fpath)
            self._path_added = True

    def _kwargs(self):
        kw = {'interactive': True, 'logging_level': 'WARNING'}
        if self._cache_dir:
            kw['cache_dir'] = self._cache_dir
        return kw

    def get_stemmer(self):
        if self._stemmer is None:
            self._ensure_path()
            from farasa.stemmer import FarasaStemmer
            self._stemmer = FarasaStemmer(**self._kwargs())
        return self._stemmer

    def get_pos_tagger(self):
        if self._pos_tagger is None:
            self._ensure_path()
            from farasa.pos import FarasaPOSTagger
            self._pos_tagger = FarasaPOSTagger(**self._kwargs())
        return self._pos_tagger

    def get_ner(self):
        if self._ner is None:
            self._ensure_path()
            from farasa.ner import FarasaNamedEntityRecognizer
            self._ner = FarasaNamedEntityRecognizer(**self._kwargs())
        return self._ner

    def get_diacritizer(self):
        if self._diacritizer is None:
            self._ensure_path()
            from farasa.diacratizer import FarasaDiacritizer
            self._diacritizer = FarasaDiacritizer(**self._kwargs())
        return self._diacritizer

    def terminate_all(self):
        for tool in [self._stemmer, self._pos_tagger, self._ner, self._diacritizer]:
            if tool is not None:
                try:
                    tool.terminate()
                except Exception:
                    pass


# ─── CheckpointManager ────────────────────────────────────────────────────────

class CheckpointManager:
    """Periodic checkpointing with atomic writes for crash recovery."""

    def __init__(self, output_path, interval=1000):
        self.output_path = Path(output_path)
        self.checkpoint_path = self.output_path.with_suffix('.checkpoint.json')
        self.interval = interval
        self._counter = 0

    def tick(self):
        self._counter += 1
        return self._counter % self.interval == 0

    def save(self, phase_results, current_phase, done_keys):
        tmp = self.checkpoint_path.with_suffix('.tmp')
        data = {
            'phase': current_phase,
            'done_keys': list(done_keys),
            'phase_results': phase_results,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(str(tmp), str(self.checkpoint_path))

    def load(self):
        if not self.checkpoint_path.exists():
            return None
        with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['phase_results'], data['phase'], set(data['done_keys'])

    def cleanup(self):
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()


# ─── Phase A: Classify CALIMA_NOT_RECOGNIZED ──────────────────────────────────

def classify_unrecognized(form, awn4_pos, has_diac, farasa_stem, farasa_pos_tag,
                          farasa_pos_mapped, farasa_ner_tag):
    """Classify an unrecognized lemma using Farasa signals."""
    stem_reduced = farasa_stem is not None and farasa_stem != form and farasa_stem != ''
    is_entity = farasa_ner_tag is not None and farasa_ner_tag.startswith('B-')
    entity_type = farasa_ner_tag.split('-')[1] if is_entity else None
    pos_meaningful = farasa_pos_mapped is not None
    pos_proper = farasa_pos_tag in PROPER_NOUN_TAGS if farasa_pos_tag else False

    # Rule 1: NER entity
    if is_entity:
        if stem_reduced:
            return 'PROPER_NOUN', 'HIGH', f'NER={farasa_ner_tag}, stem_reduced, type={entity_type}'
        return 'FOREIGN_PROPER_NOUN', 'HIGH', f'NER={farasa_ner_tag}, stem_not_reduced, type={entity_type}'

    # Rule 2: POS says proper noun
    if pos_proper:
        if stem_reduced:
            return 'PROPER_NOUN', 'MEDIUM', f'POS={farasa_pos_tag}(proper), stem_reduced'
        return 'FOREIGN_PROPER_NOUN', 'MEDIUM', f'POS={farasa_pos_tag}(proper), stem_not_reduced'

    # Rule 3: Farasa succeeds
    if stem_reduced and pos_meaningful:
        return 'CALIMA_COVERAGE_GAP', 'HIGH', f'stem={farasa_stem}, POS={farasa_pos_tag}->{farasa_pos_mapped}'
    if stem_reduced:
        return 'CALIMA_COVERAGE_GAP', 'MEDIUM', f'stem={farasa_stem}, POS_unmappable={farasa_pos_tag}'

    # Rule 4: No stem reduction
    if not stem_reduced and pos_meaningful:
        if farasa_pos_tag == 'NN' and not has_diac and awn4_pos == 'n':
            return 'HIGH_CONFIDENCE_FOREIGN', 'MEDIUM', f'stem_not_reduced, POS=NN(default), no_diac'
        return 'AMBIGUOUS', 'LOW', f'stem_not_reduced, POS={farasa_pos_tag}->{farasa_pos_mapped}'

    if not stem_reduced and not pos_meaningful:
        return 'HIGH_CONFIDENCE_FOREIGN', 'HIGH', f'stem_not_reduced, POS_unmappable={farasa_pos_tag}'

    return 'AMBIGUOUS', 'LOW', 'no_rule_matched'


def process_phase_a(key, lemma, tools):
    """Process one lemma for Phase A."""
    form = lemma['cleaned_form']
    result = {
        'writtenForm': lemma['writtenForm'],
        'pos': lemma['pos'],
        'synset_count': lemma.get('synset_count', len(lemma.get('synset_ids', []))),
        'has_diacritics': lemma.get('has_diacritics', False),
        'is_multiword': lemma.get('is_multiword', False),
        'farasa_stem': None,
        'stem_reduced': None,
        'farasa_pos_raw': None,
        'farasa_pos_tag': None,
        'farasa_pos_mapped': None,
        'farasa_pos_is_proper': None,
        'farasa_ner_raw': None,
        'farasa_ner_tag': None,
        'classification': None,
        'classification_confidence': None,
        'classification_reasoning': None,
        'suggested_pos': None,
        'error': None,
    }
    errors = []

    # Stemmer
    try:
        raw = tools.get_stemmer().stem(form)
        result['farasa_stem'] = raw.strip()
        result['stem_reduced'] = (result['farasa_stem'] != form)
    except Exception as e:
        errors.append(f'stemmer:{type(e).__name__}:{str(e)[:200]}')

    # POS tagger
    try:
        raw = tools.get_pos_tagger().tag(form)
        result['farasa_pos_raw'] = raw
        result['farasa_pos_tag'] = parse_pos_output(raw)
        if result['farasa_pos_tag']:
            mapped, is_proper = map_farasa_pos(result['farasa_pos_tag'])
            result['farasa_pos_mapped'] = mapped
            result['farasa_pos_is_proper'] = is_proper
    except Exception as e:
        errors.append(f'pos:{type(e).__name__}:{str(e)[:200]}')

    # NER
    try:
        raw = tools.get_ner().recognize(form)
        result['farasa_ner_raw'] = raw
        result['farasa_ner_tag'] = parse_ner_output(raw)
    except Exception as e:
        errors.append(f'ner:{type(e).__name__}:{str(e)[:200]}')
        result['farasa_ner_tag'] = 'O'

    # Classification
    if result['farasa_stem'] is not None or result['farasa_pos_tag'] is not None:
        cls, conf, reason = classify_unrecognized(
            form, lemma['pos'], lemma.get('has_diacritics', False),
            result.get('farasa_stem', form),
            result.get('farasa_pos_tag'),
            result.get('farasa_pos_mapped'),
            result.get('farasa_ner_tag', 'O'),
        )
        result['classification'] = cls
        result['classification_confidence'] = conf
        result['classification_reasoning'] = reason
        if result.get('farasa_pos_is_proper'):
            result['suggested_pos'] = 'noun_prop'
    else:
        result['classification'] = 'FARASA_FAILURE'

    if errors:
        result['error'] = '; '.join(errors)
    return result


# ─── Phase B: Cross-validate DIACRITICS_MISMATCH ─────────────────────────────

def compare_diacritics(awn4_form, calima_lexes, farasa_diac, pos):
    """Three-way diacritics comparison: AWN4 vs CALIMA vs Farasa."""
    awn4 = normalize_nfc(awn4_form)
    calima = [normalize_nfc(c) for c in calima_lexes]
    farasa = normalize_nfc(farasa_diac) if farasa_diac else None

    # Check verb final-fatha first
    awn4_stripped, was_stripped = strip_verb_final_fatha(awn4, pos)
    if was_stripped and any(awn4_stripped == c for c in calima):
        return {
            'is_verb_final_fatha': True,
            'verdict': 'VERB_FINAL_FATHA_ONLY',
            'verdict_confidence': 'HIGH',
            'agreement_pattern': 'verb_convention_diff',
        }

    # Exact comparisons
    awn4_calima_exact = any(awn4 == c for c in calima)
    awn4_farasa_exact = (farasa is not None and awn4 == farasa)
    calima_farasa_exact = (farasa is not None and any(farasa == c for c in calima))

    # Normalized comparisons (alef normalization)
    awn4_n = normalize_alef(awn4)
    calima_n = [normalize_alef(c) for c in calima]
    farasa_n = normalize_alef(farasa) if farasa else None

    awn4_calima_norm = any(awn4_n == c for c in calima_n)
    awn4_farasa_norm = (farasa_n is not None and awn4_n == farasa_n)
    calima_farasa_norm = (farasa_n is not None and any(farasa_n == c for c in calima_n))

    # Determine verdict
    if farasa is None:
        verdict = 'FARASA_FAILED'
        confidence = 'LOW'
        pattern = 'farasa_no_output'
    elif calima_farasa_norm and not awn4_farasa_norm:
        verdict = 'AWN4_LIKELY_WRONG'
        confidence = 'HIGH'
        pattern = 'calima_farasa_agree'
    elif awn4_farasa_norm and not calima_farasa_norm:
        verdict = 'CALIMA_LIKELY_WRONG'
        confidence = 'MEDIUM'
        pattern = 'awn4_farasa_agree'
    elif awn4_calima_norm:
        verdict = 'FALSE_POSITIVE'
        confidence = 'HIGH'
        pattern = 'awn4_calima_agree_normalized'
    else:
        verdict = 'ALL_THREE_DISAGREE'
        confidence = 'LOW'
        pattern = 'no_agreement'

    return {
        'is_verb_final_fatha': was_stripped,
        'awn4_vs_calima_exact': awn4_calima_exact,
        'awn4_vs_farasa_exact': awn4_farasa_exact,
        'calima_vs_farasa_exact': calima_farasa_exact,
        'awn4_vs_calima_norm': awn4_calima_norm,
        'awn4_vs_farasa_norm': awn4_farasa_norm,
        'calima_vs_farasa_norm': calima_farasa_norm,
        'verdict': verdict,
        'verdict_confidence': confidence,
        'agreement_pattern': pattern,
    }


def process_phase_b(key, lemma, tools):
    """Process one lemma for Phase B."""
    form = lemma.get('cleaned_form', lemma['writtenForm'])
    pos = lemma['pos']
    flag_details = lemma.get('flag_details', {})
    diac_info = flag_details.get('diacritics_mismatch', {})

    awn4_diac = diac_info.get('awn4_diacritized', form)
    calima_lexes = diac_info.get('calima_lexes', [])

    result = {
        'writtenForm': lemma['writtenForm'],
        'pos': pos,
        'synset_count': lemma.get('synset_count', len(lemma.get('synset_ids', []))),
        'has_diacritics': lemma.get('has_diacritics', False),
        'awn4_diacritized': awn4_diac,
        'calima_diacritized': calima_lexes,
        'undiacritized_form': strip_diacritics(awn4_diac),
        'farasa_diacritized': None,
        'comparison': None,
        'error': None,
    }

    # Check verb final-fatha early (skip diacritizer for these)
    awn4_stripped, is_fatha = strip_verb_final_fatha(normalize_nfc(awn4_diac), pos)
    if is_fatha and any(awn4_stripped == normalize_nfc(c) for c in calima_lexes):
        result['comparison'] = {
            'is_verb_final_fatha': True,
            'verdict': 'VERB_FINAL_FATHA_ONLY',
            'verdict_confidence': 'HIGH',
            'agreement_pattern': 'verb_convention_diff',
        }
        return result

    # Run Farasa diacritizer on the undiacritized form
    try:
        undiac = strip_diacritics(awn4_diac)
        raw = tools.get_diacritizer().diacritize(undiac)
        result['farasa_diacritized'] = raw.strip() if raw else None
    except Exception as e:
        result['error'] = f'diacritizer:{type(e).__name__}:{str(e)[:200]}'

    result['comparison'] = compare_diacritics(
        awn4_diac, calima_lexes, result['farasa_diacritized'], pos
    )
    return result


# ─── Phase C: Cross-validate POS_MISMATCH ────────────────────────────────────

def process_phase_c(key, lemma, tools):
    """Process one lemma for Phase C."""
    form = lemma.get('cleaned_form', lemma['writtenForm'])
    awn4_pos = lemma['pos']
    calima_pos_values = lemma.get('calima_pos_values', [])
    flag_details = lemma.get('flag_details', {})
    pos_info = flag_details.get('pos_mismatch', {})

    result = {
        'writtenForm': lemma['writtenForm'],
        'pos': awn4_pos,
        'synset_count': lemma.get('synset_count', len(lemma.get('synset_ids', []))),
        'awn4_pos': awn4_pos,
        'calima_pos_values': calima_pos_values,
        'calima_expected_pos': pos_info.get('expected_calima_pos', []),
        'calima_actual_pos': pos_info.get('actual_calima_pos', []),
        'farasa_pos_raw': None,
        'farasa_pos_tag': None,
        'farasa_pos_mapped': None,
        'farasa_pos_is_proper': None,
        'verdict': None,
        'verdict_confidence': None,
        'agreement_pattern': None,
        'error': None,
    }

    try:
        raw = tools.get_pos_tagger().tag(form)
        result['farasa_pos_raw'] = raw
        result['farasa_pos_tag'] = parse_pos_output(raw)
        if result['farasa_pos_tag']:
            mapped, is_proper = map_farasa_pos(result['farasa_pos_tag'])
            result['farasa_pos_mapped'] = mapped
            result['farasa_pos_is_proper'] = is_proper
    except Exception as e:
        result['error'] = f'pos:{type(e).__name__}:{str(e)[:200]}'

    # Three-way verdict
    farasa_mapped = result.get('farasa_pos_mapped')
    if farasa_mapped is None:
        result['verdict'] = 'FARASA_POS_UNMAPPABLE'
        result['verdict_confidence'] = 'LOW'
        result['agreement_pattern'] = f'farasa_tag={result.get("farasa_pos_tag")}'
    else:
        # Map CALIMA pos values to AWN4 categories for comparison
        calima_awn4_set = set()
        calima_to_awn4 = {
            'noun': 'n', 'noun_prop': 'n', 'noun_num': 'n', 'noun_quant': 'n',
            'verb': 'v', 'verb_pseudo': 'v',
            'adj': 'a', 'adj_comp': 'a', 'adj_num': 'a',
            'adv': 'r', 'adv_interrog': 'r', 'adv_rel': 'r',
        }
        for cp in calima_pos_values:
            mapped_cp = calima_to_awn4.get(cp)
            if mapped_cp:
                calima_awn4_set.add(mapped_cp)

        awn4_farasa_agree = (farasa_mapped == awn4_pos)
        calima_has_awn4 = (awn4_pos in calima_awn4_set)
        calima_has_farasa = (farasa_mapped in calima_awn4_set)

        if calima_has_farasa and not awn4_farasa_agree:
            result['verdict'] = 'AWN4_POS_LIKELY_WRONG'
            result['verdict_confidence'] = 'HIGH'
            result['agreement_pattern'] = 'calima_farasa_agree'
        elif awn4_farasa_agree and not calima_has_farasa:
            result['verdict'] = 'CALIMA_TAXONOMY_DIFFERENCE'
            result['verdict_confidence'] = 'HIGH'
            result['agreement_pattern'] = 'awn4_farasa_agree'
        elif awn4_farasa_agree and calima_has_farasa:
            # All three agree (shouldn't be POS_MISMATCH then, but possible with multi-POS)
            result['verdict'] = 'ALL_AGREE'
            result['verdict_confidence'] = 'HIGH'
            result['agreement_pattern'] = 'all_three_agree'
        else:
            result['verdict'] = 'AMBIGUOUS_POS'
            result['verdict_confidence'] = 'LOW'
            result['agreement_pattern'] = 'no_agreement'

    return result


# ─── Summary builder ──────────────────────────────────────────────────────────

def build_summary(phase_a, phase_b, phase_c):
    """Build aggregate summary statistics from phase results."""
    summary = {}

    if phase_a is not None:
        classifications = Counter()
        confidences = Counter()
        ner_tags = Counter()
        stem_reduced_count = 0
        errors = 0
        for r in phase_a.values():
            if r.get('classification'):
                classifications[r['classification']] += 1
            if r.get('classification_confidence'):
                confidences[r['classification_confidence']] += 1
            if r.get('farasa_ner_tag'):
                ner_tags[r['farasa_ner_tag']] += 1
            if r.get('stem_reduced'):
                stem_reduced_count += 1
            if r.get('error'):
                errors += 1
        summary['phase_a'] = {
            'total': len(phase_a),
            'classifications': dict(classifications.most_common()),
            'classification_confidence': dict(confidences.most_common()),
            'ner_breakdown': dict(ner_tags.most_common()),
            'stem_reduction_count': stem_reduced_count,
            'stem_reduction_pct': round(100 * stem_reduced_count / max(len(phase_a), 1), 1),
            'errors': errors,
        }

    if phase_b is not None:
        verdicts = Counter()
        confidences = Counter()
        verb_fatha = 0
        errors = 0
        for r in phase_b.values():
            comp = r.get('comparison', {})
            v = comp.get('verdict')
            if v:
                verdicts[v] += 1
            c = comp.get('verdict_confidence')
            if c:
                confidences[c] += 1
            if comp.get('is_verb_final_fatha'):
                verb_fatha += 1
            if r.get('error'):
                errors += 1
        summary['phase_b'] = {
            'total': len(phase_b),
            'verdicts': dict(verdicts.most_common()),
            'verdict_confidence': dict(confidences.most_common()),
            'verb_final_fatha_count': verb_fatha,
            'errors': errors,
        }

    if phase_c is not None:
        verdicts = Counter()
        confidences = Counter()
        errors = 0
        for r in phase_c.values():
            v = r.get('verdict')
            if v:
                verdicts[v] += 1
            c = r.get('verdict_confidence')
            if c:
                confidences[c] += 1
            if r.get('error'):
                errors += 1
        summary['phase_c'] = {
            'total': len(phase_c),
            'verdicts': dict(verdicts.most_common()),
            'verdict_confidence': dict(confidences.most_common()),
            'errors': errors,
        }

    return summary


def print_summary(summary, metadata, output_path):
    print()
    print('=' * 70)
    print('  FARASA CROSS-VALIDATION SUMMARY')
    print('=' * 70)
    for phase_key in ['phase_a', 'phase_b', 'phase_c']:
        if phase_key not in summary:
            continue
        s = summary[phase_key]
        label = {'phase_a': 'A: Unrecognized', 'phase_b': 'B: Diacritics', 'phase_c': 'C: POS'}[phase_key]
        print(f'\n  Phase {label} — {s["total"]:,} lemmas')
        if 'classifications' in s:
            for k, v in s['classifications'].items():
                print(f'    {k:30s} {v:>6,}')
        if 'verdicts' in s:
            for k, v in s['verdicts'].items():
                print(f'    {k:30s} {v:>6,}')
        if s.get('errors'):
            print(f'    {"ERRORS":30s} {s["errors"]:>6,}')
    print(f'\n  Elapsed: {metadata["elapsed_seconds"]:.1f}s')
    print(f'  Output:  {output_path}')
    print('=' * 70)


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(args):
    t0 = time.time()

    # Load CALIMA results
    print(f'Loading CALIMA results from {args.calima_results}...')
    with open(args.calima_results, 'r', encoding='utf-8') as f:
        calima_data = json.load(f)
    all_lemmas = calima_data['lemmas']
    print(f'  Loaded {len(all_lemmas):,} lemmas')

    # Checkpoint
    ckpt = CheckpointManager(args.output, args.checkpoint_interval)
    existing = ckpt.load()
    if existing:
        saved_results, saved_phase, _done_keys = existing
        done_count = sum(len(v) for v in saved_results.values() if isinstance(v, dict))
        print(f'  Resuming from checkpoint: phase={saved_phase}, {done_count} done')
    else:
        saved_results = {}
        saved_phase = None

    # Initialize results per phase
    phase_a_results = saved_results.get('phase_a', {}) if saved_phase else {}
    phase_b_results = saved_results.get('phase_b', {}) if saved_phase else {}
    phase_c_results = saved_results.get('phase_c', {}) if saved_phase else {}

    tools = FarasaToolManager(cache_dir=args.farasa_cache_dir)
    phases = args.phase

    try:
        # ── Phase A ──
        if 'A' in phases:
            subset = {k: v for k, v in all_lemmas.items()
                      if 'CALIMA_NOT_RECOGNIZED' in v.get('flags', [])
                      and (args.include_multiword or not v.get('is_multiword', False))}
            keys = sorted(subset.keys())
            if args.limit:
                keys = keys[:args.limit]
            print(f'\nPhase A: Classifying {len(keys):,} unrecognized lemmas...')
            for key in tqdm(keys, desc='Phase A', unit='lemma'):
                if key in phase_a_results:
                    continue
                phase_a_results[key] = process_phase_a(key, subset[key], tools)
                if ckpt.tick():
                    ckpt.save({'phase_a': phase_a_results, 'phase_b': phase_b_results, 'phase_c': phase_c_results}, 'A', set())
            ckpt.save({'phase_a': phase_a_results, 'phase_b': phase_b_results, 'phase_c': phase_c_results}, 'A_done', set())
            print(f'  Phase A complete: {len(phase_a_results):,} lemmas')

        # ── Phase B ──
        if 'B' in phases:
            subset = {k: v for k, v in all_lemmas.items()
                      if 'DIACRITICS_MISMATCH' in v.get('flags', [])}
            keys = sorted(subset.keys())
            if args.limit:
                keys = keys[:args.limit]
            print(f'\nPhase B: Cross-validating {len(keys):,} diacritics mismatches...')
            for key in tqdm(keys, desc='Phase B', unit='lemma'):
                if key in phase_b_results:
                    continue
                phase_b_results[key] = process_phase_b(key, subset[key], tools)
                if ckpt.tick():
                    ckpt.save({'phase_a': phase_a_results, 'phase_b': phase_b_results, 'phase_c': phase_c_results}, 'B', set())
            ckpt.save({'phase_a': phase_a_results, 'phase_b': phase_b_results, 'phase_c': phase_c_results}, 'B_done', set())
            print(f'  Phase B complete: {len(phase_b_results):,} lemmas')

        # ── Phase C ──
        if 'C' in phases:
            subset = {k: v for k, v in all_lemmas.items()
                      if 'POS_MISMATCH' in v.get('flags', [])}
            keys = sorted(subset.keys())
            if args.limit:
                keys = keys[:args.limit]
            print(f'\nPhase C: Cross-validating {len(keys):,} POS mismatches...')
            for key in tqdm(keys, desc='Phase C', unit='lemma'):
                if key in phase_c_results:
                    continue
                phase_c_results[key] = process_phase_c(key, subset[key], tools)
                if ckpt.tick():
                    ckpt.save({'phase_a': phase_a_results, 'phase_b': phase_b_results, 'phase_c': phase_c_results}, 'C', set())
            ckpt.save({'phase_a': phase_a_results, 'phase_b': phase_b_results, 'phase_c': phase_c_results}, 'C_done', set())
            print(f'  Phase C complete: {len(phase_c_results):,} lemmas')

    finally:
        tools.terminate_all()

    # Build output
    elapsed = time.time() - t0
    tools_used = []
    if 'A' in phases:
        tools_used.extend(['stemmer', 'pos_tagger', 'ner'])
    if 'B' in phases:
        tools_used.append('diacritizer')
    if 'C' in phases and 'pos_tagger' not in tools_used:
        tools_used.append('pos_tagger')

    summary = build_summary(
        phase_a_results if 'A' in phases else None,
        phase_b_results if 'B' in phases else None,
        phase_c_results if 'C' in phases else None,
    )

    metadata = {
        'script': 'farasa_cross_validation.py',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'calima_results_path': str(args.calima_results),
        'calima_audit_timestamp': calima_data.get('metadata', {}).get('timestamp'),
        'phases_run': phases,
        'farasa_tools_used': tools_used,
        'total_lemmas_processed': len(phase_a_results) + len(phase_b_results) + len(phase_c_results),
        'elapsed_seconds': round(elapsed, 1),
        'checkpoint_interval': args.checkpoint_interval,
    }

    output = {
        'metadata': metadata,
        'summary': summary,
    }
    if phase_a_results:
        output['phase_a_lemmas'] = phase_a_results
    if phase_b_results:
        output['phase_b_lemmas'] = phase_b_results
    if phase_c_results:
        output['phase_c_lemmas'] = phase_c_results

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ckpt.cleanup()
    print_summary(summary, metadata, args.output)


def main():
    parser = argparse.ArgumentParser(
        description='Cross-validate AWN4 lemma quality flags using Farasa NLP tools.'
    )
    parser.add_argument('--calima-results', type=str, default=DEFAULT_CALIMA,
                        help='Path to calima_lemma_audit.json')
    parser.add_argument('-o', '--output', type=str, default=DEFAULT_OUTPUT,
                        help='Output JSON path')
    parser.add_argument('--phase', nargs='+', choices=['A', 'B', 'C', 'all'],
                        default=['all'],
                        help='Which phases to run (default: all)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Process only first N lemmas per phase (testing)')
    parser.add_argument('--checkpoint-interval', type=int, default=1000,
                        help='Save checkpoint every N lemmas (default: 1000)')
    parser.add_argument('--include-multiword', action='store_true',
                        help='Include multiword lemmas in Phase A')
    parser.add_argument('--farasa-cache-dir', type=str, default=None,
                        help='Custom cache directory for Farasa')
    args = parser.parse_args()

    if 'all' in args.phase:
        args.phase = ['A', 'B', 'C']

    run_pipeline(args)


if __name__ == '__main__':
    main()
