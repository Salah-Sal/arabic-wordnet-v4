# AWN4 vs OEWN 2024: Structural Discrepancy Report

**Date:** 2026-03-04
**Method:** Programmatic analysis via `wn` Python library (v1.0.0)
**Data:** `awn4.xml.gz` (109,901 synsets) vs. `oewn:2024` (120,630 synsets)

---

## Executive Summary

AWN4 is **not** a complete Arabic translation of OEWN 2024. The analysis reveals three categories of structural gaps with evidence for each:

| Finding | Scope | Impact |
|---------|-------|--------|
| Satellite adjectives (pos=`s`) completely absent | 10,720 synsets | 41% of OEWN's adjective space missing |
| 9 critical hub verbs absent | 9 synsets | ~1,191 verb children dangling without Arabic parent |
| 3,123 synsets with no ILI link | 2,933 AWN4-custom + 190 ILI-free from OEWN | Cross-lingual alignment broken for 2.8% of AWN4 |

Total synsets dropped from OEWN: **10,729** (8.9%)
Total relations dropped: **12,825** (4.3% of 297,150)

---

## Finding 1 — Satellite Adjective Collapse (pos=`s`)

### What happened

OEWN represents adjectives in two tiers:

| Tier | POS code | Role | OEWN count |
|------|----------|------|------------|
| Head adjectives | `a` | Anchor the antonym cluster (e.g. *good* ↔ *bad*) | 7,502 |
| Satellite adjectives | `s` | Near-synonyms of the head (e.g. *superb*, *excellent* are satellites of *good*) | 10,720 |

AWN4 has **all 7,502 head adjectives** but **zero satellite adjectives**:

```
OEWN adj coverage:
  pos='a':  7,502 synsets  →  AWN4: 7,502 ✓ (100%)
  pos='s': 10,720 synsets  →  AWN4:     0 ✗ (0%)
```

The ILIs of all 10,627 satellite adjectives with ILI assignments **do not appear anywhere in AWN4** — they were not merged into the `a` tier, they were simply dropped.

### Evidence

```python
oewn_s_ilis = {ss.ili for ss in en.synsets(pos='s') if ss.ili}  # 10,627
awn4_ilis    = {ss.ili for ss in arb.synsets() if ss.ili}
s_ilis_in_awn4 = oewn_s_ilis & awn4_ilis  # → 0
```

### What these synsets contained

Satellite adjectives include highly common and semantically rich words — these are NOT obscure technical terms:

| OEWN satellite | English lemmas | Head (present in AWN4) | Definition |
|----------------|----------------|------------------------|------------|
| oewn-00003552-s | emergent, emerging | nascent | coming into existence |
| oewn-00004170-s | moribund | dying | on the point of death |
| oewn-00004295-s | last | dying | occurring at time of death |
| oewn-00005472-s | direct, exact | absolute | lacking mitigating elements |
| oewn-00005598-s | implicit, unquestioning | absolute | being without doubt |
| oewn-00005717-s | infinite | absolute | total and all-embracing |
| oewn-00005838-s | living (intensifier) | absolute | (informal) absolute |

The heads with the most satellites lost:

| Head adjective | Satellites lost |
|----------------|----------------|
| chromatic | 147 |
| cardinal | 133 |
| ordinal | 92 |
| formed | 72 |
| large, big | 48 |
| achromatic, neutral | 46 |
| colored, coloured | 46 |
| ill, sick | 34 |
| intense | 26 |

### Cascading relation loss

The `similar` relation (which links satellites to their head) dropped by **46.6%** as a direct consequence:

```
OEWN similar relations:  23,188
AWN4 similar relations:  12,371
Dropped:                 10,817 (46.6%)
```

This explains why all 7,502 AWN4 adjective synsets appear as isolated roots with no hierarchy — they ARE the heads, but their satellite clusters were amputated.

### Consequence for review

Every AWN4 adjective synset at review is a **head adjective that should have satellites**. When assigning Arabic lemmas, reviewers are covering only the head concept and missing the range of near-synonyms that should live in AWN4 as separate synsets. For example:

- AWN4 has a synset for "مُطلَق" (absolute, head)
- AWN4 should also have separate synsets for "صريح/مباشر" (direct/exact), "ضمني" (implicit), "لانهائي" (infinite) — but none exist

---

## Finding 2 — Nine Missing Hub Verbs

### What happened

9 verb synsets present in OEWN 2024 were not translated into AWN4. These are not peripheral verbs — they are **structural backbone nodes** that serve as the direct parents of hundreds of translated AWN4 verbs.

### Evidence

```python
oewn_verb_ilis = {ss.ili for ss in en.synsets(pos='v') if ss.ili}
awn4_verb_ilis = {ss.ili for ss in arb.synsets(pos='v') if ss.ili}
missing = oewn_verb_ilis - awn4_verb_ilis  # → 9 ILIs
```

