# Designing a human review methodology for Arabic WordNet 4.0

**A robust evaluation framework for AWN 4.0's 109,823 AI-translated synsets should combine multi-stage stratified sampling of ~1,500 synsets, a multi-dimensional scoring rubric (semantic accuracy, lemma quality, naturalness, completeness, cultural adequacy), Krippendorff's α as the primary inter-annotator agreement metric with a target of α ≥ 0.80 for binary judgments, and Arabic-specific validation checks for diacritization, morphological form, and dialectal contamination.** This methodology draws on three decades of multilingual WordNet construction—from EuroWordNet and BalkaNet through FinnWordNet and AWN V3—and adapts established practices to the unprecedented scale of AI-assisted lexical resource creation.

The challenge is substantial: AWN 4.0 represents the largest Arabic WordNet ever attempted, roughly **11× larger than AWN V3's 9,576 validated synsets**. While earlier Arabic WordNets were built through manual or semi-automatic methods with full expert review, AWN 4.0's AI-generated content requires a fundamentally different quality assurance strategy—one that balances statistical rigor with practical scalability. The research below synthesizes evaluation methodologies from dozens of multilingual WordNet projects, IAA standards from computational linguistics, Arabic-specific linguistic challenges, and sampling theory to produce an actionable review framework.

---

## Lessons from three decades of WordNet evaluation

Multilingual WordNet projects have converged on a shared evaluation paradigm with two complementary pillars: **automated structural checks** and **human quality assessment**. The most sophisticated automated framework comes from BalkaNet, where Smrž (2004) developed **27 quality control tests** covering DTD conformance, duplicate literal detection, cycle detection in hierarchies, dangling uplink identification, base concept coverage verification, and cross-lingual alignment consistency. These tests—categorized as language-universal or language-specific, fully automatic or requiring manual input—remain the gold standard for structural validation and should be implemented as a first-pass filter for AWN 4.0 before any human review begins.

For human evaluation, projects have used strikingly different scales. **FinnWordNet**, built by professional translators rendering 208,645 word senses from PWN 3.0 into Finnish in ~100 days, evaluated quality across five dimensions: spelling correctness, translation accuracy, synonym quality at both lexeme and concept levels, and usefulness for NLP tasks. The Japanese WordNet adopted a simpler approach, reporting an official **~5% error rate** as acceptable for release. The Hindi WordNet and IndoWordNet enforced three core principles—**minimality, coverage, and replaceability**—as quality criteria, with every synset validated by lexicographers. MultiWordNet (Italian) innovated by explicitly quantifying lexical gaps between English and Italian, finding the two lexica "highly comparable" and using this comparability as an empirical quality metric.

**AWN V3** (Freihat, Khalilia, Bella & Giunchiglia, 2024) provides the most directly relevant precedent. Its two-phase validation—two translators cross-validating each other's work, followed by an Arabic language expert approving final results—updated over 58% of existing AWN synsets. The project identified **236 lexical gaps** and created **701 phrasets** (multi-word paraphrases for untranslatable concepts), establishing mechanisms that AWN 4.0 should adopt and extend. AWN V3 also removed 8,751 incorrect lemmas from earlier versions—a stark reminder that earlier Arabic WordNets suffered from serious quality deficits, with Batita & Zrigui (2018) describing AWN as having "very poor content in both quantity and quality levels."

---

## A multi-dimensional scoring rubric for translation quality

No single universal scoring framework for WordNet quality exists, but synthesizing approaches across projects yields a recommended rubric with **six evaluation dimensions**, each scored on a defined scale.

**Semantic accuracy** (Does the Arabic synset capture the correct meaning of the English source?) is the most critical dimension. Projects have used both binary (correct/incorrect) and ordinal scales here. The WMT Multidimensional Quality Metrics (MQM) framework, widely used in machine translation evaluation, provides an error typology with severity weighting (critical/major/minor) that transfers well to WordNet evaluation. For AWN 4.0, a **4-point scale** is recommended: 3 = fully accurate, 2 = mostly accurate with minor issues, 1 = partially accurate with significant issues, 0 = incorrect or unrelated meaning. This avoids the neutral midpoint of 5-point Likert scales that annotators tend to overuse.

