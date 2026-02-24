# Formal Hierarchy Mapping: AWN4 (OEWN 2024) vs Arabic Ontology

## 1. Overview

This document provides a level-by-level structural mapping between the noun
hierarchies of **AWN4** (derived from OEWN 2024, English Princeton WordNet
lineage) and the **Arabic Ontology** (BFO-inspired, Arabic-native).

| Property | AWN4 | Arabic Ontology |
|----------|------|-----------------|
| Source | OEWN 2024 (English) | Arabic-native (BFO-inspired) |
| Total concepts | 84,956 noun synsets | 4,885 concepts |
| Root | entity (كَيْنُونَة) | كَيْنُونَة / شَيْء (entity) |
| L1 branches | 3 | 5 |
| Max depth | ~18 levels | ~12 levels |
| Design philosophy | Lexical (word senses) | Ontological (conceptual types) |

### Methodology

Mapping was established by:
1. **Lemma matching** — normalized Arabic lemmas (strip diacritics, normalize alef/taa-marbuta) between AWN4 entries and Arabic Ontology concept names
2. **Structural alignment** — matching English gloss labels where Arabic lemma matching was ambiguous
3. **Hypernym-path verification** — BFS up to 8 hops through AWN4's hypernym graph to verify parent-child agreement

---

## 2. Level 0 — Root

| AWN4 | Arabic Ontology | Alignment |
|------|-----------------|-----------|
| **entity** (كَيْنُونَة, كِيَان) | **كَيْنُونَة / شَيْء / كَائِن** (entity) | EXACT |
| 3 children, 88,200 descendants | 5 children, 4,885 descendants | — |

Both resources share the same root concept. The Arabic Ontology uses the
classical شَيْء as primary label; AWN4 uses كَيْنُونَة.

---

## 3. Level 1 — Primary Branches

### 3.1 AWN4 L1 Nodes (3)

| # | Node | Arabic | Children | Descendants |
|---|------|--------|----------|-------------|
| 1 | physical entity | كِيَان مَادِّيّ | 6 | 50,323 |
| 2 | abstraction, abstract entity | تَجْرِيد, كِيَان مُجَرَّد | 9 | 37,834 |
| 3 | thing | شَيْء | 12 | 12 |

### 3.2 Arabic Ontology L1 Nodes (5)

| # | Node | English gloss | Children | Descendants |
|---|------|---------------|----------|-------------|
| 1 | قَائِم / مَوْجُود / شَيْء | object / independent continuant | 7 | 691 |
| 2 | مُتَعَلِّق / مَنُوط | dependent entity | 13 | 1,282 |
| 3 | سَيْرورَة / حُدُوث | occurrent | 8 | 1,779 |
| 4 | تَعْبِير | information | 109 | 376 |
| 5 | مُجَرَّد / نَظَرِيّ | abstract | 14 | 752 |

### 3.3 L1 Cross-Mapping

```
AWN4                          Arabic Ontology
─────────────────────         ─────────────────────────────
                         ┌──► قَائِم (independent continuant)
physical entity ─────────┤
                         └──► سَيْرورَة (occurrent) [partial]

                         ┌──► مُتَعَلِّق (dependent entity)
                         ├──► مُجَرَّد (abstract)
abstraction ─────────────┤
                         ├──► تَعْبِير (information)
                         └──► سَيْرورَة (occurrent) [partial]

thing ───────────────────     (no match — 12 informal English words)
```

**Key divergence:** AWN4's binary physical/abstract split does not map cleanly
to the Arabic Ontology's 5-way BFO partition. In particular:

- AWN4 places **processes** under `physical entity` and **events** under
  `abstraction`. The Arabic Ontology groups ALL temporal phenomena under
  `سيرورة` (occurrent).
- AWN4 places **qualities, relations, communication** under `abstraction`.
  The Arabic Ontology splits these across `dependent entity`, `information`,
  and `abstract`.

---

## 4. Level 2 — Detailed Branch Mapping

