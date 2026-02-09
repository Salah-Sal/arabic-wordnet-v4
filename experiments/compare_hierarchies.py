#!/usr/bin/env python3
"""
Compare the Arabic Ontology's subTypeOf hierarchy against AWN4's hypernym chains.

For each ontology concept that has a subTypeOf parent, this script:
1. Maps the child concept to AWN4 synset(s) via normalized lemma matching
2. Maps the parent concept to AWN4 synset(s) via normalized lemma matching
3. Checks whether any hypernym path exists between the child's and parent's
   AWN4 synsets (up to MAX_HOPS depth via BFS)
4. Categorizes the result as AGREE, DISAGREE, PARTIAL, or UNMATCHABLE

Output: detailed .txt report and markdown summary statistics.
"""
import csv
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
import time

# ============================================================
# Configuration
# ============================================================
BASE = "/Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4"
ONTOLOGY_DIR = f"{BASE}/experiments/arabic-ontology"
AWN4_XML = f"{BASE}/output/awn4.xml"
OUTPUT_REPORT = f"{BASE}/experiments/hierarchy_comparison_report.txt"

MAX_HOPS = 8   # Maximum hypernym chain depth to search
SAMPLE_PER_CATEGORY = 15  # Number of detailed examples per category in report

# ============================================================
# Phase 0: Normalization functions (reused from find_matches.py)
# ============================================================
DIACRITICS = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')

def strip_diacritics(text):
    """Remove Arabic diacritics for comparison."""
    return DIACRITICS.sub('', text)

def normalize_for_match(text):
    """Normalize Arabic text for matching: strip diacritics, trailing numbers, etc."""
    t = strip_diacritics(text.strip())
    t = re.sub(r'\d+$', '', t)
    t = t.replace('\u0625', '\u0627').replace('\u0623', '\u0627').replace('\u0622', '\u0627')
    t = t.replace('\u0640', '')
    return t.strip()

# ============================================================
# Phase 1: Load Arabic Ontology
# ============================================================
print("Phase 1: Loading Arabic Ontology...")
t0 = time.time()

