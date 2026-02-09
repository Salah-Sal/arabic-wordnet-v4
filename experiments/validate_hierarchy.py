#!/usr/bin/env python3
"""
Deep validation of hierarchy comparison results.
Dumps ALL AGREE and a large sample of DISAGREE entries with full detail
for manual linguistic review.
"""
import csv
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
import time
import json

BASE = "/Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4"
ONTOLOGY_DIR = f"{BASE}/experiments/arabic-ontology"
AWN4_XML = f"{BASE}/output/awn4.xml"

MAX_HOPS = 8

DIACRITICS = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')

def strip_diacritics(text):
    return DIACRITICS.sub('', text)

def normalize_for_match(text):
    t = strip_diacritics(text.strip())
    t = re.sub(r'\d+$', '', t)
    t = t.replace('\u0625', '\u0627').replace('\u0623', '\u0627').replace('\u0622', '\u0627')
    t = t.replace('\u0640', '')
    return t.strip()

# Phase 1: Load Ontology
print("Loading Ontology...")
onto_concepts = {}
with open(f"{ONTOLOGY_DIR}/Concepts.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        onto_concepts[row["conceptId"]] = row

onto_relations = {}
with open(f"{ONTOLOGY_DIR}/Relations.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        onto_relations[row["concept_id"]] = row

subtypeof_pairs = []
for cid, rel in onto_relations.items():
    parent_id = rel.get("subTypeOfID", "NULL")
    if parent_id and parent_id not in ("NULL", "0"):
        subtypeof_pairs.append((cid, parent_id))

# Phase 2: Parse AWN4
print("Parsing AWN4 XML...")
awn4_lemma_to_synsets = defaultdict(set)
hypernym_graph = defaultdict(set)
awn4_synset_defs = {}
awn4_synset_pos = {}
# Also track which lemma forms led to each synset
awn4_synset_lemmas = defaultdict(list)  # synset_id -> list of (raw_lemma, normalized)

current_entry = None
current_synset_id = None
current_synset_hypernyms = None
current_synset_def = None
current_synset_pos_val = None

for event, elem in ET.iterparse(AWN4_XML, events=("start", "end")):
    tag = elem.tag
    if event == "start":
        if tag == "LexicalEntry":
            current_entry = {"lemma": "", "synset_ids": []}
        elif tag == "Synset":
            current_synset_id = elem.get("id")
            current_synset_hypernyms = set()
            current_synset_def = None
            current_synset_pos_val = elem.get("partOfSpeech", "")
    elif event == "end":
        if tag == "Lemma" and current_entry is not None:
            current_entry["lemma"] = elem.get("writtenForm", "")
        elif tag == "Sense" and current_entry is not None:
            sid = elem.get("synset", "")
            if sid:
                current_entry["synset_ids"].append(sid)
        elif tag == "LexicalEntry" and current_entry is not None:
            raw = current_entry["lemma"]
            norm = normalize_for_match(raw)
            if norm:
                for sid in current_entry["synset_ids"]:
                    awn4_lemma_to_synsets[norm].add(sid)
                    awn4_synset_lemmas[sid].append((raw, norm))
            current_entry = None
        elif tag == "Definition" and current_synset_id is not None:
            if current_synset_def is None:
                current_synset_def = elem.text or ""
        elif tag == "SynsetRelation" and current_synset_id is not None:
            rel_type = elem.get("relType", "")
            target = elem.get("target", "")
            if rel_type in ("hypernym", "instance_hypernym"):
                current_synset_hypernyms.add(target)
        elif tag == "Synset" and current_synset_id is not None:
            hypernym_graph[current_synset_id] = current_synset_hypernyms
            if current_synset_def:
                awn4_synset_defs[current_synset_id] = current_synset_def
            if current_synset_pos_val:
                awn4_synset_pos[current_synset_id] = current_synset_pos_val
            current_synset_id = None
        elem.clear()

# Phase 3: Build concept -> synset matching
# Track WHICH ontology lemma matched WHICH AWN4 synsets
concept_to_synsets = {}
concept_match_detail = {}  # concept_id -> {onto_lemma: [matched_synset_ids]}

for cid, c in onto_concepts.items():
    matched_synsets = set()
    detail = {}
    for lemma in c.get("arabicSynset", "").split("|"):
        lemma = lemma.strip()
        if lemma:
            norm = normalize_for_match(lemma)
            if norm and norm in awn4_lemma_to_synsets:
                sids = awn4_lemma_to_synsets[norm]
                matched_synsets.update(sids)
                detail[lemma] = list(sids)
    if matched_synsets:
        concept_to_synsets[cid] = matched_synsets
        concept_match_detail[cid] = detail

# Phase 4: Classify
def find_hypernym_path(child_synsets, parent_synsets, max_hops):
    parent_set = set(parent_synsets)
    best_result = None
    for start_sid in child_synsets:
        queue = deque()
        queue.append((start_sid, 0, [start_sid]))
        visited = {start_sid}
        while queue:
            current, depth, path = queue.popleft()
            if depth > 0 and current in parent_set:
                if best_result is None or depth < best_result[1]:
                    best_result = (True, depth, start_sid, current, list(path))
                break
            if depth >= max_hops:
                continue
            for parent in hypernym_graph.get(current, set()):
                if parent not in visited:
                    visited.add(parent)
                    queue.append((parent, depth + 1, path + [parent]))
    if best_result:
        return best_result
    return (False, -1, None, None, None)

results_agree = []
results_disagree = []

for child_cid, parent_cid in subtypeof_pairs:
    child_synsets = concept_to_synsets.get(child_cid, set())
    parent_synsets = concept_to_synsets.get(parent_cid, set())

    if child_synsets and parent_synsets:
        found, hops, c_sid, p_sid, path = find_hypernym_path(
            child_synsets, parent_synsets, MAX_HOPS)
        if found:
            results_agree.append((child_cid, parent_cid, hops, c_sid, p_sid, path))
        else:
            results_disagree.append((child_cid, parent_cid, child_synsets, parent_synsets))

print(f"\nAGREE: {len(results_agree)}, DISAGREE: {len(results_disagree)}")

# Phase 5: Dump ALL AGREE entries with full detail
def sid_info(sid):
    d = awn4_synset_defs.get(sid, "")
    pos = awn4_synset_pos.get(sid, "")
    lemmas = awn4_synset_lemmas.get(sid, [])
    lemma_str = ", ".join(f"{raw}" for raw, norm in lemmas[:5])
    return f"{sid} [{pos}] lemmas=({lemma_str}) def: {d[:120]}"

def concept_info(cid):
    c = onto_concepts.get(cid, {})
    ar = c.get("arabicSynset", "?")
    en = c.get("englishSynset", "")
    gloss = c.get("gloss", "")[:100]
    return f"[{cid}] {ar}" + (f" ({en})" if en and en != "NULL" else "") + (f" // {gloss}" if gloss else "")

out_path = f"{BASE}/experiments/validation_all_agree.txt"
with open(out_path, "w", encoding="utf-8") as out:
    out.write(f"ALL {len(results_agree)} AGREE CASES — Full Detail for Linguistic Review\n")
    out.write("=" * 120 + "\n\n")

    for i, (child_cid, parent_cid, hops, c_sid, p_sid, path) in enumerate(results_agree, 1):
        out.write(f"--- AGREE #{i} ({hops} hop{'s' if hops != 1 else ''}) ---\n")
        out.write(f"  CHILD ontology: {concept_info(child_cid)}\n")
        out.write(f"  PARENT ontology: {concept_info(parent_cid)}\n")

        # Show which ontology lemma matched which synset
        child_detail = concept_match_detail.get(child_cid, {})
        parent_detail = concept_match_detail.get(parent_cid, {})

        # Find which ontology lemma led to c_sid
        child_via = "?"
        for lemma, sids in child_detail.items():
            if c_sid in sids:
                child_via = lemma
                break
        parent_via = "?"
        for lemma, sids in parent_detail.items():
            if p_sid in sids:
                parent_via = lemma
                break

        out.write(f"  Child matched via lemma: '{child_via}' -> {c_sid}\n")
        out.write(f"  Parent matched via lemma: '{parent_via}' -> {p_sid}\n")
        out.write(f"  AWN4 hypernym path:\n")
        for step in path:
            out.write(f"    -> {sid_info(step)}\n")
        out.write("\n")

print(f"Wrote: {out_path}")

# Phase 6: Dump first 100 DISAGREE with full detail
out_path2 = f"{BASE}/experiments/validation_disagree_sample.txt"
with open(out_path2, "w", encoding="utf-8") as out:
    n = min(100, len(results_disagree))
    out.write(f"DISAGREE CASES — {n} of {len(results_disagree)} — Full Detail\n")
    out.write("=" * 120 + "\n\n")

    for i, (child_cid, parent_cid, child_sids, parent_sids) in enumerate(results_disagree[:n], 1):
        out.write(f"--- DISAGREE #{i} ---\n")
        out.write(f"  CHILD ontology: {concept_info(child_cid)}\n")
        out.write(f"  PARENT ontology: {concept_info(parent_cid)}\n")

        child_detail = concept_match_detail.get(child_cid, {})
        parent_detail = concept_match_detail.get(parent_cid, {})

        out.write(f"  Child AWN4 matches ({len(child_sids)} synsets):\n")
        for lemma, sids in child_detail.items():
            for sid in sids[:3]:
                out.write(f"    '{lemma}' -> {sid_info(sid)}\n")

        out.write(f"  Parent AWN4 matches ({len(parent_sids)} synsets):\n")
        for lemma, sids in parent_detail.items():
            for sid in sids[:3]:
                out.write(f"    '{lemma}' -> {sid_info(sid)}\n")
        out.write("\n")

print(f"Wrote: {out_path2}")

# Phase 7: Summary statistics on AGREE quality
print("\n=== AGREE QUALITY INDICATORS ===")
# Check POS consistency: does child synset POS == parent synset POS?
pos_match = 0
pos_mismatch = 0
pos_cross = defaultdict(int)
for child_cid, parent_cid, hops, c_sid, p_sid, path in results_agree:
    c_pos = awn4_synset_pos.get(c_sid, "?")
    p_pos = awn4_synset_pos.get(p_sid, "?")
    if c_pos == p_pos:
        pos_match += 1
    else:
        pos_mismatch += 1
        pos_cross[f"{c_pos}->{p_pos}"] += 1

print(f"POS consistent (child=parent): {pos_match} / {len(results_agree)}")
print(f"POS mismatch: {pos_mismatch}")
for cross, cnt in sorted(pos_cross.items(), key=lambda x: -x[1]):
    print(f"  {cross}: {cnt}")

# Check if child/parent synset came from the SAME ontology lemma (potential self-match)
same_lemma_match = 0
for child_cid, parent_cid, hops, c_sid, p_sid, path in results_agree:
    child_detail = concept_match_detail.get(child_cid, {})
    parent_detail = concept_match_detail.get(parent_cid, {})
    child_norms = set(normalize_for_match(l) for l in child_detail)
    parent_norms = set(normalize_for_match(l) for l in parent_detail)
    # Did the matching go through the same normalized form?
    child_match_norm = None
    parent_match_norm = None
    for lemma, sids in child_detail.items():
        if c_sid in sids:
            child_match_norm = normalize_for_match(lemma)
    for lemma, sids in parent_detail.items():
        if p_sid in sids:
            parent_match_norm = normalize_for_match(lemma)
    if child_match_norm and parent_match_norm and child_match_norm == parent_match_norm:
        same_lemma_match += 1

print(f"\nAGREE via same normalized lemma on both sides: {same_lemma_match} / {len(results_agree)}")
print("  (These are cases where child+parent ontology concepts share a lemma form,")
print("   so the 'agreement' may just be matching the same word to its own hypernym)")

# Phase 8: Analyze DISAGREE — how many have cross-POS contamination?
print("\n=== DISAGREE QUALITY INDICATORS ===")
# For disagree, check if child or parent matches are dominated by wrong POS
disagree_child_pos = defaultdict(int)
disagree_parent_pos = defaultdict(int)
cross_pos_disagree = 0

for child_cid, parent_cid, child_sids, parent_sids in results_disagree:
    child_pos = set(awn4_synset_pos.get(sid, "?") for sid in child_sids)
    parent_pos = set(awn4_synset_pos.get(sid, "?") for sid in parent_sids)

    # Count how many disagree cases have adjective contamination
    if "a" in child_pos or "a" in parent_pos:
        cross_pos_disagree += 1

print(f"DISAGREE with adjective synsets in matches: {cross_pos_disagree} / {len(results_disagree)}")

# How many disagree cases have child or parent with >10 synsets (polysemy explosion)?
poly_child = sum(1 for _, _, csids, _ in results_disagree if len(csids) > 10)
poly_parent = sum(1 for _, _, _, psids in results_disagree if len(psids) > 10)
print(f"DISAGREE with child >10 synsets: {poly_child}")
print(f"DISAGREE with parent >10 synsets: {poly_parent}")

print("\nDone.")