### The 9 missing verbs

| ILI | English lemmas | OEWN hypernym | Direct children in OEWN | Children present in AWN4 |
|-----|---------------|---------------|------------------------|--------------------------|
| i33603 | **act, move** | *(none — ROOT)* | 190 | 186 (98%) |
| i22325 | **change** (intrans) | act, move | 197 | 196 (99%) |
| i22389 | **change, alter, modify** (trans) | induce, stimulate | 427 | 425 (99%) |
| i30898 | **travel, go, move, locomote** | act, move | 135 | 135 (100%) |
| i30960 | **move, displace** (trans) | change, alter | 94 | 94 (100%) |
| i29849 | **make, create** | induce, stimulate | 59 | 58 (98%) |
| i25546 | **induce, stimulate, cause** | act, move | 31 | 29 (94%) |
| i33643 | **interact** | act, move | 22 | 21 (95%) |
| i25403 | **communicate, intercommunicate** | interact | 36 | 36 (100%) |

### The dangling children problem

The 9 missing verbs are **absent from AWN4 entirely** — not present as empty stubs:

```python
for ili in missing_hub_ilis:
    found = [ss for ss in arb.synsets() if ss.ili == ili]
    # → [] for all 9
```

Yet their children ARE in AWN4 (e.g. 186 of 190 children of "act, move" are translated). This means those 186 AWN4 verb synsets have a hypernym relation that points **outside AWN4** — to the OEWN-only "act, move" synset. The wn library resolves this as a cross-lexicon reference. When you call `hypernyms()` on those AWN4 verbs, the returned synset exists only in English — it has no Arabic lemmas.

### Structural consequence: the verb hierarchy has no Arabic root

In OEWN, the action verb tree is:

```
act, move (ROOT, ili=i33603)  ← MISSING from AWN4
├── change (intrans)  ← MISSING
│   └── ... 196 AWN4 verbs with broken parent
├── change, alter, modify (trans)  ← MISSING
│   └── ... 425 AWN4 verbs with broken parent
├── travel, go, move, locomote  ← MISSING
│   └── ... 135 AWN4 verbs with broken parent
├── interact  ← MISSING
│   └── communicate  ← MISSING
│       └── ... 36 AWN4 verbs with broken parent
└── induce, stimulate, cause  ← MISSING
    ├── make, create  ← MISSING
    │   └── ... 58 AWN4 verbs with broken parent
    └── ...
```

All action verbs in AWN4 that OEWN places under "act, move" are now structurally parentless within Arabic semantic space. Their definitions, attestation, and review cannot place them in context against their Arabic generalization.

### Hypernym/hyponym symmetry break

This explains the measured relation asymmetry:
```
AWN4 hypernym relations: 93,435
AWN4 hyponym relations:  92,255
Difference:               1,180  ← these are the "dangling" hypernym edges
                                    pointing to OEWN-only synsets
```

---

## Finding 3 — 3,123 Synsets Without ILI Link

### What they are

| Category | Count | Explanation |
|----------|-------|-------------|
| AWN4-custom (8x/9x ID prefix) | 2,933 | Added by the AWN4 team; no OEWN equivalent |
| ILI-free from OEWN (0x-7x ID, ILI=None in both) | 190 | New OEWN 2024 synsets not yet assigned to ILI |

```
Leading digit of numeric ID part:
  '9x': 2,222   '8x': 711   → 2,933 AWN4-custom
  '0x'-'7x': 190             → matched OEWN IDs, both have ILI=None
```

### The AWN4-custom synsets (2,933)

These appear to have been added during the Gemini translation process or by the AWN4 team to cover Arabic-specific concepts. Sample:

| ID | Arabic lemmas | Definition |
|----|--------------|------------|
| awn4-92467464-n | ذاتي التغذية الكيميائية | كائن حي يعتمد على المواد الكيميائية للحصول على طاقته |
| awn4-92419858-n | طرائد صغيرة | حيوانات صغيرة يتم اصطيادها للرياضة أو الطعام |
| awn4-92440706-n | ماشية صغيرة | حيوانات أليفة صغيرة (دجاج، إوز، أرانب...) |
| awn4-92266961-a | لحوح, ملح | مثابر أو مصر لدرجة الإزعاج |

Since these have no ILI, they **cannot be cross-referenced** via the Global WordNet Association's interlingual index and cannot be automatically aligned with any other language's WordNet.

### The 190 ILI-free OEWN synsets

These are synsets that OEWN 2024 itself doesn't have ILI assignments for yet (likely new additions not yet submitted to the ILI registry). Both OEWN and AWN4 have them without ILI. Not a defect in AWN4 — inherited from OEWN.

---

## Finding 4 — Relation Inventory: Full Comparison