onto_concepts = {}
with open(f"{ONTOLOGY_DIR}/Concepts.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        onto_concepts[row["conceptId"]] = row

onto_relations = {}
with open(f"{ONTOLOGY_DIR}/Relations.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        onto_relations[row["concept_id"]] = row

# Extract all subTypeOf pairs: (child_id, parent_id)
subtypeof_pairs = []
for cid, rel in onto_relations.items():
    parent_id = rel.get("subTypeOfID", "NULL")
    if parent_id and parent_id not in ("NULL", "0"):
        subtypeof_pairs.append((cid, parent_id))

print(f"  {len(onto_concepts)} concepts, {len(subtypeof_pairs)} subTypeOf pairs")
print(f"  Elapsed: {time.time()-t0:.1f}s")

# ============================================================
# Phase 2: Stream-parse AWN4 XML
# ============================================================
print("Phase 2: Parsing AWN4 XML (this may take a moment)...")
t1 = time.time()

awn4_lemma_to_synsets = defaultdict(set)  # normalized_lemma -> set(synset_ids)
hypernym_graph = defaultdict(set)          # child_synset -> set(parent_synsets)
awn4_synset_defs = {}                      # synset_id -> first definition text
awn4_synset_pos = {}                       # synset_id -> POS

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
            norm = normalize_for_match(current_entry["lemma"])
            if norm:
                for sid in current_entry["synset_ids"]:
                    awn4_lemma_to_synsets[norm].add(sid)
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
            current_synset_hypernyms = None
            current_synset_def = None
            current_synset_pos_val = None

        elem.clear()

print(f"  {len(awn4_lemma_to_synsets)} unique normalized AWN4 lemmas")
print(f"  {len(hypernym_graph)} synsets in hypernym graph")
print(f"  Elapsed: {time.time()-t1:.1f}s")

# ============================================================
# Phase 3: Build concept -> synset matching
# ============================================================
print("Phase 3: Building concept-to-synset mappings...")
t2 = time.time()

concept_to_synsets = {}  # concept_id -> set(synset_ids)

for cid, c in onto_concepts.items():
    matched_synsets = set()
    for lemma in c.get("arabicSynset", "").split("|"):
        lemma = lemma.strip()
        if lemma:
            norm = normalize_for_match(lemma)
            if norm and norm in awn4_lemma_to_synsets:
                matched_synsets.update(awn4_lemma_to_synsets[norm])
    if matched_synsets:
        concept_to_synsets[cid] = matched_synsets

print(f"  {len(concept_to_synsets)} / {len(onto_concepts)} concepts matched to AWN4")
print(f"  Elapsed: {time.time()-t2:.1f}s")

# ============================================================
# Phase 4: BFS hypernym path finder + classify each pair
# ============================================================
print("Phase 4: Classifying subTypeOf pairs...")
t3 = time.time()

def find_hypernym_path(child_synsets, parent_synsets, max_hops):
    """
    BFS upward from each child synset through hypernym_graph.
    Returns (found, hops, child_sid, parent_sid, path) for the shortest path,
    or (False, -1, None, None, None) if no path found.
    """
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
                break  # Shortest from this start found

            if depth >= max_hops:
                continue

            for parent in hypernym_graph.get(current, set()):
                if parent not in visited:
                    visited.add(parent)
                    queue.append((parent, depth + 1, path + [parent]))

    if best_result:
        return best_result
    return (False, -1, None, None, None)


# Classification
results = {
    "AGREE": [],
    "DISAGREE": [],
    "PARTIAL_CHILD_ONLY": [],
    "PARTIAL_PARENT_ONLY": [],
    "UNMATCHABLE": [],
}

for i, (child_cid, parent_cid) in enumerate(subtypeof_pairs):
    child_synsets = concept_to_synsets.get(child_cid, set())
    parent_synsets = concept_to_synsets.get(parent_cid, set())

    if not child_synsets and not parent_synsets:
        results["UNMATCHABLE"].append((child_cid, parent_cid))
    elif not parent_synsets:
        results["PARTIAL_CHILD_ONLY"].append(
            (child_cid, parent_cid, child_synsets))
    elif not child_synsets:
        results["PARTIAL_PARENT_ONLY"].append(
            (child_cid, parent_cid, parent_synsets))
    else:
        found, hops, c_sid, p_sid, path = find_hypernym_path(
            child_synsets, parent_synsets, MAX_HOPS)
        if found:
            results["AGREE"].append(
                (child_cid, parent_cid, hops, c_sid, p_sid, path))
        else:
            results["DISAGREE"].append(
                (child_cid, parent_cid, child_synsets, parent_synsets))

    if (i + 1) % 500 == 0:
        print(f"  Processed {i+1} / {len(subtypeof_pairs)} pairs...")

print(f"  Classification complete. Elapsed: {time.time()-t3:.1f}s")

# ============================================================
# Phase 5: Generate detailed report
# ============================================================
print("Phase 5: Writing report...")

def concept_label(cid):
    c = onto_concepts.get(cid, {})
    ar = c.get("arabicSynset", "?")
    en = c.get("englishSynset", "")
    label = f"[{cid}] {ar}"
    if en and en != "NULL":
        label += f" ({en})"
    return label

def synset_label(sid):
    d = awn4_synset_defs.get(sid, "")
    pos = awn4_synset_pos.get(sid, "")
    trunc = d[:80] + "..." if len(d) > 80 else d
    prefix = f"{sid}"
    if pos:
        prefix += f" [{pos}]"
    if trunc:
        prefix += f": {trunc}"
    return prefix

total = len(subtypeof_pairs)
n_agree = len(results["AGREE"])
n_disagree = len(results["DISAGREE"])
n_partial_c = len(results["PARTIAL_CHILD_ONLY"])
n_partial_p = len(results["PARTIAL_PARENT_ONLY"])
n_partial = n_partial_c + n_partial_p
n_unmatch = len(results["UNMATCHABLE"])

# Hop distribution
hop_counts = defaultdict(int)
if results["AGREE"]:
    for _, _, hops, _, _, _ in results["AGREE"]:
        hop_counts[hops] += 1

with open(OUTPUT_REPORT, "w", encoding="utf-8") as out:
    out.write("=" * 100 + "\n")
    out.write("ARABIC ONTOLOGY subTypeOf vs AWN4 HYPERNYM CHAINS\n")
    out.write(f"Compared {total} ontology parent-child pairs\n")
    out.write(f"Hypernym search depth: up to {MAX_HOPS} hops\n")
    out.write("=" * 100 + "\n\n")

    # Summary
    out.write("SUMMARY STATISTICS\n")
    out.write("-" * 60 + "\n")
    out.write(f"Total subTypeOf pairs analyzed:       {total}\n")
    out.write(f"  AGREE     (hypernym path found):    {n_agree:>5}  ({100*n_agree/total:.1f}%)\n")
    out.write(f"  DISAGREE  (both matched, no path):  {n_disagree:>5}  ({100*n_disagree/total:.1f}%)\n")
    out.write(f"  PARTIAL   (only one side matched):  {n_partial:>5}  ({100*n_partial/total:.1f}%)\n")
    out.write(f"    - child only:                     {n_partial_c:>5}\n")
    out.write(f"    - parent only:                    {n_partial_p:>5}\n")
    out.write(f"  UNMATCHABLE (neither matched):      {n_unmatch:>5}  ({100*n_unmatch/total:.1f}%)\n\n")

    if hop_counts:
        out.write("AGREE — Hop distribution:\n")
        for h in sorted(hop_counts):
            out.write(f"  {h} hop{'s' if h != 1 else ' '}: {hop_counts[h]:>5}  ({100*hop_counts[h]/n_agree:.1f}%)\n")
        avg_hops = sum(h * c for h, c in hop_counts.items()) / n_agree
        out.write(f"  Average: {avg_hops:.2f} hops\n")
        out.write("\n")

    # AGREE examples
    out.write("\n" + "=" * 100 + "\n")
    out.write(f"AGREE EXAMPLES (showing {min(SAMPLE_PER_CATEGORY, n_agree)} of {n_agree})\n")
    out.write("=" * 100 + "\n\n")

    for entry in results["AGREE"][:SAMPLE_PER_CATEGORY]:
        child_cid, parent_cid, hops, c_sid, p_sid, path = entry
        out.write(f"  Ontology: {concept_label(child_cid)}\n")
        out.write(f"    subTypeOf -> {concept_label(parent_cid)}\n")
        out.write(f"  AWN4 path ({hops} hop{'s' if hops != 1 else ''}):\n")
        for step_sid in path:
            out.write(f"    -> {synset_label(step_sid)}\n")
        out.write("\n")

    # DISAGREE examples
    out.write("\n" + "=" * 100 + "\n")
    out.write(f"DISAGREE EXAMPLES (showing {min(SAMPLE_PER_CATEGORY, n_disagree)} of {n_disagree})\n")
    out.write("=" * 100 + "\n\n")

    for entry in results["DISAGREE"][:SAMPLE_PER_CATEGORY]:
        child_cid, parent_cid, child_sids, parent_sids = entry
        out.write(f"  Ontology: {concept_label(child_cid)}\n")
        out.write(f"    subTypeOf -> {concept_label(parent_cid)}\n")
        out.write(f"  Child AWN4 synsets ({len(child_sids)}):\n")
        for sid in sorted(child_sids)[:5]:
            out.write(f"    {synset_label(sid)}\n")
        if len(child_sids) > 5:
            out.write(f"    ... and {len(child_sids) - 5} more\n")
        out.write(f"  Parent AWN4 synsets ({len(parent_sids)}):\n")
        for sid in sorted(parent_sids)[:5]:
            out.write(f"    {synset_label(sid)}\n")
        if len(parent_sids) > 5:
            out.write(f"    ... and {len(parent_sids) - 5} more\n")
        out.write(f"  -> No hypernym path found within {MAX_HOPS} hops\n\n")

    # PARTIAL — child only
    out.write("\n" + "=" * 100 + "\n")
    out.write(f"PARTIAL — CHILD ONLY (showing {min(SAMPLE_PER_CATEGORY, n_partial_c)} of {n_partial_c})\n")
    out.write("=" * 100 + "\n\n")

    for entry in results["PARTIAL_CHILD_ONLY"][:SAMPLE_PER_CATEGORY]:
        child_cid, parent_cid, child_sids = entry
        out.write(f"  Child:  {concept_label(child_cid)} -> {len(child_sids)} AWN4 synsets\n")
        out.write(f"  Parent: {concept_label(parent_cid)} -> NO AWN4 match\n\n")

    # PARTIAL — parent only
    out.write("\n" + "=" * 100 + "\n")
    out.write(f"PARTIAL — PARENT ONLY (showing {min(SAMPLE_PER_CATEGORY, n_partial_p)} of {n_partial_p})\n")
    out.write("=" * 100 + "\n\n")

    for entry in results["PARTIAL_PARENT_ONLY"][:SAMPLE_PER_CATEGORY]:
        child_cid, parent_cid, parent_sids = entry
        out.write(f"  Child:  {concept_label(child_cid)} -> NO AWN4 match\n")
        out.write(f"  Parent: {concept_label(parent_cid)} -> {len(parent_sids)} AWN4 synsets\n\n")

    # UNMATCHABLE examples
    out.write("\n" + "=" * 100 + "\n")
    out.write(f"UNMATCHABLE EXAMPLES (showing {min(SAMPLE_PER_CATEGORY, n_unmatch)} of {n_unmatch})\n")
    out.write("=" * 100 + "\n\n")

    for child_cid, parent_cid in results["UNMATCHABLE"][:SAMPLE_PER_CATEGORY]:
        out.write(f"  Child:  {concept_label(child_cid)}\n")
        out.write(f"  Parent: {concept_label(parent_cid)}\n\n")

    out.write("=" * 100 + "\n")
    out.write("END OF REPORT\n")
    out.write("=" * 100 + "\n")

# ============================================================
# Phase 6: Print markdown summary
# ============================================================
elapsed_total = time.time() - t0
print(f"\nReport saved to:\n  {OUTPUT_REPORT}")
print(f"Total elapsed: {elapsed_total:.1f}s")

print("\n--- MARKDOWN FOR FINDINGS.md ---\n")

print("## 4. Ontology subTypeOf vs AWN4 Hypernym Chains\n")
print("**Script:** `experiments/compare_hierarchies.py`")
print("**Output:** `experiments/hierarchy_comparison_report.txt`\n")
print("### Method")
print(f"For each of the {total} ontology subTypeOf pairs:")
print("1. Map child and parent concepts to AWN4 synsets via normalized lemma matching")
print(f"2. BFS up the AWN4 hypernym graph (max {MAX_HOPS} hops) from child synsets toward parent synsets")
print("3. Classify as AGREE / DISAGREE / PARTIAL / UNMATCHABLE\n")

print("### Results\n")
print("| Category | Count | % |")
print("|----------|------:|---:|")
print(f"| AGREE (hypernym path exists) | {n_agree} | {100*n_agree/total:.1f}% |")
print(f"| DISAGREE (both matched, no path) | {n_disagree} | {100*n_disagree/total:.1f}% |")
print(f"| PARTIAL (one side unmatched) | {n_partial} | {100*n_partial/total:.1f}% |")
print(f"| UNMATCHABLE (neither matched) | {n_unmatch} | {100*n_unmatch/total:.1f}% |")
print(f"| **Total** | **{total}** | **100%** |\n")

if hop_counts:
    print("#### Hop Distribution (AGREE cases)\n")
    print("| Hops | Count | % of AGREE |")
    print("|-----:|------:|-----------:|")
    for h in sorted(hop_counts):
        print(f"| {h} | {hop_counts[h]} | {100*hop_counts[h]/n_agree:.1f}% |")
    print(f"\nAverage path length: {avg_hops:.2f} hops")
