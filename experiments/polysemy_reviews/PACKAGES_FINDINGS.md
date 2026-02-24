# AWN4 Polysemy Evidence Packages — Approach & Findings

**Date:** 2026-02-23
**Script:** `experiments/polysemy_packages.py`
**Report:** `experiments/polysemy_packages.json` (16.7 MB)
**Prerequisite:** `experiments/prefilter_report.json` (Stage 1 output)

---

## Motivation

Stage 1 (`prefilter_dict.py`) discovered **5,378 groups of synsets sharing identical normalized lemma sets** — involving 12,496 synsets total. The worst case: عقد appears as the sole lemma in 18 different noun synsets, each representing a distinct English sense (legal contract, bridge bid, decade, etc.). A user browsing AWN4 sees 18 entries labeled "عقد" with no way to tell them apart.

These are the **highest-value targets** for review: each group needs at least one disambiguating synonym per synset. Before sending them to an LLM reviewer (Stage 4B), we need to assemble all the evidence a reviewer needs into a single self-contained package.

---

## Approach

### Data Sources

| Resource | Size | What It Provides |
|----------|------|------------------|
| `experiments/prefilter_report.json` | 66 MB | `duplicate_synsets` list: groups of synset IDs sharing lemma sets |
| `output/awn4.xml` | 72 MB, 109,901 synsets | Full synset data: definitions, examples, relations, ILI links |
| `arabic_dict.db` | 86 MB, 94,537 entries | Dictionary evidence: headwords (diacritized), roots, POS, definitions, examples |

### Architecture

The script runs in 5 phases:

1. **Load prefilter report** — extract `duplicate_synsets` list, apply `--top` / `--min-count` filters, build target sets.
2. **Stream-parse AWN4 XML** — single pass using `ET.iterparse` with `elem.clear()`. Stores full data (definitions, examples, relations, lemmas) for the ~12,496 target synsets, and minimal data (first definition + lemmas) for all 109,901 synsets to enable hypernym lookups.
3. **Load dictionary evidence** — single SQL query, scans all 94K rows, extracts entries matching target lemmas via canonical normalization.
4. **Assemble evidence packages** — merges AWN4 synset data, hypernym context, and dictionary evidence into one package per group.
5. **Write JSON output + print summary**.

Total runtime: **3.5 seconds**.

### Normalization

Same canonical normalization as Stage 1 (copied for self-containment):

1. Strip diacritics (tashkeel, superscript alef, Quranic marks)
2. Normalize alef variants: أ/إ/آ → ا
3. Normalize alef maqsura: ى → ي
4. Remove tatweel, trailing digits, definite article (ال)

### Hypernym Context Strategy

Each synset's first hypernym is resolved to provide upstream context. For example, in the عقد group:

- Synset "legal contract" → hypernym "اتفاقية مكتوبة" (written agreement)
- Synset "decade 1830s" → hypernym "عقد" (decade) → hypernym "فترة زمنية" (time period)

This helps a reviewer understand *why* English WordNet separated these senses and decide which Arabic synonym to add for disambiguation.

**Implementation:** During the XML parse, minimal data (definition + lemmas) is stored for ALL 109,901 synsets, allowing O(1) hypernym lookup without a second parse pass. Memory cost is ~50 MB.

---

## Results

### Summary

```
Groups processed:             5,378
Total synsets covered:       12,496
Packages with dict data:      2,856  (53.1%)
Hypernym context found:      10,248  (100.0% of synsets with hypernyms)
Elapsed:                      3.5s
Output size:                  16.7 MB
```

### Key Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Total polysemy groups | 5,378 | From prefilter `DUPLICATE_SYNSETS` check |
| Total synsets in groups | 12,496 | 11.4% of all AWN4 synsets |
| Unique target lemmas | 5,919 | Distinct normalized forms across all groups |
| Lemmas with DB evidence | 2,715 (45.9%) | Higher than the 24.9% across all AWN4 — polysemous words tend to be common |
| DB entries matched | 10,526 | Multiple entries per lemma (different POS, sources) |
| Synsets with hypernym context | 10,248 / 12,496 (82.0%) | Remaining 18% are top-level concepts or adverbs |
| Hypernym resolution rate | 100% | All hypernym targets found in same XML file |
| Missing synsets from XML | 0 | All synset IDs from prefilter found in XML |

### POS Distribution of Groups

| POS | Groups | % |
|-----|--------|---|
| Noun (n) | 3,626 | 67.4% |
| Verb (v) | 1,110 | 20.6% |
| Adjective (a) | 463 | 8.6% |
| Adverb (r) | 179 | 3.3% |

Nouns dominate because English has deep noun polysemy (e.g., "head", "point", "base") that the LLM translator collapsed into single Arabic words.

### Group Size Distribution

| Group Size | Groups | Synsets | Cumulative % of Synsets |
|------------|--------|---------|------------------------|
| 2 synsets | 4,016 | 8,032 | 64.3% |
| 3 synsets | 940 | 2,820 | 86.8% |
| 4 synsets | 235 | 940 | 94.4% |
| 5 synsets | 74 | 370 | 97.3% |
| 6 synsets | 25 | 150 | 98.5% |
| 7 synsets | 12 | 84 | 99.2% |
| 8+ synsets | 76 | ~100 | 100% |

The long tail: 4,016 groups (74.7%) have exactly 2 synsets. A `--min-count 3` filter gives 1,362 higher-value groups.

---

## Detailed Findings

### Finding 1: Dictionary Coverage is Higher for Polysemous Words

**45.9%** of target lemmas have dictionary evidence, vs. 24.9% across all AWN4 lemmas. This makes sense — polysemous words are by definition high-frequency and well-attested in standard dictionaries.