### 4.1 AWN4 `physical entity` → Arabic Ontology

| AWN4 L2 | Desc. | Arabic Ontology Match | AO Location | Confidence |
|----------|-------|-----------------------|-------------|------------|
| **object, physical object** | 28,744 | مُجَسَّد / مَحْسُوس (physical object) | L1.قائم → L2 | HIGH |
| **causal agent, cause** | 22,840 | Split: مُتَعَضٍّ (organism) + شخص اعتباري (social agent) | L2.مجسد → L3; L2.اعتباري → L3 | MEDIUM |
| **matter** | 7,213 | مَادَّة (material) | L2.مجسد → L3 | HIGH |
| **thing** (under phys.) | 2,836 | — | No match | — |
| **process, physical process** | 1,717 | عَمَلِيَّة (process) | L1.سيرورة → L2 | HIGH (different branch) |
| **substance** | 0 | (merged under مادة) | — | LOW |

**Notes:**
- AWN4's `causal agent` (22,840 descendants) is the most problematic. It
  merges biological organisms and social agents into one branch. The Arabic
  Ontology separates organism (L3 under physical object) from social agent
  (L3 under social object).
- AWN4's `process, physical process` maps to the Arabic Ontology's
  `عملية` (process), but they sit in different L1 branches (physical entity
  vs occurrent).

### 4.2 AWN4 `abstraction` → Arabic Ontology

| AWN4 L2 | Desc. | Arabic Ontology Match | AO Location | Confidence |
|----------|-------|-----------------------|-------------|------------|
| **group, grouping** | 8,547 | مَجْمُوعَة / تَشْكِيلَة (collection) | L1.قائم → L2.اعتباري → L3 | MEDIUM |
| **event** | 8,398 | فَعَّالِيَّة / حَدَث (event) | L1.سيرورة → L2 | HIGH (different branch) |
| **attribute** | 7,882 | سِمَة / صِفَة (quality) | L1.متعلق → L2 | HIGH (different branch) |
| **relation** | 5,642 | عَلَاقَة (relation) | L1.متعلق → L2 | HIGH (different branch) |
| **communication** | 4,912 | تَعْبِير مُجَسَّد (info realization) | L1.تعبير → L2 | MEDIUM (different branch) |
| **psychological feature** | 4,818 | Split: صفة (quality) + حالة (state) + قابلية (disposition) | L1.متعلق → L2 | LOW (fragmented) |
| **measure, quantity, amount** | 2,472 | كَمِّيَّة (quantity) | L1.مجرد → L2 | HIGH |
| **set** | 29 | (under مجموعة) | — | LOW |
| **otherworld** | 0 | — | No match | — |

**Notes:**
- 5 of 9 AWN4 `abstraction` children have HIGH-confidence matches in the
  Arabic Ontology, but all sit in **different L1 branches**. This is the
  core structural mismatch.
- AWN4's `psychological feature` has no single counterpart — it fragments
  across the Arabic Ontology's `quality`, `state`, `disposition`, and
  `capability` under `dependent entity`.

### 4.3 Arabic Ontology `قائم` (independent continuant) → AWN4

| AO L2 | Desc. | AWN4 Match | AWN4 Location | Confidence |
|--------|-------|-----------:|---------------|------------|
| **مُجَسَّد** (physical object) | 381 | object, physical object | L1.physical entity → L2 | HIGH |
| **موجود اعتباري** (social object) | 303 | Split: group + causal agent (partial) | L1.abstraction → L2; L1.physical entity → L2 | MEDIUM |
| **حَيِّز** (spatial region) | 0 | — | — | — |
| *4 leaf nodes* | 0 | — | No match (Arabic philosophical) | — |

### 4.4 Arabic Ontology `متعلق` (dependent entity) → AWN4

