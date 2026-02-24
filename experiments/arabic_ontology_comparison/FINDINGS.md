# Linguistic Resource Exploration — Findings

Branch: `explore/linguistic-resources`

---

## Resources Under Study

| Resource | Type | Size | Format | Source |
|----------|------|------|--------|--------|
| **Arabic WordNet 4.0 (AWN4)** | Lexical database | 109,823 synsets, 124,653 entries, 166,643 senses | WN-LMF 1.4 XML | This project (AI-translated from OEWN 2024) |
| **Arabic Ontology** | Hierarchical taxonomy | 13,755 concepts | CSV (Concepts + Relations) | Birzeit University / SinaLab |
| **Qabas Lexicon** | Morphological lexicon | ~58,000 lemmas | CSV | Birzeit University / SinaLab |

---

## 1. Qabas Lexicon

**Location:** `experiments/qabas/`

### Structure
- Flat morphological lexicon with no hierarchy or semantic relations
- Columns: lemma_id, lemma, language, pos_cat, pos, root, augmentation, number, person, gender, voice, transitivity, uninflected
- Language breakdown: 50,899 Modern Standard Arabic, 6,045 foreign, 1,522 colloquial
- POS: overwhelmingly nouns (57,983 اسم), 483 function words (كلمة وظيفية)

### Key Finding
- Qabas website claims linkage to the Arabic Ontology (28,435 entries, 87% linked) and 110 dictionaries, but **the downloadable CSV contains none of these cross-references** — only core morphological data and SAMA mapping
- Ontology terms exist as flat entries in Qabas but with no parent-child relationships encoded

---

## 2. Arabic Ontology

**Location:** `experiments/arabic-ontology/`

### Structure
- **Concepts.csv**: conceptId, arabicSynset (pipe-separated synonyms with diacritics), englishSynset, gloss, example, dataSourceId
- **Relations.csv**: concept_id, subTypeOfID, partOfID, instanceOfID
- Root entity: 293198 (كينونة / entity) with 5 top-level children: object, dependent entity, occurrent, information, abstract
- 107 additional NLP domain roots (IDs 334000001–334000113)
- Relations: 4,885 subTypeOf, 17 partOf, 9 instanceOf; remainder NULL
- 86% of concepts have no English equivalent (Arabic-native)
- DataSources: 43 (general, 8,741), 38 (Islamic jurisprudence, 1,796), 303 (1,298), 200 (780), 455 (523)

### How It Differs from AWN4
| Dimension | Arabic Ontology | AWN4 |
|-----------|----------------|------|
| Scale | 13,755 concepts | 109,823 synsets |
| Structure | Single layer (concept → relations) | Three layers (entry → sense → synset) |
| Origin | Arabic-native definitions | Translated from English WordNet |
| Relation types | 3 (subTypeOf, partOf, instanceOf) | 21 (hypernym, hyponym, meronym, etc.) |
| Format | CSV | WN-LMF 1.4 XML |
| Cultural coverage | Strong (Islamic, classical Arabic) | Weak (inherits English cultural bias) |

---

## 3. Arabic Ontology vs AWN4 — Side-by-Side Comparison

**Script:** `experiments/find_matches.py`
**Output:** `experiments/ontology_vs_awn4_comparison.txt` (35 entries, 3,988 lines)

### Matching Statistics
- Matching method: normalized lemma overlap (strip diacritics, normalize alef, remove trailing digits)
- **10,406 / 13,755 (75.6%)** ontology concepts have at least one matching AWN4 lemma
- 35 random entries selected (seed=42) for manual comparison

### Assessment

#### A. Conceptual Architecture Mismatch
The Ontology groups rich synonym sets under a **single concept** (e.g., 28 verbs under "issuing a command"). AWN4 follows Princeton WordNet's fine-grained **sense disambiguation** (e.g., أمر splits into 19 synsets). This reflects different lexicographic philosophies: the Arab rhetorical tradition of grouping meanings vs. the analytic tradition of decomposing polysemy.

#### B. Polysemy Explosion in AWN4
High-frequency Arabic lemmas produce extreme fan-out in AWN4:

| Lemma | Ontology Meaning | AWN4 Synsets |
|-------|-----------------|:--:|
| رفع | becoming thin | 48 |
| شغل | employing | 30 |
| قرع | going bald | 25 |
| أمر | commanding | 19 |
| وسط | placing in middle | 16 |
| أمن | securing | 16 |
| هز | becoming active | 15 |