**Lemma appropriateness** evaluates whether each Arabic word in the synset is a valid translation of the concept. This should be scored per-lemma as binary (valid/invalid), with invalid lemmas further categorized: non-existent Arabic word, dialectal form, wrong part of speech, semantically distant, or morphologically malformed. **Synonym coherence** assesses whether the Arabic lemmas within a synset are truly interchangeable in context—FinnWordNet evaluated this at both lexeme and concept levels, a distinction worth preserving. **Gloss and example quality** checks Arabic definitions and usage examples for grammatical correctness, naturalness, and informativeness. **Completeness** evaluates whether the synset includes sufficient Arabic synonyms and all required structural elements. **Cultural-linguistic adequacy** captures whether culture-specific concepts are handled appropriately through direct translation, phrasets, lexical gap annotation, or adaptation.

The following scoring matrix captures the recommended rubric:

| Dimension | Scale | Anchors |
|-----------|-------|---------|
| Semantic accuracy | 0–3 | 0 = wrong meaning, 1 = partially correct, 2 = mostly correct, 3 = fully correct |
| Lemma validity | Binary per lemma | Valid / Invalid (with error subtype) |
| Synonym coherence | 0–2 | 0 = not synonymous, 1 = partially synonymous, 2 = fully synonymous |
| Gloss quality | 0–3 | 0 = missing/unintelligible, 1 = poor, 2 = adequate, 3 = excellent |
| Completeness | 0–2 | 0 = critically incomplete, 1 = partially complete, 2 = complete |
| Cultural adequacy | Categorical | Direct translation / Phraset needed / Lexical gap / Adaptation required |

Quality thresholds from comparable projects suggest targets of **≥90% of synsets scoring 2–3 on semantic accuracy** (informed by Lam et al.'s 90% precision benchmark for automatic WordNet construction and FinnWordNet's professional translator standard) and **≥85% of lemmas rated valid**.

---

## Inter-annotator agreement: metrics, thresholds, and practical design

The canonical reference for IAA in computational linguistics remains Artstein & Poesio (2008), who argue that **Krippendorff's α is the most suitable general-purpose reliability metric** for annotation projects. It handles any number of annotators, accommodates missing data, and supports nominal, ordinal, interval, and ratio measurement scales through appropriate distance functions. For AWN 4.0's mixed evaluation scheme—combining binary lemma judgments with ordinal quality ratings—this flexibility is essential.

Three threshold frameworks guide interpretation. **Krippendorff (2019)** sets the strictest standards: α ≥ 0.80 for reliable data, **0.667 ≤ α < 0.80** for tentative conclusions, and α < 0.667 as unreliable. Carletta (1996), who introduced kappa to computational linguistics, proposed κ ≥ 0.80 for "good reliability" and κ ≥ 0.67 as allowing "tentative conclusions." The Landis & Koch (1977) scale classifies κ = 0.61–0.80 as "substantial" and κ = 0.81–1.00 as "almost perfect" agreement.

WordNet-specific IAA benchmarks reveal that **fine-grained sense annotation is inherently difficult**. Senseval campaigns found human inter-tagger agreement of ~95% at coarse-grained level but only ~85% for fine-grained WordNet senses, with raw agreement of 70–80% typical for the latter (Navigli, 2009). The MASC WordNet Sense Annotation Project used 4–6 annotators per round with Krippendorff's α computed via Artstein's scripts. The IAMTC multilingual annotation project (Passonneau, Habash & Rambow, 2006)—directly relevant as it included Arabic—achieved κ ranging from **0.65 for all annotators to 0.87 for the two best annotators** on WordNet-derived concept annotation. The most impressive recent result comes from the DWUG DE Sense diachronic study, which achieved α = 0.87 across three annotators—attributed to careful inventory design.