| AO L2 | Desc. | AWN4 Match | AWN4 Location | Confidence |
|--------|-------|-----------:|---------------|------------|
| **سِمَة / صِفَة** (quality) | 141 | attribute | L1.abstraction → L2 | HIGH |
| **دَوْر** (role) | 924 | — (no single node) | Scattered in causal agent | LOW |
| **عَلَاقَة** (relation) | 77 | relation | L1.abstraction → L2 | HIGH |
| **حَالَة** (state) | 70 | psychological feature (partial) | L1.abstraction → L2 | MEDIUM |
| **قَابِلِيَّة** (disposition) | 43 | psychological feature (partial) | L1.abstraction → L2 | LOW |
| **قُدْرَة** (capability) | 14 | — | — | — |
| *7 leaf nodes* | 0 | — | No match (Arabic philosophical) | — |

### 4.5 Arabic Ontology `سيرورة` (occurrent) → AWN4

| AO L2 | Desc. | AWN4 Match | AWN4 Location | Confidence |
|--------|-------|-----------:|---------------|------------|
| **عَمَلِيَّة** (process) | 1,176 | process, physical process | L1.physical entity → L2 | HIGH |
| **فَعَّالِيَّة / حَدَث** (event) | 151 | event | L1.abstraction → L2 | HIGH |
| **فِعْل** (action) | 272 | (within event subtree) | L1.abstraction → L2.event → deeper | MEDIUM |
| **زَمَن** (time) | 172 | measure, quantity, amount (partial) | L1.abstraction → L2 | MEDIUM |
| *4 leaf nodes* | 0 | — | No match | — |

**Key insight:** The Arabic Ontology's `occurrent` branch maps to **two
different AWN4 L1 branches** — processes go to `physical entity`, while
events go to `abstraction`. This is the single biggest source of DISAGREE
results in automated comparison.

### 4.6 Arabic Ontology `تعبير` (information) → AWN4

| AO L2 | Desc. | AWN4 Match | AWN4 Location | Confidence |
|--------|-------|-----------:|---------------|------------|
| **تَعْبِير مُجَسَّد** (info realization) | 267 | communication | L1.abstraction → L2 | MEDIUM |
| **مَعْلُومَات** (info object) | 0 | — | — | — |
| *107 linguistic leaf nodes* | 0 | — | Grammar-specific, no match | — |

### 4.7 Arabic Ontology `مجرد` (abstract) → AWN4

| AO L2 | Desc. | AWN4 Match | AWN4 Location | Confidence |
|--------|-------|-----------:|---------------|------------|
| **صِفَة** (attribute) | 325 | attribute | L1.abstraction → L2 | HIGH |
| **كَمِّيَّة** (quantity) | 4 | measure, quantity, amount | L1.abstraction → L2 | HIGH |
| **حَدّ رِياضِيّ** (formal entity) | 25 | — | — | LOW |
| **وَصْف** (description) | 320 | — | — | LOW |
| **مَقُولَة** (proposition) | 64 | — | — | LOW |
| *9 leaf nodes* | 0 | — | Arabic philosophical | — |

---

## 5. Level 3 — Key Subtree Mappings

Where L2 nodes align, the L3 structure often **agrees locally** even when
L1/L2 placement differs.

### 5.1 Physical Objects

```
AWN4: object → whole → living thing → organism → animal
AO:   مجسد → متعضٍّ (organism) → حقيقي النواة → حيوان (animal)
```
**Alignment:** AGREE on organism→animal path. The Arabic Ontology adds a
biological classification layer (prokaryote/eukaryote) between organism and
animal that AWN4 does not have.

### 5.2 Artifacts

```
AWN4: object → whole → artifact → [45 children: structure, instrumentality, ...]
AO:   مجسد → مصنوع (artifact) → [8 children: gas/liquid/solid artifact, ...]
```
**Alignment:** AGREE on physical object → artifact. The Arabic Ontology
classifies artifacts by **physical state** (gas, liquid, solid); AWN4
classifies by **function** (structure, instrumentality, covering, etc.).

### 5.3 Locations

