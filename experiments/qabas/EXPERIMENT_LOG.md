# Experiment: Qabas Lexicon Exploration

| | |
|---|---|
| **Date** | 2026-02-09 |
| **Type** | Data exploration (no scripts) |
| **Status** | Complete |

---

## Motivation

Understand the Qabas morphological lexicon (~58K lemmas, Birzeit University / SinaLab) as a potential enrichment source for AWN4 — particularly its morphological data (roots, augmentation patterns, transitivity, voice, gender).

## Data

- **Qabas-dataset.csv** — ~58,000 lemmas
  - Columns: lemma_id, lemma, language, pos_cat, pos, root, augmentation, number, person, gender, voice, transitivity, uninflected
  - Language breakdown: 50,899 MSA, 6,045 foreign, 1,522 colloquial
  - POS: overwhelmingly nouns (57,983 اسم), 483 function words (كلمة وظيفية)
- **Qabas-SAMA-Mapping.csv** — SAMA morphological analyzer mappings

## Findings

1. **Missing cross-references:** The Qabas website claims 87% linkage to the Arabic Ontology (28,435 entries linked) and coverage of 110 dictionaries. The downloadable CSV contains **none of these cross-references** — only core morphological data and a SAMA mapping. Ontology terms exist as flat entries but with no parent-child relationships encoded.

2. **Useful morphological data:** Root, augmentation pattern, transitivity, voice, and gender are available per lemma. This could enrich AWN4 entries that currently lack root information.

3. **Flat structure:** No hierarchy, no semantic relations, no definitions, no examples. Purely morphological.

## Impact on Later Work

- Informed `RESEARCH_IDEAS.md` item 3 (Qabas morphological enrichment) and item 6 (root-based semantic clustering)
- Not directly used in subsequent experiments — the dictionary DB (المعجم الوسيط, المعجم الكبير) became the primary evidence source instead

## Relationship to Other Experiments

```
This experiment ──→ RESEARCH_IDEAS #3 (morphological enrichment, not started)
                ──→ RESEARCH_IDEAS #6 (root-based clustering, not started)
```