For AWN 4.0, realistic targets are **α ≥ 0.80 for binary judgments** (lemma validity, overall acceptability) and **α ≥ 0.67 for ordinal ratings** (semantic accuracy, gloss quality), using Krippendorff's α with ordinal distance function for the latter and nominal distance for the former. Cohen's κ should supplement as a pairwise diagnostic to identify individual annotator biases.

**Disagreement handling** should follow a structured protocol: independent dual annotation → automatic flagging of disagreements → expert adjudication with documented rationale → periodic guideline revision based on disagreement patterns. The MASC project demonstrated that disagreements can productively reveal sense inventory problems, leading to revisions of the annotation scheme itself. For AWN 4.0, persistent disagreements likely signal genuine ambiguity in AI-translated content and should be preserved as metadata rather than forcibly resolved.

---

## Arabic-specific challenges demand specialized evaluation criteria

Arabic presents a constellation of linguistic challenges that generic WordNet evaluation misses entirely. The **root-pattern (جذر-وزن) morphological system** means that lemmatization—the foundation of WordNet entries—is inherently more complex than for European languages. Best-in-class Arabic morphological analyzers (Farasa, MADAMIRA, CAMeL Tools) achieve ~96–97% lemmatization accuracy, meaning that even with perfect AI translation, **3–4% of entries may have morphologically malformed lemmas**. Every Arabic lemma in AWN 4.0 should be validated against a morphological analyzer as an automated pre-filter.

**Diacritization (tashkeel)** creates perhaps the most acute evaluation challenge. Without diacritics, the undiacritized string عقد can represent 8+ different words—contract, necklace, decade, complexes, and more. AWN V1 had inconsistent vocalization: "Arabic words were in some cases vocalized and in others not" (Rodríguez et al., 2008). AWN 4.0 must establish a clear, explicit diacritization policy before review begins. The recommended approach is **minimum disambiguating diacritics**: shadda (gemination marker) always present, plus vowels necessary to distinguish homographs, without requiring full tashkeel for every entry. This balances disambiguation needs with annotator workload.

**Dialectal contamination** is a particular risk with AI-generated translations. Google Gemini's training data includes dialectal Arabic alongside MSA, meaning translations may inadvertently include Egyptian, Levantine, or Gulf forms. The word for "car" alone illustrates the problem: سيارة (MSA) vs. عربية (Egyptian) vs. توموبيل (Moroccan). Reviewers must be trained to identify and flag dialectal forms, with only MSA accepted.

**Broken plurals** (~41% of Arabic noun types use non-concatenative plural patterns) require specific handling conventions. Following AWN V2's precedent, the singular indefinite form should serve as the primary lemma, with broken plural forms recorded as morphological metadata rather than separate entries. AI-generated content may inconsistently use plural forms as lemmas, making this a targeted check item.

For AI-translation-specific quality issues, reviewers should watch for five common error types:

- **Literal translation artifacts** where word-by-word rendering produces unnatural Arabic
- **Polysemy inheritance** where English polysemy incorrectly inflates Arabic sense counts
- **Hallucinated Arabic words** that morphological analyzers cannot validate
- **Named entity contamination** where proper nouns appear as regular lexical entries
- **Technical terminology mishandling** where established Arabic terms (from language academies) are ignored in favor of ad hoc transliterations

---

## Stratified sampling to evaluate 110K synsets efficiently

For a population of 109,823 synsets, standard sample size calculations yield **n ≈ 383 for ±5% margin of error and n ≈ 1,067 for ±3% margin of error** at 95% confidence (using n = Z²p(1-p)/E² with p = 0.5 for maximum variability, adjusted for finite population). However, the need for subgroup analysis across POS categories, semantic domains, and confidence bands pushes the practical requirement to **1,500–2,000 synsets**.