```
AWN4: object → location → region → [2,465 descendants]
AO:   مجسد → منطقة جغرافية (geographical region) → يابسة / مائية
      اعتباري → مَوْضِع (place) → مَحَلّ (site) → [165 descendants]
```
**Alignment:** PARTIAL. AWN4 keeps all locations under `physical object`.
The Arabic Ontology splits physical geography (under `مجسد`) from
socially-defined places (under `موجود اعتباري`).

### 5.4 Persons / Agents

```
AWN4: physical entity → causal agent → [person, organism, ...]
AO:   اعتباري → شخص اعتباري (social agent) → إنسان (natural person) [12 desc]
      مجسد → متعضٍّ (organism) → ... → إنسان [biological sense]
```
**Alignment:** DISAGREE. AWN4 merges all agents (people, organizations,
natural forces) under one `causal agent` node. The Arabic Ontology
distinguishes the biological person (under physical object) from the social
person (under social object).

### 5.5 Time

```
AWN4: abstraction → measure, quantity, amount → time period, ...
AO:   سيرورة (occurrent) → زمن (time) → فترة / مدة / نقطة زمنية
```
**Alignment:** DISAGREE on placement. AWN4 treats time as a kind of
measure/quantity (abstract). The Arabic Ontology treats time as a kind of
occurrent (temporal entity).

### 5.6 Qualities / Attributes

```
AWN4: abstraction → attribute → [shape, size, color, ...]
AO:   متعلق → سمة (quality) → خاصية مادية / خاصية مجردة
      مجرد → صفة (attribute) → صفة مادية / صفة مجردة
```
**Alignment:** PARTIAL. The Arabic Ontology makes a **physical vs abstract
quality** distinction at L3 that AWN4 does not. Additionally, the Arabic
Ontology places qualities in two locations: as `dependent entity` properties
(inherent in objects) and as `abstract` attributes (conceptual).

---

## 6. Automated Comparison Results

Based on BFS hypernym-path verification of 4,885 Arabic Ontology
`subTypeOf` relations against AWN4:

### 6.1 Classification Breakdown

| Category | Count | % | Description |
|----------|-------|---|-------------|
| **AGREE** | 569 | 11.6% | Both concepts matched; hypernym path found in AWN4 |
| **DISAGREE** | 974 | 19.9% | Both matched; no hypernym path (structural mismatch) |
| **PARTIAL** | 2,115 | 43.3% | Only one side matched AWN4 |
| **UNMATCHABLE** | 1,227 | 25.1% | Neither side matched AWN4 |

### 6.2 After Manual Validation

| Category | Estimated true % | Notes |
|----------|------------------|-------|
| Genuine AGREE | ~6% | ~half of AGREE are false positives from polysemy |
| Genuine DISAGREE | ~3% | Real structural differences |
| False friends | ~8% | Homograph matches to wrong sense |
| Ontology errors | ~3% | Inverted hierarchies, instance-vs-type confusion |
| Coverage gap | ~80% | One or both sides have no matching concept |

### 6.3 AGREE Path-Length Distribution

| Hops | Count | % |
|------|-------|---|
| 1 | 257 | 45.2% |
| 2 | 125 | 22.0% |
| 3 | 63 | 11.1% |
| 4 | 63 | 11.1% |
| 5+ | 61 | 10.7% |
| **Average** | **2.26** | — |

Short paths (1-2 hops) dominate, indicating that where both resources cover
the same domain, their local structure is similar.

---

## 7. Structural Divergence Summary

### 7.1 Fundamental Architecture

| Dimension | AWN4 (OEWN) | Arabic Ontology |
|-----------|-------------|-----------------|
| Top split | Physical vs Abstract (2+1) | BFO 5-way (continuant / dependent / occurrent / information / abstract) |
| Processes/events | Split across physical entity + abstraction | Unified under سيرورة (occurrent) |
| Qualities | Under abstraction | Under متعلق (dependent entity) |
| Information | Under abstraction → communication | Own L1 branch (تعبير) |
| Agents | Unified under causal agent | Split: biological organism vs social agent |
| Time | Under abstraction → measure | Under سيرورة (occurrent) |
| Classification by | Lexical function/usage | Ontological type (BFO categories) |