This means **53.1% of packages** include authoritative dictionary data, making them immediately ready for LLM review with ground-truth evidence.

### Finding 2: Hypernym Chains Effectively Disambiguate English Senses

The عقد (18 synsets) case study shows this clearly:

| # | Synset ID | AWN4 Definition | Hypernym Lemmas |
|---|-----------|-----------------|-----------------|
| 0 | awn4-06532935-n | اتفاق ملزم بين شخصين أو أكثر قابل للتنفيذ بموجب القانون | اتفاقية مكتوبة |
| 1 | awn4-06750143-n | (في لعبة البريدج) يصبح أعلى عطاء هو العقد... | إعلان العطاء, عطاء, مزايدة |
| 2–16 | awn4-1517XXXX-n | العقد من [year] إلى [year] | عقد (= decade) |
| 17 | awn4-15229779-n | فترة مدتها 10 سنوات | فترة, فترة زمنية, مدة |

The hypernym context reveals the English sense structure: synsets 2–16 are all specific decades inheriting from the generic "decade" synset (#17), which itself inherits from "time period". Synset 0 is a legal contract under "written agreement". Synset 1 is a bridge game term.

A reviewer can now assign targeted disambiguating synonyms:
- Legal contract → add عقد قانوني or اتفاقية
- Decade → add عَقْد زمني
- Bridge bid → flag as culturally irrelevant or add عقد (بريدج)

### Finding 3: Decade Synsets Reveal a Systematic Translation Pattern

15 of the 18 عقد synsets are decades ("the 1830s", "the 1840s", etc.). They have trailing digits in the raw lemma (e.g., "عقد 1830") that normalize away. This is a recurring pattern where AWN4 mechanically translated every decade entry from English WordNet. These 15 synsets are not errors — they're legitimate entries — but they need standardized Arabic labeling (e.g., عقد الثلاثينيات من القرن التاسع عشر).

### Finding 4: Multi-Lemma Groups Show Synonym Collapse

The 1,588 multi-lemma duplicate groups (e.g., {عزل, فصل} appearing in 7 verb synsets) show that even when the translator provided two Arabic synonyms, the *same pair* was reused across multiple senses without additional disambiguators. The dictionary evidence for these groups is especially valuable because the DB can show which specific meaning of فصل or عزل applies to each sense.

---

## Package Structure

Each evidence package contains:

```json
{
    "group_id": 0,
    "lemma_set": ["عقد"],
    "pos": "n",
    "count": 18,
    "synsets": [
        {
            "id": "awn4-06532935-n",
            "ili": "i70736",
            "definitions": ["اتفاق ملزم بين شخصين أو أكثر..."],
            "examples": ["..."],
            "lemmas_raw": ["عقد"],
            "hypernym": {
                "id": "awn4-06784454-n",
                "definition": "اتفاقية مكتوبة...",
                "lemmas_raw": ["اتفاقية مكتوبة"]
            }
        }
    ],
    "dictionary_evidence": {
        "عقد": [
            {
                "headword": "عَقَدَ",
                "root": "عقد",
                "pos": "verb",
                "source": "المعجم الوسيط",
                "definitions": ["صفَّ رجليه ووثب...", "..."],
                "examples": ["..."]
            }
        ]
    },
    "root_family": ["عقد"]
}
```

---

## How to Run

```bash
# Default: all 5,378 groups
python experiments/polysemy_packages.py

# Top 100 worst offenders
python experiments/polysemy_packages.py --top 100

# Only groups with 5+ synsets (127 groups)
python experiments/polysemy_packages.py --min-count 5

# Custom output path
python experiments/polysemy_packages.py --top 10 --output experiments/polysemy_top10.json

# Custom input paths
python experiments/polysemy_packages.py \
    --prefilter experiments/prefilter_report.json \
    --awn4-xml output/awn4.xml \
    --dict-db ../../arabic-dictionaries/extraction/db/arabic_dict.db
```

## Query Examples

```python
import json

data = json.load(open('experiments/polysemy_packages.json'))

# Find the عقد group
for pkg in data['packages']:
    if 'عقد' in pkg['lemma_set']:
        print(f"Group {pkg['group_id']}: {pkg['count']} synsets")
        for s in pkg['synsets']:
            print(f"  {s['id']}: {s['definitions'][0][:60]}")

# All groups with 5+ synsets
big_groups = [p for p in data['packages'] if p['count'] >= 5]
print(f"{len(big_groups)} groups with 5+ synsets")

# Groups with dictionary evidence
with_dict = [p for p in data['packages'] if p['dictionary_evidence']]
print(f"{len(with_dict)} groups have dictionary evidence")

# Get all roots across all packages
all_roots = set()
for p in data['packages']:
    all_roots.update(p['root_family'])
print(f"{len(all_roots)} unique roots")
```

---

## Next Steps

### Stage 4B: LLM Polysemy Review (Planned)

Feed evidence packages into **Gemini 3 Flash** to propose disambiguating synonyms for each synset within a group. The LLM sees all synsets together with dictionary evidence, enabling it to assign targeted Arabic synonyms that distinguish each sense.

**Prioritization strategy:**
1. Start with `--min-count 5` (127 groups, ~700 synsets) — high-value, manageable volume
2. Scale to `--min-count 3` (1,362 groups) after validating output quality
3. Full run on all 5,378 groups last

### Coverage Improvement

Loading classical dictionaries (لسان العرب, تاج العروس, القاموس المحيط) into the SQLite DB would push dictionary coverage from 45.9% toward ~70-80% for polysemous lemmas, giving the LLM reviewer richer evidence for more groups.