```
Relation Type              OEWN       AWN4   Retained  Dropped
──────────────────────────────────────────────────────────────
similar                  23,188     12,371     53.4%   10,817  ← satellite adj
hyponym                  93,446     92,255     98.7%    1,191  ← dangling children
domain_topic              6,946      6,481     93.3%      465
exemplifies               1,667      1,437     86.2%      230  ← mostly from 's' synsets
domain_region             1,349      1,276     94.6%       73
also                      2,728      2,716     99.6%       12
hypernym                 93,446     93,435    100.0%       11  ← 9 missing hub verbs
is_entailed_by              407        401     98.5%        6
causes                      221        219     99.1%        2
──────────────────────────────────────────────────────────────
TOTAL                   297,150    284,325     95.7%   12,825
```

Of the 12,825 dropped relations:
- **10,817 (84.4%)** are `similar` — direct consequence of satellite adjective removal
- **1,191 (9.3%)** are `hyponym` — children whose parent was a missing hub verb
- **465 (3.6%)** are `domain_topic` — domain classification lost for some synsets
- **230 (1.8%)** are `exemplifies` — 223 of these belonged to satellite adj synsets

---

## Summary of Impact by Category

### Adjective coverage (most severe gap)
- AWN4 covers 41.2% of OEWN's adjective synsets (7,502 / 18,222)
- The missing 58.8% (10,720 satellite adjectives) are NOT obscure — they include common near-synonyms like *emergent*, *moribund*, *implicit*, *infinite*, *direct*, *exact*
- Every adjective in AWN4 is a "head" without its satellite cloud — the granularity of Arabic adjectival expression in the WordNet is severely curtailed

### Verb structure (moderate gap)
- AWN4 covers 99.9% of verb synsets by count
- But the 9 missing verbs are **structurally central** — they are the direct ancestors of ~1,100 AWN4 verb synsets
- The entire "action" subtree of Arabic verbs has no Arabic generalization node — the backbone verb "act, move" has no Arabic translation

### Noun and adverb coverage (negligible gaps)
- Nouns: 100% coverage, single unified tree from كَيْنُونَة (entity)
- Adverbs: 100% coverage, flat structure (3,622 independent roots)

### Cross-lingual alignment
- 2,933 AWN4-custom synsets (2.7% of total) have no ILI and cannot be aligned to other GWA member WordNets
- These represent AWN4-specific conceptual additions that enrich Arabic coverage but fragment multilingual interoperability

---

## Recommendations for the Review Pipeline

### For adjective review (high priority)
1. Flag every AWN4 `a`-adjective synset as needing satellite candidate identification
2. For each head synset, use the OEWN `similar` relation to identify the satellite synsets that SHOULD exist in AWN4 — these are strong candidates for `add_lemma` actions or `flag_lexical_gap`
3. The missing satellites likely have Arabic equivalents — they just weren't translated. A batch translation pass for satellite adjectives should be considered

### For verb review (moderate priority)
1. When reviewing any verb synset, use `ss.translate(lang='en')` to find the OEWN equivalent and check where it sits in OEWN's hierarchy
2. The 9 missing hub verbs represent conceptual gaps that should be translated and added:
   - "act, move" → likely Arabic: "فَعَلَ / تَصَرَّفَ"
   - "change" (intrans) → "تَغَيَّرَ"
   - "change, alter, modify" → "غَيَّرَ / بَدَّلَ"
   - "travel, go, move, locomote" → "سَافَرَ / تَنَقَّلَ"
   - "communicate" → "تَوَاصَلَ"
   - "make, create" → "صَنَعَ / خَلَقَ"

### For cross-lingual alignment
1. The 2,933 AWN4-custom synsets should be submitted for ILI registration via the Global WordNet Association
2. Until then, treat them as AWN4-local and flag them in the review YAML with `cili_alignment: "custom-no-ili"`

---

## Appendix: Verification Commands

```python
import wn
arb = wn.Wordnet('awn4')
en  = wn.Wordnet('oewn')

# Confirm satellite adjective gap
print(len(en.synsets(pos='s')))   # 10,720
print(len(arb.synsets(pos='s')))  # 0

# Confirm 9 missing hub verbs
oewn_v_ilis = {ss.ili for ss in en.synsets(pos='v') if ss.ili}
awn4_v_ilis = {ss.ili for ss in arb.synsets(pos='v') if ss.ili}
print(oewn_v_ilis - awn4_v_ilis)  # 9 ILIs

# Confirm ILI-free synsets
print(sum(1 for ss in arb.synsets() if not ss.ili))  # 3,123

# Confirm relation asymmetry
from collections import Counter
awn4_rels = Counter()
for ss in arb.synsets():
    for rel_type, targets in ss.relations().items():
        awn4_rels[rel_type] += len(targets)
print(awn4_rels['hypernym'], awn4_rels['hyponym'])  # 93435, 92255
```