#### C. Semantic Mismatches (~1/3 of entries)
In roughly one-third of the 35 matched entries, the lemma match is a **false friend** — the two resources define entirely different meanings of the same word form:

| Lemma | Ontology Meaning | AWN4 Meaning | Issue |
|-------|-----------------|--------------|-------|
| كرسي | academic chair/position | physical chair/seat | Different sense entirely |
| فتوة | Sufi spiritual chivalry | youth, muscular strength, bully | Islamic concept lost |
| زوج | even number (fiqh term) | husband, spouse, pair, marry | Mathematical sense missing |
| رفع | becoming thin/emaciated | raising/lifting (all 48 senses) | Rare Arabic sense absent from AWN4 |
| ضنى | offspring/descendants | yearning/longing | False friend after normalization |
| ركض | kicking with foot | running | Both valid but different |
| قرع | going bald from disease | knocking, drumming, pumpkins | Specific sense absent |
| عارض | welcoming face-to-face | opposing, disagreeing, projector | Welcoming sense absent |
| دليل | prophet/messenger | evidence, guide, directory | Prophetic sense absent |
| باطل | lying/falsehood | invalid (legal), wrong | Different semantic field |

#### D. Where the Ontology Excels
- **Islamic and cultural vocabulary**: DataSource 38 entries carry meanings rooted in classical Arabic scholarly traditions that AWN4 misses
- **Richer synonymy**: Ontology synsets contain authentic Arabic synonyms (e.g., 25 near-synonyms for falsehood in entry باطل)
- **Arabic-native glosses**: Definitions written as natural Arabic explanations with cultural context

#### E. Where AWN4 Excels
- **Relational richness**: hypernym/hyponym/meronym networks (e.g., شركة has 36 hyponyms)
- **Concrete/universal concepts**: telescope, jubilee, ooze, slide — well-structured with examples
- **Technical/modern vocabulary**: computer science, physics, professional language inherited from English WordNet

#### F. Normalization Trap
Diacritic stripping creates false matches: ضَنًى (offspring) vs ضنى (yearning), قَيّاسٌ (surveyor, person) vs قياس (measurement, act). The diacritics that were stripped actually disambiguate different words.

### Conclusion
The two resources are **complementary, not competing**. A merged resource would use AWN4's structural framework and relational richness, augmented with the Ontology's Arabic-native concepts, culturally-specific meanings, and rich synonym sets. The 75.6% lemma overlap suggests integration is feasible, but the semantic mismatches require human linguistic judgment — it cannot be automated.

---

## 4. Ontology subTypeOf vs AWN4 Hypernym Chains

**Script:** `experiments/compare_hierarchies.py`
**Output:** `experiments/hierarchy_comparison_report.txt`

### Method
For each of the 4,885 ontology subTypeOf pairs:
1. Map child and parent concepts to AWN4 synsets via normalized lemma matching
2. BFS up the AWN4 hypernym graph (max 8 hops) from child synsets toward parent synsets
3. Classify as AGREE / DISAGREE / PARTIAL / UNMATCHABLE

### Results (after AWN4 upper-ontology fix)

AWN4 was initially missing 78 upper-level OEWN noun synsets (entity, physical entity, abstraction, object, organism, etc.), causing 2,836 disconnected noun roots. After restoring these synsets and 6,076 hypernym/hyponym relations, the results improved significantly:

| Category | Before Fix | After Fix | Change |
|----------|------:|------:|--------|
| AGREE (hypernym path exists) | 319 (6.5%) | **569 (11.6%)** | **+250 (+78%)** |
| DISAGREE (both matched, no path) | 1,217 (24.9%) | 974 (19.9%) | -243 |
| PARTIAL (one side unmatched) | 2,113 (43.3%) | 2,115 (43.3%) | ~same |
| UNMATCHABLE (neither matched) | 1,236 (25.3%) | 1,227 (25.1%) | ~same |
| **Total** | **4,885** | **4,885** | |

#### Hop Distribution (AGREE cases, after fix)

| Hops | Count | % of AGREE |
|-----:|------:|-----------:|
| 1 | 257 | 45.2% |
| 2 | 125 | 22.0% |
| 3 | 63 | 11.1% |
| 4 | 63 | 11.1% |
| 5 | 37 | 6.5% |
| 6 | 17 | 3.0% |
| 7 | 6 | 1.1% |
| 8 | 1 | 0.2% |

