# Experiment: Arabic Ontology vs AWN4 Comparison

| | |
|---|---|
| **Date** | 2026-02-09 |
| **Scripts** | `find_matches.py`, `compare_hierarchies.py`, `validate_hierarchy.py` |
| **Status** | Complete |

---

## Motivation

The Arabic Ontology (13,755 Arabic-native concepts, Birzeit University / SinaLab) is the closest existing Arabic lexical resource to AWN4. This experiment answers two questions:

1. **Lemma overlap:** How much vocabulary do they share? Are they complementary or redundant?
2. **Structural agreement:** When both resources define the same concept, do they agree on how concepts relate hierarchically?

## Part 1: Side-by-Side Lemma Comparison

**Script:** `find_matches.py`

**Method:** Normalized lemma matching — strip diacritics, normalize alef variants (أ/إ/آ → ا), normalize alef maqsura (ى → ي), remove definite article (ال), strip trailing digits.

**Key findings:**
- **75.6%** of ontology concepts (10,406/13,755) have at least one matching AWN4 lemma
- ~1/3 of matches are **false friends** (same word form, different meaning):
  - كرسي = "academic chair/position" in Ontology vs "physical chair" in AWN4
  - فتوة = "Sufi chivalry" vs "youth/strength/bully"
  - زوج = "even number" vs "husband/spouse"
- AWN4 has extreme polysemy: رفع → 48 synsets, شغل → 30, قرع → 25
- The Ontology excels at Islamic/cultural vocabulary and richer synonymy; AWN4 excels at relational networks (hypernym/hyponym/meronym) and technical/modern vocabulary

**Conclusion:** Complementary resources, not competing. Integration feasible but requires human linguistic judgment — cannot be automated.

## Part 2: Hierarchy Comparison

**Scripts:** `compare_hierarchies.py`, `validate_hierarchy.py`

**Method:** For each of the 4,885 ontology subTypeOf pairs, map both parent and child to AWN4 via normalized lemma matching, then BFS up to 8 hops in AWN4's hypernym graph. Classify as AGREE / DISAGREE / PARTIAL / UNMATCHABLE.

**Critical discovery during experiment:** AWN4 was missing **78 upper-level OEWN noun synsets** (entity, physical entity, abstraction, object, organism, etc.), causing 2,836 disconnected noun roots. These were immediately restored (commit `1857565`), along with 6,076 hypernym/hyponym relations.

**Results after fix:**

| Category | Count | % |
|---|---|---|
| AGREE | 569 | 11.6% |
| DISAGREE | 974 | 19.9% |
| PARTIAL | 2,115 | 43.3% |
| UNMATCHABLE | 1,227 | 25.1% |

## Part 3: Manual Validation

**Script:** `validate_hierarchy.py`

Manual validation of 41 DISAGREE cases revealed the raw numbers overstate disagreement:
- ~41% are PARTIAL in disguise (ontology-native abstract parents matched to unrelated homographs)
- ~15% are total false friends on the child side (e.g., خُصّ "farmer's hut" matched to خصّ "to concern")
- ~20% are genuine structural differences (correct matches but AWN4 organizes differently — notably the worship-building cluster)
- ~12% are genuine ontology errors (e.g., بلدة subTypeOf قرية inverts size)
- ~7% are artifacts (self-matches)

**Corrected assessment:** ~6% genuine agreement, ~3% genuine disagreement, ~57% untestable. Where both resources correctly represent the same concept pair, they **agree ~2:1 over disagree**.

## Outputs

| File | Description |
|---|---|
| `ontology_vs_awn4_comparison.txt` | Full side-by-side match report |
| `hierarchy_comparison_report.txt` | AGREE/DISAGREE/PARTIAL breakdown |
| `validation_all_agree.txt` | Manual review of all 569 AGREE pairs |
| `validation_disagree_sample.txt` | Manual review of 41 DISAGREE pairs |
| `formal_hierarchy_mapping.md` | Formal mapping between the two hierarchies |
| `data/` | Arabic Ontology source data (Concepts.csv, Relations.csv) |
| `FINDINGS.md` | Full documented findings (sections 2–5) |

## Impact on Later Work

- **AWN4 fix:** Restored 78 missing upper-ontology synsets + 6,076 relations — direct improvement to the base resource
- **Polysemy observation:** The qualitative finding that رفع has 48 synsets was later quantified precisely by the pre-filter (Experiment 5: 5,378 groups, 12,496 synsets)
- **False-friend problem:** Underscored that normalized lemma matching alone is insufficient — motivating the evidence-package approach in later experiments

## Relationship to Other Experiments

```
This experiment ──→ Fixed AWN4 base resource (78 missing synsets)
                ──→ Qualitatively revealed polysemy explosion → quantified by prefilter/
                ──→ RESEARCH_IDEAS #1 (24.4% gap), #5 (orphan analysis), #9 (NULL relations)
```
