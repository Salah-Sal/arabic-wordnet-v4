#!/usr/bin/env python3
"""
Convert Arabic WordNet translations to WN-LMF 1.4 XML format.

This script:
1. Loads Arabic translations from batch files
2. Gets ILI mappings and SynsetRelations from OEWN via wn library
3. Generates stable IDs using deterministic hashing
4. Outputs WN-LMF 1.4 compliant XML

Usage:
    python convert_to_lmf.py [--output OUTPUT_PATH]
"""

import argparse
import hashlib
import json
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import wn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

LEXICON_ID = "awn4"
LEXICON_LABEL = "Arabic WordNet 4.0"
LANGUAGE = "arb"  # BCP-47 for Modern Standard Arabic
VERSION = "4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
EMAIL = "contact@example.com"  # Update with actual email
PROJECT_URL = "https://github.com/Salah-Sal/arabic-wordnet-v4"
CITATION = "Arabic WordNet 4.0 (2024). A Comprehensive Arabic Lexical Database."

# Path to Arabic translations (relative to this script)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
AR_BATCHES_DIR = PROJECT_ROOT.parent / "arabic-wordnet-awn3" / "data" / "output" / "batches_750_ar"
OUTPUT_DIR = PROJECT_ROOT / "output"

# SynsetRelations to include (semantic, language-independent)
INCLUDED_SYNSET_RELATIONS = {
    'hypernym', 'hyponym',
    'instance_hypernym', 'instance_hyponym',
    'mero_member', 'mero_part', 'mero_substance',
    'holo_member', 'holo_part', 'holo_substance',
    'entails', 'is_entailed_by',
    'causes', 'is_caused_by',
    'similar', 'also', 'attribute',
    'domain_topic', 'domain_region', 'has_domain_topic', 'has_domain_region',
    'exemplifies', 'is_exemplified_by'
}

# ============================================================================
# ID Generation (Deterministic Hashing)
# ============================================================================

def generate_entry_id(lemma: str, pos: str) -> str:
    """Generate stable, deterministic entry ID from lemma+POS."""
    key = f"{lemma}:{pos}"
    hash_suffix = hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]
    return f"{LEXICON_ID}-e{hash_suffix}"


def generate_sense_id(lemma: str, synset_id: str) -> str:
    """Generate stable, deterministic sense ID from lemma+synset."""
    key = f"{lemma}:{synset_id}"
    hash_suffix = hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]
    return f"{LEXICON_ID}-s{hash_suffix}"


def convert_synset_id(oewn_id: str) -> str:
    """Convert OEWN synset ID to AWN4 format.

    Example: oewn-00001740-n -> awn4-00001740-n
    """
    if oewn_id.startswith('oewn-'):
        return f"{LEXICON_ID}-{oewn_id[5:]}"
    return f"{LEXICON_ID}-{oewn_id}"


# ============================================================================
# Arabic Text Validation
# ============================================================================