Average path length: 2.26 hops (was 1.48)

### Interpretation

**11.6% of ontology parent-child pairs now have a confirmed hypernym path in AWN4**, nearly double the pre-fix rate. The improvement is explained by:

1. **250 new AGREE cases** came from the restored upper hierarchy. The Ontology's abstract parent concepts (entity, organism, object, etc.) now exist in AWN4 as hypernym targets, so BFS can find paths that previously dead-ended at missing synsets.

2. **243 fewer DISAGREE cases**: Many former "disagreements" were caused by the missing upper levels — child synsets existed but couldn't reach their parents because the intermediate hierarchy was absent. With it restored, these become agreements.

3. **Average hops increased from 1.48 to 2.26**: The new agreements include longer paths through the restored upper hierarchy (e.g., animal→organism→living thing→whole→object→physical entity). The 1-hop share dropped from 70.5% to 45.2% as longer-distance agreements became possible.

4. **PARTIAL remains dominant (43.3%)**: The largest category is still pairs where only one side matches AWN4. This is inherent to the lemma-matching method — the Ontology contains many Arabic-native concepts with no AWN4 equivalent.

5. **False-friend contamination in DISAGREE (19.9%)**: As documented in section 3C, normalized lemma matching produces false friends. The real disagreement rate is likely lower — many DISAGREE cases are PARTIAL in disguise (see section 5 for manual validation).

### Conclusion

Restoring AWN4's upper-level hierarchy nearly doubled the agreement rate from 6.5% to 11.6%. The remaining gap is dominated by untestable pairs (43% PARTIAL + 25% UNMATCHABLE) rather than genuine structural conflicts. Where both resources correctly represent the same concept pair, they agree roughly twice as often as they disagree — a finding consistent with the manual validation in section 5.

---

## 5. Manual Linguistic Validation of Hierarchy Comparison

**Script:** `experiments/validate_hierarchy.py`
**Output:** `experiments/validation_all_agree.txt`, `experiments/validation_disagree_sample.txt`

### Method
Manual review of all 319 AGREE cases and 41 DISAGREE cases (of 1,217), examining:
- Whether the matched AWN4 synsets correspond to the intended senses of the ontology concepts
- Whether hypernym paths are linguistically valid or artifacts of false-friend matching
- Automated quality indicators: POS consistency, same-lemma self-matching, polysemy explosion

### Quality Indicators (automated)
- **POS consistency in AGREE:** 319/319 (100%) — child and parent AWN4 synsets always share the same POS. Good sign.
- **Same-lemma self-matches in AGREE:** 34/319 (10.7%) — cases where child and parent ontology concepts share a lemma form, so the "agreement" may just be matching the same polysemous word to its own hypernym chain.
- **Adjective contamination in DISAGREE:** 289/1,217 (23.7%) — nearly a quarter of DISAGREE cases have adjective synsets mixed into their noun matches, indicating false-friend pollution.
- **Polysemy explosion in DISAGREE:** 616/1,217 (50.6%) have parent matched to >10 synsets — the parent concept fans out to so many AWN4 senses that the correct one is drowned out.

### AGREE Validation (319 cases reviewed, first 67 in detail)

#### Genuinely Correct: ~85%
The majority of AGREE cases are linguistically sound. Strongest domains:

- **Biological taxonomy** (fungi, plants, animals, fish): Near-perfect alignment. Both resources derive from universal scientific classifications. فطر دعامي→فطر (basidiomycete→fungus), نبات وعائي→نبات (vascular plant→plant), حيوان فقاري→حيوان حبلي (vertebrate→chordate) — all correct.
- **Geography/water bodies**: بحر→مسطح مائي (sea→body of water), نهر→مجرى مائي (river→waterway), خليج→مسطح مائي (gulf→body of water) — perfect alignment.
- **Mathematics**: عدد حقيقي→عدد مركب (real→complex number), مجموعة فارغة→مجموعة (empty set→set), عدد غير نسبي→عدد حقيقي (irrational→real) — correct.
- **Time periods**: قرن→فترة (century→period), فصل→فترة (season→period), عقد→فترة (decade→period) — correct.
- **Built environment**: منجم فحم→منجم (coal mine→mine), محطة قطار→محطة (train station→station), مول→متجر (mall→shop) — correct.