A **three-stage sampling protocol** maximizes information yield:

**Stage 1 — Pilot (n = 300–500 synsets).** All annotators review the same items. Stratify across all four POS categories (with minimum 50 per category), 5–6 major semantic domains, and 3 frequency bands. Purpose: calibrate guidelines, estimate per-stratum error rates, compute initial IAA, identify annotation scheme ambiguities. Run two pilot rounds with guideline revision between them. Target timeline: 1–2 weeks per round.

**Stage 2 — Main evaluation (n = 1,000–1,500 synsets).** Informed by pilot error rates, use **Neyman allocation** (sample sizes proportional to stratum size × stratum standard deviation) to over-sample high-error categories. Dual-annotate 20–30% for ongoing IAA monitoring; single-annotate the remainder with expert spot-checking and embedded gold-standard "honeypot" items. Over-sample these high-risk categories: low-confidence MT translations, culture-sensitive semantic domains (religion, kinship, food, law), highly polysemous source synsets, and adverbs/adjectives (which translation literature consistently identifies as harder than nouns).

**Stage 3 — Targeted deep dive (n = 300–500 synsets).** Focus exclusively on problematic categories identified in Stage 2—specific domains with elevated error rates, specific translation error types, or synsets near confidence-score decision boundaries.

The POS distribution in WordNets heavily favors nouns (~70%), with verbs (~12%), adjectives (~15%), and adverbs (~3%) as minorities. Proportionate sampling would leave adverb subsamples too small for meaningful analysis. The solution is **proportionate allocation with minimum floors**: at least 100–150 adverbs, 200 verbs, 200 adjectives, and 700–800 nouns across the total evaluation sample.

---

## Cultural adaptation through a graduated response framework

The expand model underlying AWN 4.0—translating from English WordNet into Arabic—inherits a well-documented **Anglo-Saxon conceptual bias**. EuroWordNet formalized two alternative approaches: the expand model (translate from source language, inherit relations) and the merge model (build independently, align afterward). The expand model is faster but forces English conceptual structures onto the target language. AWN 4.0, having used the expand approach at unprecedented scale, will inevitably contain thousands of synsets where direct translation is inadequate.

Freihat et al.'s (2024) innovations for AWN V3 provide the clearest action framework, introducing two structural mechanisms: **lexical gaps** (explicit markers that a concept has no Arabic lexicalization) and **phrasets** (multi-word paraphrases expressing the concept). AWN V3 identified 236 lexical gaps and 701 phrasets in just 9,576 synsets. Extrapolating to AWN 4.0's scale, the review process should expect to identify **several thousand synsets** requiring cultural adaptation.

A **graduated response taxonomy** should guide reviewer decisions for each problematic synset:

- **Direct translation** — one-to-one correspondence exists; standard case
- **Near-synonym approximation** — closest available Arabic term, annotated with eq_near_synonym alignment type (per EuroWordNet conventions)
- **Phraset** — no single word exists, but the concept is expressible as a natural Arabic multi-word expression
- **Lexical gap with gloss** — concept is culturally foreign but comprehensible; mark as lexical gap, provide explanatory Arabic gloss
- **Omission candidate** — concept is entirely irrelevant to Arabic (e.g., culture-specific institutional terms like "hanging chad"); flag for project-level decision

Arabic-specific domains requiring particular attention include **kinship terminology** (Arabic has far more specific terms than English, with separate words for paternal and maternal relatives—a case where Arabic is richer, not poorer), **religious terminology** (rich Islamic vocabulary with no English parallel, and English Christian terminology lacking Arabic equivalents), and **food/culinary terms** (Bella et al., 2023, found 2,140 lexical gaps in English-Arabic food terminology alone). The review guidelines should include a domain-specific checklist for these high-risk areas.