def validate_arabic_text(text: str) -> list:
    """Check for common Arabic text issues."""
    issues = []

    if not text:
        return ["Empty text"]

    # Check for direction markers
    if '\u200e' in text or '\u200f' in text:
        issues.append("Contains direction markers")

    # Check for mixed scripts (Arabic + Latin)
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))
    if has_arabic and has_latin:
        # This might be intentional (scientific terms, etc.)
        pass  # issues.append("Contains mixed Arabic/Latin scripts")

    # Check for control characters
    for char in text:
        if unicodedata.category(char) == 'Cc' and char not in '\n\t':
            issues.append(f"Contains control character: U+{ord(char):04X}")

    return issues


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text (conservative policy)."""
    if not text:
        return text

    # Remove direction markers
    text = text.replace('\u200e', '').replace('\u200f', '')

    # Remove zero-width characters
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

    return text.strip()


# ============================================================================
# Data Loading
# ============================================================================

def load_arabic_translations(batches_dir: Path) -> dict:
    """Load all Arabic translations from batch files.

    Returns:
        dict: {oewn_id: {lem_ar: [...], def_ar: str, ex_ar: [...]}}
    """
    translations = {}
    file_count = 0

    logger.info(f"Loading Arabic translations from {batches_dir}")

    for file_path in sorted(batches_dir.glob('*.json')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for entry in data.get('translations', []):
                synset_id = entry['id']

                # Normalize Arabic text and deduplicate
                lem_ar = [normalize_arabic(lem) for lem in entry.get('lem_ar', [])]
                lem_ar = [lem for lem in lem_ar if lem]  # Remove empty
                # Deduplicate while preserving order
                seen = set()
                lem_ar = [x for x in lem_ar if not (x in seen or seen.add(x))]

                def_ar = normalize_arabic(entry.get('def_ar', ''))
                ex_ar = [normalize_arabic(ex) for ex in entry.get('ex_ar', [])]
                ex_ar = [ex for ex in ex_ar if ex]  # Remove empty

                if synset_id in translations:
                    logger.warning(f"Duplicate synset {synset_id} in {file_path.name}")

                translations[synset_id] = {
                    'lem_ar': lem_ar,
                    'def_ar': def_ar,
                    'ex_ar': ex_ar
                }

            file_count += 1

        except json.JSONDecodeError as e:
            logger.error(f"JSON error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")

    logger.info(f"Loaded {len(translations)} translations from {file_count} files")
    return translations


def load_oewn_data() -> dict:
    """Load OEWN data from wn library.

    Returns:
        dict: {oewn_id: {ili: str, pos: str, relations: {rel_type: [target_ids]}}}
    """
    logger.info("Loading OEWN data from wn library...")

    # Ensure OEWN is downloaded
    try:
        wn.download('oewn:2024')
    except Exception as e:
        logger.warning(f"OEWN download note: {e}")

    en = wn.Wordnet('oewn:2024')
    oewn_data = {}

    synsets_list = list(en.synsets())
    logger.info(f"Processing {len(synsets_list)} OEWN synsets...")

    for i, ss in enumerate(synsets_list):
        if (i + 1) % 10000 == 0:
            logger.info(f"  Processed {i + 1}/{len(synsets_list)} synsets")

        synset_id = ss.id

        # Get ILI
        ili = ss.ili.id if ss.ili else None

        # Get POS from synset ID (e.g., oewn-00001740-n -> n)
        pos = synset_id.split('-')[-1]

        # Get relations (only SynsetRelations we want to include)
        relations = {}
        all_rels = ss.relations()
        for rel_type, targets in all_rels.items():
            if rel_type in INCLUDED_SYNSET_RELATIONS:
                relations[rel_type] = [t.id for t in targets]

        oewn_data[synset_id] = {
            'ili': ili,
            'pos': pos,
            'relations': relations
        }

    logger.info(f"Loaded {len(oewn_data)} OEWN synsets with ILI and relations")
    return oewn_data


# ============================================================================
# WN-LMF XML Generation
# ============================================================================

def generate_lmf_xml(ar_translations: dict, oewn_data: dict) -> Element:
    """Generate WN-LMF XML structure.

    Returns:
        Element: Root LexicalResource element
    """
    logger.info("Generating WN-LMF XML structure...")

    # Create root element
    root = Element('LexicalResource')
    root.set('xmlns:dc', 'https://globalwordnet.github.io/schemas/dc/')

    # Create Lexicon
    lexicon = SubElement(root, 'Lexicon')
    lexicon.set('id', LEXICON_ID)
    lexicon.set('label', LEXICON_LABEL)
    lexicon.set('language', LANGUAGE)
    lexicon.set('email', EMAIL)
    lexicon.set('license', LICENSE_URL)
    lexicon.set('version', VERSION)
    lexicon.set('url', PROJECT_URL)
    lexicon.set('citation', CITATION)
    lexicon.set('dc:description', f'Arabic WordNet with {len(ar_translations)} synsets derived from Open English WordNet')
    lexicon.set('dc:source', 'Derived from Open English WordNet 2024 (https://en-word.net/)')

    # Add dependency declaration (required by WN-LMF standard for derived wordnets)
    requires = SubElement(lexicon, 'Requires')
    requires.set('id', 'oewn')
    requires.set('version', '2024')
    requires.set('url', 'https://en-word.net/')

    # Track entries: {(lemma, pos): [senses]}
    entries = defaultdict(list)

    # Track synsets to generate
    synsets_to_generate = []

    # Statistics
    stats = {
        'synsets': 0,
        'entries': 0,
        'senses': 0,
        'relations': 0,
        'missing_oewn': 0,
        'empty_lemmas': 0,
        'pos_counts': defaultdict(int)
    }

    # Process each Arabic translation
    logger.info("Processing translations...")
    for oewn_id, ar_data in ar_translations.items():
        # Get OEWN data
        oewn = oewn_data.get(oewn_id)
        if not oewn:
            stats['missing_oewn'] += 1
            continue

        # Convert synset ID
        awn_synset_id = convert_synset_id(oewn_id)
        pos = oewn['pos']

        # Get lemmas
        lemmas = ar_data['lem_ar']
        if not lemmas:
            stats['empty_lemmas'] += 1
            continue

        # Create senses for each lemma
        for lemma in lemmas:
            sense_id = generate_sense_id(lemma, awn_synset_id)
            entries[(lemma, pos)].append({
                'sense_id': sense_id,
                'synset_id': awn_synset_id
            })
            stats['senses'] += 1

        # Queue synset for generation
        synsets_to_generate.append({
            'id': awn_synset_id,
            'ili': oewn['ili'],
            'pos': pos,
            'definition': ar_data['def_ar'],
            'examples': ar_data['ex_ar'],
            'relations': oewn['relations']
        })

        stats['synsets'] += 1
        stats['pos_counts'][pos] += 1

    # Build set of synset IDs we have (for filtering relations)
    valid_synset_ids = {s['id'] for s in synsets_to_generate}
    logger.info(f"Valid synset IDs for relation filtering: {len(valid_synset_ids)}")

    # Generate LexicalEntry elements
    logger.info(f"Generating {len(entries)} lexical entries...")
    for (lemma, pos), senses in sorted(entries.items()):
        entry_id = generate_entry_id(lemma, pos)

        entry_elem = SubElement(lexicon, 'LexicalEntry')
        entry_elem.set('id', entry_id)

        lemma_elem = SubElement(entry_elem, 'Lemma')
        lemma_elem.set('writtenForm', lemma)
        lemma_elem.set('partOfSpeech', pos)
        lemma_elem.set('script', 'Arab')

        # Add senses with ordering
        for i, sense_data in enumerate(senses, 1):
            sense_elem = SubElement(entry_elem, 'Sense')
            sense_elem.set('id', sense_data['sense_id'])
            sense_elem.set('synset', sense_data['synset_id'])
            if len(senses) > 1:
                sense_elem.set('n', str(i))

        stats['entries'] += 1

    # Generate Synset elements
    logger.info(f"Generating {len(synsets_to_generate)} synsets...")
    for synset_data in synsets_to_generate:
        synset_elem = SubElement(lexicon, 'Synset')
        synset_elem.set('id', synset_data['id'])

        # ILI is required by DTD - use empty string if missing
        synset_elem.set('ili', synset_data['ili'] if synset_data['ili'] else '')

        synset_elem.set('partOfSpeech', synset_data['pos'])

        # Definition
        if synset_data['definition']:
            def_elem = SubElement(synset_elem, 'Definition')
            def_elem.text = synset_data['definition']

        # Examples
        for example in synset_data['examples']:
            ex_elem = SubElement(synset_elem, 'Example')
            ex_elem.text = example

        # SynsetRelations - only include if target exists in our data
        for rel_type, targets in synset_data['relations'].items():
            for target_oewn_id in targets:
                # Convert target ID to AWN format
                target_awn_id = convert_synset_id(target_oewn_id)

                # Only include relation if target synset exists
                if target_awn_id in valid_synset_ids:
                    rel_elem = SubElement(synset_elem, 'SynsetRelation')
                    rel_elem.set('relType', rel_type)
                    rel_elem.set('target', target_awn_id)
                    stats['relations'] += 1
                else:
                    stats['skipped_relations'] = stats.get('skipped_relations', 0) + 1

    # Log statistics
    logger.info("=" * 50)
    logger.info("Generation Statistics:")
    logger.info(f"  Synsets: {stats['synsets']}")
    logger.info(f"  Entries: {stats['entries']}")
    logger.info(f"  Senses: {stats['senses']}")
    logger.info(f"  Relations: {stats['relations']}")
    logger.info(f"  Missing OEWN data: {stats['missing_oewn']}")
    logger.info(f"  Empty lemmas: {stats['empty_lemmas']}")
    logger.info(f"  Skipped relations (missing target): {stats.get('skipped_relations', 0)}")
    logger.info("  POS Distribution:")
    for pos, count in sorted(stats['pos_counts'].items()):
        logger.info(f"    {pos}: {count}")
    logger.info("=" * 50)

    return root


def prettify_xml(elem: Element) -> str:
    """Return a pretty-printed XML string."""
    rough_string = tostring(elem, encoding='unicode')

    # Add XML declaration and DOCTYPE
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    doctype = '<!DOCTYPE LexicalResource SYSTEM "http://globalwordnet.github.io/schemas/WN-LMF-1.4.dtd">\n'

    # Parse and prettify
    reparsed = minidom.parseString(rough_string)
    pretty = reparsed.toprettyxml(indent="  ")

    # Remove the default XML declaration added by minidom
    lines = pretty.split('\n')
    if lines[0].startswith('<?xml'):
        lines = lines[1:]

    # Combine with our declaration and doctype
    return xml_declaration + doctype + '\n'.join(lines)


def write_xml(root: Element, output_path: Path):
    """Write XML to file with pretty formatting."""
    logger.info(f"Writing XML to {output_path}...")

    xml_string = prettify_xml(root)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_string)

    # Get file size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Written {size_mb:.1f} MB to {output_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Convert Arabic WordNet to WN-LMF XML')
    parser.add_argument('--output', '-o', type=Path, default=OUTPUT_DIR / 'awn4.xml',
                        help='Output XML file path')
    parser.add_argument('--ar-batches', type=Path, default=AR_BATCHES_DIR,
                        help='Path to Arabic translation batches')
    args = parser.parse_args()

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Arabic WordNet Conversion to WN-LMF 1.4")
    logger.info("=" * 60)
    logger.info(f"Arabic batches: {args.ar_batches}")
    logger.info(f"Output: {args.output}")

    try:
        # Load data
        ar_translations = load_arabic_translations(args.ar_batches)
        oewn_data = load_oewn_data()

        # Generate XML
        root = generate_lmf_xml(ar_translations, oewn_data)

        # Write output
        write_xml(root, args.output)

        logger.info("Conversion completed successfully!")

    except Exception as e:
        logger.exception(f"Conversion failed: {e}")
        raise


if __name__ == "__main__":
    main()