#### False Positives: ~6%
Cases where the hypernym path exists but connects wrong senses:

| # | Ontology pair | What AWN4 actually matched | Problem |
|---|---|---|---|
| 4 | مصنع أسلحة→مصنع (weapons factory→factory) | "person who makes weapons"→"person who makes things" | Matched agents, not locations |
| 20 | دائرة→هيئة (department→organization) | "geometric circle"→"spatial form/shape" | Both senses wrong — geometry, not administration |
| 29 | عشرة→عدد مركب (ten→composite number) | "tithe (1/10)"→"complex number (a+bi)" | Double false friend — 5 hops of correct math hypernyms connecting two wrong senses |
| 66 | ساعة→فترة (hour→time interval) | "memorable moment"→"time period" | Wrong sense of ساعة |

Case #29 is particularly instructive: the path tenth→simple fraction→fraction→rational→real→complex number is a **valid 5-hop chain of correct hypernyms** — but it connects "one-tenth" to "complex number," neither of which is what the Ontology intended (ten and composite number). The BFS algorithm cannot detect this because the path is internally consistent.

#### Weak/Shifted Matches: ~9%
Technically valid paths but through different sense nuances:

| # | Ontology intent | AWN4 actual path | Issue |
|---|---|---|---|
| 1 | مدرسة IS-A صرح (school IS-A educational institution) | school-building→building | Ontology means institutional hierarchy; AWN4 gives physical containment |
| 16 | وكر→ملاذ (criminal hideout→refuge from danger) | "cozy retreat"→"private peaceful place" | Emotional valence inverted |
| 18 | مسار (traffic lane)→طريق (road) | "trail left behind"→"route/path" | Lane ≠ trail |
| 51 | قلعة→حصن (castle→stronghold) | Both are lemmas of the same AWN4 synset | AWN4 treats them as synonyms, not hierarchy |

### DISAGREE Validation (41 of 1,217 reviewed in detail)

The DISAGREE category decomposes into four distinct failure modes:

#### Mode A: Ontology-Native Parents with No AWN4 Equivalent (~41%)
The most common pattern. The Ontology defines abstract Arabic-native parent concepts that have no English WordNet counterpart. The lemma matcher latches onto homographs:

| Parent concept | Ontology meaning | AWN4 matched to |
|---|---|---|
| مُجَمَّع \| مَنْشَط | "site for social activities" | assembler (software), stimulant (drug), energy source |
| شاغِر \| صِفْر \| صَفِر | "empty container/void" | vacant (adj), zero (math), whistle (verb), brass (metal) |
| مَنْتَج | "productive site" | film producer (person), productive (adj) |
| صَرْح | "educational institution" | building (structure), declared/said (verb) |

Every child of مُجَمَّع/مَنْشَط (station, shop, toilet, slaughterhouse...) is classified DISAGREE because of this. These are **PARTIAL cases in disguise** — the parent side has no valid AWN4 match.

#### Mode B: Total False Friends on the Child Side (~15%)

