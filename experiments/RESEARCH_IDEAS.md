# Research Ideas — Linguistic Resource Exploration

Potential analyses and studies across AWN4, the Arabic Ontology, and Qabas.

---

## High Value — Directly Improvable

### 1. The 24.4% Gap: Ontology Concepts with No AWN4 Match
~3,350 ontology concepts have no matching lemma in AWN4. These are candidates for genuinely missing Arabic-native meanings. Extract them, categorize by domain (Islamic, cultural, scientific, etc.), and assess which represent real gaps worth adding to AWN4.

- **Input:** Arabic Ontology Concepts.csv, AWN4 lemma index
- **Output:** Categorized list of missing concepts with priority ranking

### 2. AWN4 Translation Quality Audit
AWN4 was AI-translated via Google Gemini. Sample synsets and evaluate: Do Arabic definitions read naturally? Are examples culturally appropriate or do they feel like translated English? (e.g., the baseball sense of آمن, the pumpkin senses of قرع — are these useful for Arabic speakers?)

- **Input:** AWN4 synsets (sampled)
- **Output:** Quality scores, list of problematic translations, culturally misfit entries

### 3. Qabas Morphological Enrichment
Qabas has root, augmentation pattern, transitivity, voice, and gender for ~58K lemmas. Match these against AWN4 entries and quantify: How many AWN4 lemmas could gain root information? Could transitivity data help disambiguate verb senses?

- **Input:** Qabas-dataset.csv, AWN4 lexical entries
- **Output:** Match rate, enrichable entry count, sample enrichments

### 4. ~~Ontology Hierarchy vs AWN4 Hypernym Chains~~ DONE
Completed. See FINDINGS.md sections 4 and 5. Automated comparison of 4,885 subTypeOf pairs followed by manual linguistic validation of all 319 AGREE and 41 DISAGREE cases. Key finding: ~6% genuine agreement, ~3% genuine disagreement, ~57% untestable due to matching limitations. Where both resources correctly match, they agree ~2:1 over disagree. The raw 24.9% DISAGREE rate was inflated — over half were PARTIAL cases disguised by false-friend matching.

- **Scripts:** `experiments/compare_hierarchies.py`, `experiments/validate_hierarchy.py`
- **Output:** `experiments/hierarchy_comparison_report.txt`, `experiments/validation_all_agree.txt`, `experiments/validation_disagree_sample.txt`, FINDINGS.md sections 4–5

---

## Medium Value — Structural Analysis

### 5. AWN4 Relation Density and Orphan Analysis
265,676 relations across 109,823 synsets — but how are they distributed? Are some synsets completely isolated (no hypernym, no hyponym)? Are there broken chains? This would be a health check on AWN4's internal structure.

- **Input:** AWN4 synset relations
- **Output:** Distribution histogram, list of orphan synsets, chain integrity report

### 6. Root-Based Semantic Clustering
Using Qabas roots + AWN4 lemmas: Do entries sharing the same trilateral root cluster under related synsets? Arabic morphology predicts semantic relatedness from shared roots — does AWN4's structure reflect this, or does the English-origin hierarchy break Arabic root-based intuitions?

- **Input:** Qabas roots, AWN4 lemma-to-synset mappings
- **Output:** Clustering analysis, examples of root coherence vs divergence

### 7. POS Distribution Comparison
The Ontology doesn't explicitly tag POS but its synsets mix nouns, verbs, and adjectives freely. AWN4 strictly separates them. Compare how each resource handles multi-POS lemmas (e.g., صريح as adj vs noun) to reveal systematic patterns.

- **Input:** AWN4 POS tags, Ontology synsets, Qabas pos_cat/pos fields
- **Output:** POS distribution tables, cross-resource comparison

### 8. Cultural Relevance Filtering
Identify AWN4 synsets that are culturally irrelevant or misleading for Arabic speakers (baseball terminology, English-specific legal concepts, Christian-specific religious terms applied to Islamic contexts). Candidates for removal or re-annotation.

- **Input:** AWN4 synsets with domain_topic relations
- **Output:** Flagged synsets by category, removal/adaptation recommendations

---

## Exploratory — Deeper Questions

### 9. The Ontology's NULL-Relation Majority
Most Ontology concepts have no subTypeOf, partOf, or instanceOf. Are these genuinely root-level concepts, or is the Ontology simply incomplete? Analyze whether NULL-relation concepts differ in quality (shorter glosses? missing examples?) from those with relations.

- **Input:** Ontology Concepts.csv + Relations.csv
- **Output:** Quality comparison metrics (gloss length, example presence, synonym count) for related vs unrelated concepts

### 10. DataSource Analysis Within the Ontology
The 5 data sources (43, 38, 303, 200, 455) may represent different quality levels, domains, or time periods. Compare them to reveal whether some sources are more suitable for integration than others.

- **Input:** Ontology Concepts.csv (dataSourceId field)
- **Output:** Per-source statistics (size, gloss quality, English coverage, relation density)

### 11. Synonym Set Comparison
The Ontology often has 10–25 synonyms per concept while AWN4 has 1–4 lemmas per synset. Systematically check: Do the Ontology's extra synonyms exist somewhere in AWN4 (under different synsets), or are they genuinely missing from the wordnet?

- **Input:** Ontology arabicSynset fields, AWN4 lemma index
- **Output:** Coverage rate, list of synonyms absent from AWN4 entirely

### 12. ILI Linkage Analysis
Every AWN4 synset has an ILI (Inter-Lingual Index) link. Check which ILI concepts have no Arabic entry at all — these are "holes" in Arabic's representation within the global wordnet ecosystem.

- **Input:** AWN4 ILI mappings, full ILI index
- **Output:** Coverage percentage, gap analysis by semantic domain