All cultural adaptation decisions should be recorded using CILI (Collaborative Interlingual Index) alignment types—eq_synonym, eq_near_synonym, eq_has_hypernym, eq_has_hyponym—to maintain cross-lingual interoperability and enable future research on lexical gaps.

---

## Workflow architecture for reproducibility and scale

The practical infrastructure for reviewing 109,823 synsets demands careful workflow engineering. **INCEpTION** (Klie et al., 2018) emerges as the strongest annotation platform candidate, offering knowledge base integration (enabling direct linking to WordNet/OEWN), multi-annotator workflows with built-in curation, IAA computation, and active learning support. However, WordNet review is fundamentally a structured-record task rather than text annotation, so a **custom web application** or enhanced spreadsheet system (following AWN V3's precedent) with automated IAA computation scripts may prove more practical. Label Studio offers a flexible middle ground with customizable templates and ML backend integration.

Documentation standards should follow the **MATTER cycle** (Model, Annotate, Train, Test, Evaluate, Revise) from Pustejovsky & Stubbs (2012), with annotation guidelines containing: task definition, annotation taxonomy with formal criteria, step-by-step decision procedures, 2–3 positive and negative examples per category including borderline cases, and a living edge-case repository updated throughout the project. Bloomberg's (2020) annotation management guidelines further recommend designating a **single guideline owner** for consistency, embedding guidelines within the annotation tool (not as a separate document), and communicating changes promptly to all annotators.

Annotator fatigue management is critical at this scale. Recommended practices include **limiting sessions to 2–4 hours** with enforced breaks, keeping batch sizes at 50–200 synsets, rotating annotators between POS categories or domains, embedding gold-standard honeypot items to automatically detect accuracy drops, and holding weekly calibration sessions to maintain alignment. Per-batch IAA monitoring should track quality trends over time, with automatic alerts when agreement drops below threshold.

The full quality assurance pipeline should proceed in this order:

1. **Automated structural validation** — implement BalkaNet-style checks for XML conformance, duplicate detection, relation consistency, and cycle detection
2. **Automated linguistic validation** — morphological analyzer verification of all Arabic lemmas, spell-checking, diacritization consistency checks
3. **Pilot human evaluation** — 300–500 synsets, all annotators, two rounds with guideline refinement
4. **Main human evaluation** — 1,000–1,500 stratified synsets with IAA monitoring
5. **Expert adjudication** — resolution of disagreements and review of flagged items
6. **Targeted deep dives** — focused review of high-error categories
7. **Statistical reporting** — overall and per-stratum accuracy estimates with confidence intervals

---

## Conclusion

The proposed methodology for AWN 4.0 represents a synthesis of best practices across the entire multilingual WordNet tradition, adapted to the novel challenge of evaluating AI-generated content at scale. Three insights are particularly important for the project.

First, **automated pre-filtering is essential and underused**. BalkaNet's 27-test framework, supplemented by Arabic morphological analysis, can eliminate a substantial fraction of errors before any human reviewer sees them—dramatically improving the efficiency of expensive human evaluation time. Second, the AWN V3 innovations of **lexical gaps and phrasets** should be adopted as first-class structural elements in AWN 4.0, not treated as edge cases. At 110K synsets, the number of culture-specific adaptation challenges will be an order of magnitude larger than what AWN V3 encountered. Third, the **multi-stage sampling design** (pilot → main → targeted) is not merely a statistical convenience but a methodological necessity: pilot results will reveal which strata harbor the highest error rates, enabling efficient allocation of the most expensive resource—expert Arabic linguist time—to where it matters most.

The field lacks a standardized evaluation framework for WordNet quality, but AWN 4.0 is positioned to establish one. By rigorously documenting the review methodology, publishing the annotation guidelines, and releasing IAA statistics alongside the resource, the project can contribute not only the largest Arabic WordNet but also a replicable evaluation methodology for future AI-assisted lexical resource construction in any language.