| Case | Ontology child | AWN4 matched to |
|---|---|---|
| 3 | خُصّ (farmer's hut) | خصّ (to concern/belong to) |
| 18 | حَرَم (campus) | حَرَمَ (to deprive) |
| 26 | شام (the Levant) | شامّ (sniffer/smeller person) |
| 30 | كوثل (stern cabin of ship) | كوثل (to Catholicize) |

These are also **PARTIAL in disguise** — the child has no valid AWN4 match.

#### Mode C: Correct Matches Both Sides, No Hypernym Path (~20%)
The most linguistically interesting cases. Both resources have the right concepts but organize them differently.

The **worship cluster** (cases #2, #7, #10, #24) is the clearest example: AWN4 correctly identifies مسجد as "mosque," كنيسة as "church," and معبد as "temple/place of worship." The Ontology says mosque IS-A place-of-worship and church IS-A place-of-worship. But AWN4 inherited Princeton WordNet's structure where these are co-hyponyms organized under different intermediate nodes — not in a direct hypernym chain. The contamination from جامع→"sexual intercourse/collector" and بيعة→"pledge of allegiance/sale" makes it worse, but **even with perfect matching this would likely fail**.

The **animal shelter cluster** (cases #6, #8, #11) has the same pattern: عرين (den), حظيرة (pen), جحر (burrow) all correctly match AWN4 nouns, and مأوى (shelter) also matches correctly — but AWN4's "shelter" synsets are about human shelters (homeless shelters, protective structures), not animal habitations. The Ontology's parent مأوى/مربض specifically means "animal habitation," a distinction AWN4 doesn't make.

#### Mode D: Genuine Structural Disagreements (~12%)
Real differences in how the resources categorize concepts:

| Case | Ontology says | Problem |
|---|---|---|
| 37 | بلدة subTypeOf قرية (town IS-A village) | Inverted: towns are larger than villages |
| 21 | ضيعة subTypeOf قرية (estate IS-A village) | Estates are properties, not settlement types |
| 32, 39 | ثلاثة subTypeOf عدد أولي, أربعة subTypeOf عدد مركب | Instance-of, not subtype-of — "3" is not a type of prime |
| 13 | عاصمة subTypeOf حاضرة (capital IS-A metropolis) | Debatable — many capitals are not metropolises |

#### Self-Match Artifact (~7%)
Case #33: مختبر subTypeOf معمل (lab IS-A plant). Both child and parent match to the **same** AWN4 synset (awn4-03635277-n "laboratory"). BFS requires depth>0, so a synset can't match itself. This is a technical artifact, not a real disagreement.

### Revised Statistics

> **Note:** The table below is based on the pre-fix AWN4 (319 AGREE, 1,217 DISAGREE). After restoring the 78 missing upper-ontology synsets, the raw counts changed to 569 AGREE and 974 DISAGREE (see section 4). The qualitative breakdown below still applies to the original sample but the absolute numbers have shifted.

Based on the manual review, the raw script output significantly misrepresents the true picture. Extrapolating from the 41-case DISAGREE sample:

| Category | Raw Script | Estimated After Correction |
|---|---:|---:|
| AGREE (genuine) | 319 (6.5%) | ~290 (5.9%) |
| AGREE (false positive) | — | ~29 (0.6%) |
| DISAGREE (genuine structural) | — | ~146 (3.0%) |
| DISAGREE (actually PARTIAL) | — | ~681 (13.9%) |
| DISAGREE (self-match/other artifact) | — | ~85 (1.7%) |
| DISAGREE (Ontology error) | — | ~146 (3.0%) |
| PARTIAL (original) | 2,113 (43.3%) | ~2,794 (57.2%) |
| UNMATCHABLE | 1,236 (25.3%) | 1,236 (25.3%) |

The corrected picture: **~6% genuine agreement, ~3% genuine disagreement, ~57% untestable (one or both sides unmatched), ~25% fully unmatchable, ~3% Ontology errors.** Where both resources correctly represent the same concept pair, they agree roughly twice as often as they disagree.

### Conclusions

1. **The AGREE rate improved from 6.5% to 11.6%** after restoring 78 missing upper-ontology synsets. Both rates include ~6% false positives (wrong-sense matches that accidentally found a hypernym path).

2. **The DISAGREE rate dropped from 24.9% to 19.9%.** It remains inflated — over half of DISAGREE cases are actually PARTIAL in disguise — ontology-native abstract concepts (منشط, شاغر, منتج) or rare Arabic words (خص, كوثل, شام) matched to unrelated AWN4 homographs.

3. **Where both resources have correct matches, agreement outweighs disagreement ~2:1.** The hierarchy comparison mostly validates compatibility between the two resources rather than revealing fundamental conflicts.

4. **The Ontology contains some genuine classification errors** (بلدة subTypeOf قرية inverts the size relationship; cardinal numbers classified as subtypes rather than instances of number classes).

5. **AWN4's worship-building hierarchy has a blind spot**: mosque, church, and temple/synagogue don't connect upward to a shared "place of worship" hypernym in a way that matches the Ontology's expectations. This is inherited from Princeton WordNet's structure.

6. **AWN4 conflates human and animal shelters**: مأوى (shelter) in AWN4 is exclusively about human protective structures. The Ontology's distinction between مأوى (human shelter) and مأوى/مربض (animal habitation) has no equivalent in AWN4.

---

## Open Questions
- How many of the 3,349 non-overlapping ontology concepts represent genuinely missing Arabic-specific meanings in AWN4?
- Is the Qabas morphological data useful for enriching AWN4 entries (root, augmentation, transitivity)?
- What is the quality of the Ontology's NULL-relation concepts (the majority)?
- Could English synset matching (using the Ontology's englishSynset field + AWN4's ILI links) improve the hierarchy alignment rate?
