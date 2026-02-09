#!/usr/bin/env python3
"""
Find entries that exist in both the Arabic Ontology and AWN4,
then output a side-by-side comparison file.
"""
import csv
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
import random

BASE = "/Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4"
ONTOLOGY_DIR = f"{BASE}/experiments/arabic-ontology"
AWN4_XML = f"{BASE}/output/awn4.xml"
OUTPUT_FILE = f"{BASE}/experiments/ontology_vs_awn4_comparison.txt"

# Arabic diacritic removal for fuzzy matching
DIACRITICS = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')

def strip_diacritics(text):
    """Remove Arabic diacritics for comparison."""
    return DIACRITICS.sub('', text)

def normalize_for_match(text):
    """Normalize Arabic text for matching: strip diacritics, trailing numbers, etc."""
    t = strip_diacritics(text.strip())
    # Remove trailing digits used for disambiguation (e.g., كَائِنٌ2 -> كائن)
    t = re.sub(r'\d+$', '', t)
    # Normalize alef variants
    t = t.replace('إ', 'ا').replace('أ', 'ا').replace('آ', 'ا')
    # Remove tatweel
    t = t.replace('\u0640', '')
    return t.strip()

# ============================================================
# 1. Load Arabic Ontology
# ============================================================
print("Loading Arabic Ontology concepts...")
onto_concepts = {}
with open(f"{ONTOLOGY_DIR}/Concepts.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        onto_concepts[row["conceptId"]] = row

onto_relations = {}
with open(f"{ONTOLOGY_DIR}/Relations.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        onto_relations[row["concept_id"]] = row

# Build a lookup: normalized_lemma -> list of concept IDs
onto_lemma_lookup = defaultdict(list)
for cid, c in onto_concepts.items():
    arabic_synset = c.get("arabicSynset", "")
    for lemma in arabic_synset.split("|"):
        lemma = lemma.strip()
        if lemma:
            norm = normalize_for_match(lemma)
            if norm:
                onto_lemma_lookup[norm].append(cid)

print(f"  Loaded {len(onto_concepts)} concepts, {len(onto_lemma_lookup)} unique normalized lemmas")

# ============================================================
# 2. Stream-parse AWN4 XML to find matching lemmas
# ============================================================
print("Parsing AWN4 XML (this may take a moment)...")

# First pass: collect all lemmas and their synset mappings
awn4_lemma_to_synsets = defaultdict(set)  # lemma_text -> set of synset_ids
awn4_entry_data = {}  # entry_id -> {lemma, pos, senses: [{sense_id, synset_id}]}
awn4_synset_data = {}  # synset_id -> {ili, pos, definition, examples, relations}

current_entry_id = None
current_entry = None
current_synset_id = None
current_synset = None

for event, elem in ET.iterparse(AWN4_XML, events=("start", "end")):
    tag = elem.tag

    if event == "start":
        if tag == "LexicalEntry":
            current_entry_id = elem.get("id")
            current_entry = {"senses": []}
        elif tag == "Synset":
            current_synset_id = elem.get("id")
            current_synset = {
                "ili": elem.get("ili", ""),
                "pos": elem.get("partOfSpeech", ""),
                "definitions": [],
                "examples": [],
                "relations": []
            }

    elif event == "end":
        if tag == "Lemma" and current_entry is not None:
            current_entry["lemma"] = elem.get("writtenForm", "")
            current_entry["pos"] = elem.get("partOfSpeech", "")
        elif tag == "Sense" and current_entry is not None:
            current_entry["senses"].append({
                "sense_id": elem.get("id", ""),
                "synset_id": elem.get("synset", "")
            })
        elif tag == "LexicalEntry" and current_entry is not None:
            awn4_entry_data[current_entry_id] = current_entry
            lemma_text = current_entry.get("lemma", "")
            norm = normalize_for_match(lemma_text)
            for s in current_entry["senses"]:
                awn4_lemma_to_synsets[norm].add(s["synset_id"])
            current_entry_id = None
            current_entry = None
        elif tag == "Definition" and current_synset is not None:
            current_synset["definitions"].append(elem.text or "")
        elif tag == "Example" and current_synset is not None:
            current_synset["examples"].append(elem.text or "")
        elif tag == "SynsetRelation" and current_synset is not None:
            current_synset["relations"].append({
                "relType": elem.get("relType", ""),
                "target": elem.get("target", "")
            })
        elif tag == "Synset" and current_synset is not None:
            awn4_synset_data[current_synset_id] = current_synset
            current_synset_id = None
            current_synset = None

        # Free memory
        elem.clear()

print(f"  Loaded {len(awn4_entry_data)} lexical entries, {len(awn4_synset_data)} synsets")
print(f"  {len(awn4_lemma_to_synsets)} unique normalized AWN4 lemmas")

# ============================================================
# 3. Find matches between ontology and AWN4
# ============================================================
print("Finding matches...")

matches = []  # list of (onto_concept_id, matched_lemma, awn4_synset_ids)

for norm_lemma, onto_cids in onto_lemma_lookup.items():
    if norm_lemma in awn4_lemma_to_synsets:
        awn4_sids = awn4_lemma_to_synsets[norm_lemma]
        for cid in onto_cids:
            matches.append((cid, norm_lemma, awn4_sids))

print(f"  Found {len(matches)} matching (concept, lemma) pairs")

# Deduplicate by concept ID, keep unique concepts
seen_cids = {}
for cid, lemma, sids in matches:
    if cid not in seen_cids:
        seen_cids[cid] = (lemma, sids)

print(f"  {len(seen_cids)} unique ontology concepts with AWN4 matches")

# ============================================================
# 4. Randomly select 35 and write comparison
# ============================================================
all_matched_cids = list(seen_cids.keys())
random.seed(42)
sample_size = min(35, len(all_matched_cids))
selected = random.sample(all_matched_cids, sample_size)

print(f"  Selected {sample_size} random entries for comparison")

# Helper to get ontology parent info
def get_onto_parent(cid):
    r = onto_relations.get(cid, {})
    pid = r.get("subTypeOfID", "NULL")
    if pid == "0":
        return "ROOT (no parent)"
    if pid and pid != "NULL":
        p = onto_concepts.get(pid, {})
        return f"{pid}: {p.get('arabicSynset', '')} | {p.get('englishSynset', '')}"
    return "NULL"

def get_onto_partof(cid):
    r = onto_relations.get(cid, {})
    pid = r.get("partOfID", "NULL")
    if pid and pid != "NULL":
        p = onto_concepts.get(pid, {})
        return f"{pid}: {p.get('arabicSynset', '')} | {p.get('englishSynset', '')}"
    return "NULL"

def get_onto_instanceof(cid):
    r = onto_relations.get(cid, {})
    pid = r.get("instanceOfID", "NULL")
    if pid and pid != "NULL":
        p = onto_concepts.get(pid, {})
        return f"{pid}: {p.get('arabicSynset', '')} | {p.get('englishSynset', '')}"
    return "NULL"

# Find all AWN4 lemmas that map to a given synset
def get_awn4_lemmas_for_synset(synset_id):
    lemmas = []
    for eid, edata in awn4_entry_data.items():
        for s in edata["senses"]:
            if s["synset_id"] == synset_id:
                lemmas.append(edata["lemma"])
                break
    return lemmas[:10]  # cap at 10

# Write output
with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    out.write("=" * 100 + "\n")
    out.write("ARABIC ONTOLOGY vs AWN4 — SIDE-BY-SIDE COMPARISON\n")
    out.write(f"Selected {sample_size} entries that exist in both resources\n")
    out.write("=" * 100 + "\n\n")

    for idx, cid in enumerate(selected, 1):
        matched_lemma, awn4_synset_ids = seen_cids[cid]
        c = onto_concepts[cid]

        out.write(f"{'─' * 100}\n")
        out.write(f"  ENTRY {idx} / {sample_size}   |   Matched on lemma: \"{matched_lemma}\"\n")
        out.write(f"{'─' * 100}\n\n")

        # === ONTOLOGY SIDE ===
        out.write("  ┌─── ARABIC ONTOLOGY ───────────────────────────────────────────\n")
        out.write(f"  │ Concept ID:    {cid}\n")
        out.write(f"  │ Arabic Synset: {c.get('arabicSynset', '')}\n")
        out.write(f"  │ English:       {c.get('englishSynset', '') or '(none)'}\n")
        out.write(f"  │ Gloss:         {c.get('gloss', '') or '(none)'}\n")
        out.write(f"  │ Example:       {c.get('example', '') or '(none)'}\n")
        out.write(f"  │ DataSource:    {c.get('dataSourceId', '')}\n")
        out.write(f"  │ subTypeOf:     {get_onto_parent(cid)}\n")
        out.write(f"  │ partOf:        {get_onto_partof(cid)}\n")
        out.write(f"  │ instanceOf:    {get_onto_instanceof(cid)}\n")
        out.write(f"  └─────────────────────────────────────────────────────────────\n\n")

        # === AWN4 SIDE ===
        out.write("  ┌─── AWN4 (Arabic WordNet 4.0) ────────────────────────────────\n")
        for sid in sorted(awn4_synset_ids):  # show ALL matching synsets
            sd = awn4_synset_data.get(sid, {})
            lemmas = get_awn4_lemmas_for_synset(sid)
            defs = sd.get("definitions", [])
            examples = sd.get("examples", [])
            rels = sd.get("relations", [])

            # Group relations by type
            rel_groups = defaultdict(list)
            for rel in rels:
                rel_groups[rel["relType"]].append(rel["target"])

            out.write(f"  │\n")
            out.write(f"  │ Synset ID:     {sid}\n")
            out.write(f"  │ ILI:           {sd.get('ili', '')}\n")
            out.write(f"  │ POS:           {sd.get('pos', '')}\n")
            out.write(f"  │ Lemmas:        {' | '.join(lemmas)}\n")
            for i, d in enumerate(defs):
                out.write(f"  │ Definition{f' [{i+1}]' if len(defs)>1 else ''}:   {d}\n")
            for i, ex in enumerate(examples[:3]):
                out.write(f"  │ Example{f' [{i+1}]' if len(examples)>1 else ''}:     {ex}\n")
            if rel_groups:
                out.write(f"  │ Relations:\n")
                for rtype, targets in sorted(rel_groups.items()):
                    out.write(f"  │   {rtype}: {', '.join(targets)}\n")
            out.write(f"  │ {'- - - - - - - - - - - - - - - - - -'}\n")

        out.write(f"  │ Total matching AWN4 synsets: {len(awn4_synset_ids)}\n")

        out.write(f"  └─────────────────────────────────────────────────────────────\n\n\n")

    out.write("=" * 100 + "\n")
    out.write("END OF COMPARISON\n")
    out.write("=" * 100 + "\n")

print(f"\nDone! Comparison saved to:\n  {OUTPUT_FILE}")