### 7.2 Ranked Divergences (by impact on mapping)

1. **Process/event placement** — Affects ~10,000 AWN4 synsets. AWN4 splits
   temporal concepts across two L1 branches; AO unifies them.

2. **Causal agent fragmentation** — Affects ~22,800 AWN4 synsets. AWN4's
   monolithic `causal agent` has no counterpart; AO splits biological vs
   social agents.

3. **Quality/attribute branch** — Affects ~7,800 AWN4 synsets. Same
   concepts, different L1 placement (abstraction vs dependent entity).

4. **Communication/information** — Affects ~4,900 AWN4 synsets. AWN4 treats
   as subtype of abstraction; AO gives it own L1 branch.

5. **Location split** — Affects ~3,600 AWN4 synsets. AO distinguishes
   physical geography from social places; AWN4 unifies under physical object.

### 7.3 Areas of Strong Agreement

Despite top-level differences, these subtrees show strong local alignment:

| Domain | AWN4 path | AO path | Notes |
|--------|-----------|---------|-------|
| Organisms | phys. entity → … → organism | مجسد → متعضٍّ | Animal/plant subtrees align well |
| Artifacts (general) | phys. entity → … → artifact | مجسد → مصنوع | Both recognize artifact as subtype of physical object |
| Geographical regions | object → location → region | مجسد → منطقة جغرافية | Land/water split present in both |
| Astronomical bodies | object → … → celestial body | مجسد → جرم سماوي | Star, planet, comet align |
| Diseases | abstraction → … → disease | متعلق → قابلية → داء | Both classify as disposition/attribute |
| Occupations | — | متعلق → دور → مهنة | Arabic Ontology has 918 descendants; AWN4 has `occupation` deeper in hierarchy |

---

## 8. Mapping Recommendations

### 8.1 For Integration

If building a unified resource:

1. **Adopt the Arabic Ontology's L1 split as the upper frame**, since BFO
   categories are more principled and widely adopted in formal ontologies.
2. **Use AWN4 for lexical coverage** below L3, where its 84,956 noun
   synsets provide vastly more granularity than the AO's 4,885 concepts.
3. **Create bridge nodes** at L2-L3 to reconcile:
   - AWN4 `causal agent` → split into biological and social subtrees
   - AWN4 `process` + `event` → merge under single occurrent branch
   - AWN4 `attribute` → reclassify under dependent entity
   - AWN4 `communication` → reclassify under information

### 8.2 For Automated Mapping

1. **Restrict lemma matching to L3+ nodes** — L1 and L2 require manual
   alignment (done in this document).
2. **Use domain filters** — Biological, geographical, and artifact domains
   have high agreement rates; prioritize these for automated extension.
3. **Flag homographs** — ~8% of matches are false friends. Any automated
   pipeline must include a polysemy filter (e.g., POS + definition
   similarity).

### 8.3 Coverage Assessment

| Metric | Value |
|--------|-------|
| AO concepts matchable to AWN4 | ~1,543 / 4,885 (31.6%) |
| AWN4 synsets matchable to AO | ~1,543 / 84,956 (1.8%) |
| AWN4 concepts with no AO equivalent | ~83,400 (98.2%) |
| AO concepts with no AWN4 equivalent | ~3,342 (68.4%) |

The Arabic Ontology's strength is its **upper-level Arabic-native
conceptual structure** and its coverage of Islamic/philosophical terms.
AWN4's strength is its **broad lexical coverage** inherited from OEWN. The
two resources are complementary, not competing.

---

*Generated: 2026-02-09*
*Data sources: AWN4 v4.0 (output/awn4.xml), Arabic Ontology (Concepts.csv + Relations.csv)*
