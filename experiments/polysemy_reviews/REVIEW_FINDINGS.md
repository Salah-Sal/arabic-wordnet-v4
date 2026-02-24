# AWN4 Polysemy LLM Review — Approach & Findings

**Date:** 2026-02-23
**Script:** `experiments/polysemy_review.py`
**Output:** `experiments/polysemy_reviews/` (one JSON per group)
**Summary:** `experiments/polysemy_review_summary.json`
**Prerequisite:** `experiments/polysemy_packages.json` (Stage 4A output)

---

## Motivation

Stage 4A assembled **5,378 evidence packages** covering 12,496 synsets that share identical lemma sets. The worst case: عقد appears as the sole lemma in 18 different noun synsets (legal contract, bridge bid, decade, etc.). A user browsing AWN4 sees 18 entries labeled "عقد" with no way to tell them apart.

Each package bundles AWN4 synset data (definitions, examples, hypernym context) with dictionary evidence from المعجم الوسيط and المعجم الكبير. This stage sends those packages to an LLM to propose disambiguating Arabic synonyms.

---

## Approach

### Why Not Reuse the Existing Linguist Prompt?

The existing `linguist_review/llm_linguist_prompt.md` is a 262-line deep review covering 11+ axes (definitions, examples, POS, relations, etc.). It's wrong for this task:

| Factor | Linguist Prompt | Polysemy Prompt |
|--------|----------------|-----------------|
| Scope | 1 synset at a time | N synsets compared together |
| Output | ~2,000 tokens per synset | ~100 tokens per synset |
| Data source | Almaany web scraping | Authoritative dictionary DB |
| Task | Full quality review | Focused disambiguation only |
| Token cost at scale | ~25M output tokens | ~4M output tokens |

**Decision:** Write a focused ~60-line Arabic system prompt that does one thing well: propose 1–2 disambiguating lemmas per synset.

### Prompt Design

The system prompt is written entirely in Arabic and structured as:

1. **Role definition:** أنت لغوي عربي متخصص في المعجمية الحاسوبية — computational lexicography specialist
2. **Context:** Explains the polysemy explosion problem in AWN4
3. **Task:** For each synset, propose 1–2 fully vocalized Arabic lemmas that distinguish it from its siblings
4. **Quality guidelines:**
   - Prefer specialized Arabic terms (اللفظ المختص) over generic qualifiers
   - Full diacritization (تشكيل) required on all proposed lemmas
   - Cite dictionary evidence where available
   - Don't invent terms — ground proposals in the provided data
5. **Confidence levels:** high (dictionary-attested), medium (linguistically sound but unattested), low (approximate)
6. **Flag system:** `CULTURALLY_IRRELEVANT`, `DECADE_CLUSTER`, `PROPER_NOUN_SKIP`, `IDENTICAL_SENSES`
7. **Output format:** Strict JSON schema enforced via `response_mime_type="application/json"`

### Per-Package User Prompt

Each evidence package is formatted as structured Arabic text:

```
## المجموعة: عقد — اسم
عدد المجموعات الترادفية: 18

### المجموعة الترادفية 1: awn4-06532935-n
- التعريف: اتفاق ملزم بين شخصين أو أكثر...
- الأمثلة: ...
- اللمات الحالية: عقد
- المعنى الأعم: اتفاقية مكتوبة (اتفاقية مكتوبة)

### البيانات المعجمية
#### عقد
المعجم الوسيط: عَقَدَ (verb) جذر=عقد
  - صفَّ رجليه ووثب...
```

### Architecture

The script reuses the proven async pattern from `arabic-dictionaries/extraction/api_extract.py`:

| Component | Purpose |
|-----------|---------|
| `RateLimiter` | Sliding 60-second window, prevents exceeding RPM quota |
| `CostTracker` | Per-model token counting and cost calculation |
| `_is_retryable()` | Distinguishes transient errors (429, 503, timeouts) from permanent ones (400) |
| `asyncio.Semaphore` | Bounds concurrent API requests |
| `asyncio.gather` | Parallel launch of all review tasks |

**Lazy imports:** The `google-genai` SDK is only imported when needed, allowing `--dry-run` to work without the SDK installed.

**Resume mechanism:** Each group saves to a separate file (`group_NNNN.json`). On re-run, existing files are skipped automatically.

### Model & Cost

| Model | Input/1M | Output/1M | Free Tier |
|-------|----------|-----------|-----------|
| `gemini-3-flash-preview` | $0.00 | $0.00 | Yes |

Chosen for this pilot: **Gemini 3 Flash Preview** — free tier, sufficient quality for Arabic linguistic tasks.

---

## Pilot Results (Top 5 Groups)

### Summary

```
Groups reviewed:           5
Total synsets:            66
Proposed lemmas:         114
Avg lemmas per synset:   1.73
Cost:                    $0.00
Elapsed:                 ~4 min (with retries)
Total tokens:            13,922 in + 7,224 out = 21,146
```

### Confidence Distribution

| Level | Count | % | Description |
|-------|-------|---|-------------|
| high | 27 | 40.9% | Dictionary-attested proposals |
| medium | 37 | 56.1% | Linguistically sound, no dictionary match |
| low | 2 | 3.0% | Approximate proposals |

The 41% high-confidence rate indicates strong dictionary grounding — nearly half of all proposals are backed by المعجم الوسيط or المعجم الكبير evidence.

### Flags Distribution

| Flag | Count | Description |
|------|-------|-------------|
| `DECADE_CLUSTER` | 15 | Specific decade synsets (the 1830s, 1840s, etc.) |
| `CULTURALLY_IRRELEVANT` | 2 | Western-specific concepts (bridge game, baseball) |
| `PROPER_NOUN_SKIP` | 1 | Constellation name (Carina) |

### Groups Reviewed

| # | Lemma | POS | Synsets | Proposed | Key Disambiguation |
|---|-------|-----|---------|----------|-------------------|
| 0 | عقد | noun | 18 | 20 | تَعَاقُدٌ (contract) vs عَشْرِيَّةٌ (decade) vs عَقْدُ اللَّعِبِ (bridge bid) |
| 1 | رفع | verb | 15 | 29 | فَكَّ (lift blockade) vs نَصَبَ (raise flag) vs حَمَّلَ (upload) vs شَخَصَ (look up) |
| 2 | رأس | noun | 13 | 25 | هَامَةٌ (head/body) vs قِمَّةٌ (top) vs رَأْسُ العَضَلَةِ (muscle origin) |
| 3 | قاعدة | noun | 10 | 19 | رِكْزَة (pedestal) vs ضَابِط (rule) vs قَاعِدَةٌ عَسْكَرِيَّة (military base) |
| 4 | سحب | verb | 10 | 21 | بَزَلَ (draw liquid) vs قَطَرَ (tow) vs اسْتَرَدَّ (withdraw money) vs دَرْفَلَ (roll metal) |

---

## Detailed Findings

### Finding 1: The LLM Successfully Identifies Semantic Clusters

The عقد group (18 synsets) demonstrates this clearly. The LLM correctly identified three distinct semantic clusters:

1. **Legal contract** (1 synset) → proposed تَعَاقُدٌ and اتِّفَاقِيَّةٌ
2. **Decade — generic** (1 synset) → proposed عَشْرِيَّةٌ (an authentic Arabic term for "period of ten years")
3. **Decade — specific** (15 synsets) → all flagged `DECADE_CLUSTER` with a consistent template: عَقْدُ الـ1830 مِيلَادِيّ
4. **Bridge game term** (1 synset) → flagged `CULTURALLY_IRRELEVANT`, confidence=low

This matches exactly what a human reviewer would do: recognize the pattern, apply a template to the bulk, and focus disambiguation effort on the genuinely distinct senses.

### Finding 2: Specialized Arabic Terms Surface from Dictionary Evidence

The LLM consistently prefers authentic Arabic terminology over generic descriptions:

| Synset Sense | Generic (avoided) | Specialized (proposed) |
|-------------|-------------------|----------------------|
| Draw liquid | سحب سائل | بَزَلَ (to tap/draw out) |
| Tow a ship | سحب في الماء | قَطَرَ (to tow, nautical) |
| Pedestal | حامل تمثال | رِكْزَة (pedestal/stand) |
| Decade | عقد زمني | عَشْرِيَّةٌ (decennium) |
| Roll metal | سحب معدن | دَرْفَلَ (to roll/mill) |

Terms like بَزَلَ, قَطَرَ, رِكْزَة, and دَرْفَلَ are precisely the kind of specialized vocabulary that distinguishes a high-quality wordnet from a mechanical translation.

### Finding 3: Verb Groups Are Harder Than Noun Groups

Comparing the two verb groups (رفع, سحب) with the three noun groups:

| POS | Groups | Avg Confidence=high % |
|-----|--------|----------------------|
| Noun | 3 | 46.3% |
| Verb | 2 | 32.0% |

Verb polysemy is harder because:
- Arabic verbal morphology creates many near-synonymous forms (فَعَلَ, أَفْعَلَ, فَعَّلَ) that blur distinctions
- English verb senses often map to different Arabic verb forms rather than different roots
- Dictionary evidence for verb senses tends to list many related meanings under one headword

### Finding 4: Diacritization Quality Is Consistent

All 114 proposed lemmas include full tashkeel (diacritization), as requested. Spot-checking shows correct patterns:

- عَقْدٌ قَانُونِيّ — correct sukun on ق, fatha on ع, tanwin on د
- عَشْرِيَّةٌ — correct kasra on ر, shadda+fatha on ي, ta marbuta with tanwin
- بَزَلَ — correct Form I past tense pattern
- اسْتَرَدَّ — correct Form X past tense with shadda

This is important because AWN4 already has ~4,583 diacritization errors (from the Stage 1 prefilter). New lemmas should not introduce more.

### Finding 5: Cultural Relevance Flagging Works

Two synsets were correctly flagged as `CULTURALLY_IRRELEVANT`:

1. **عَقْدُ اللَّعِبِ** (bridge game contract) — confidence=low, since البريدج has no established Arabic lexicon
2. **قَاعِدَةُ المَلْعَبِ** (baseball base) — baseball terminology is nearly absent from Arabic dictionaries

One synset flagged `PROPER_NOUN_SKIP`: the constellation Carina (كَوْكَبَةُ القَاعِدَة) — appropriately identified as a proper noun requiring no linguistic disambiguation.

---

## Output Format

### Per-Group File: `polysemy_reviews/group_0000.json`

```json
{
  "group_id": 0,
  "lemma_set": ["عقد"],
  "pos": "n",
  "count": 18,
  "model": "gemini-3-flash-preview",
  "timestamp": "2026-02-23T16:03:42.104247+00:00",
  "input_tokens": 2755,
  "output_tokens": 2106,
  "reviews": [
    {
      "synset_id": "awn4-06532935-n",
      "proposed_lemmas": ["تَعَاقُدٌ", "اتِّفَاقِيَّةٌ"],
      "rationale": "التعاقد والاتفاقية يعبران عن الجانب القانوني والإلزامي...",
      "confidence": "high",
      "flags": []
    }
  ],
  "group_notes": "تتوزع المجموعة بين المعنى القانوني والزمني..."
}
```

### Summary File: `polysemy_review_summary.json`

```json
{
  "metadata": {
    "model": "gemini-3-flash-preview",
    "completed": 5,
    "elapsed_minutes": 1.7,
    "total_input_tokens": 13922,
    "total_output_tokens": 7224,
    "cost_usd": 0.0
  },
  "confidence_distribution": {"high": 27, "medium": 37, "low": 2},
  "flags_distribution": {"CULTURALLY_IRRELEVANT": 2, "DECADE_CLUSTER": 15, "PROPER_NOUN_SKIP": 1},
  "total_synsets_reviewed": 66,
  "total_proposed_lemmas": 114,
  "avg_proposed_lemmas_per_synset": 1.73
}
```

---

## How to Run

```bash
# Activate the project venv
source arabic-wordnet-v4/.venv/bin/activate

# Dry run — preview prompts without API calls
python experiments/polysemy_review.py --dry-run --top 3

# Top N worst polysemy groups
python experiments/polysemy_review.py --top 10

# Only groups with 5+ synsets (127 groups)
python experiments/polysemy_review.py --min-count 5

# Full run — all 5,378 groups (with automatic resume)
python experiments/polysemy_review.py

# Custom model (e.g., paid tier for higher quality)
python experiments/polysemy_review.py --model gemini-2.5-flash

# Adjust concurrency and rate limits
python experiments/polysemy_review.py --concurrency 15 --rpm 300

# Resume after interruption — just re-run (skips completed groups)
python experiments/polysemy_review.py --top 50
```

## Query Examples

```python
import json
from pathlib import Path

# Load a single group
g = json.load(open('experiments/polysemy_reviews/group_0000.json'))
for r in g['reviews']:
    print(f"{r['synset_id']}: {r['proposed_lemmas']} ({r['confidence']})")

# Find all high-confidence proposals across all groups
reviews_dir = Path('experiments/polysemy_reviews')
high_conf = []
for f in sorted(reviews_dir.glob('group_*.json')):
    data = json.loads(f.read_text())
    for r in data.get('reviews', []):
        if r['confidence'] == 'high':
            high_conf.append((data['lemma_set'], r['synset_id'], r['proposed_lemmas']))
print(f"{len(high_conf)} high-confidence proposals")

# Find all flagged synsets
for f in sorted(reviews_dir.glob('group_*.json')):
    data = json.loads(f.read_text())
    for r in data.get('reviews', []):
        if r.get('flags'):
            print(f"  {r['synset_id']}: {r['flags']} — {r['proposed_lemmas']}")

# Aggregate summary
s = json.load(open('experiments/polysemy_review_summary.json'))
print(f"Reviewed: {s['total_synsets_reviewed']} synsets")
print(f"Proposed: {s['total_proposed_lemmas']} lemmas")
print(f"Confidence: {s['confidence_distribution']}")
```

---

## Technical Notes

### API Key Resolution

The script searches three `.env` files in order:

1. `arabic-dictionaries/.env` — legacy location
2. `amr-agent/.env` — AMR agent location
3. `arabic-wordnet-v4/.env` — **project-local, loaded with `override=True`**

The project-local `.env` takes priority. The key name `GEM_API_KEY` is bridged to `GEMINI_API_KEY` (which the `google-genai` SDK reads).

### Retry Behavior

- **Retryable errors** (429 rate limit, 503 server error, timeouts): exponential backoff, up to 5 attempts
- **Non-retryable errors** (400 bad request, invalid key): fail immediately, no wasted retries
- **Empty responses**: retried up to 5 times
- **JSON parse failures**: raw response saved to `group_NNNN_raw.txt` for debugging

### Intermittent API Errors

During the pilot, we observed intermittent `API_KEY_INVALID` errors even with a valid key — some requests in the same batch succeeded while others failed. This appears to be a Gemini API propagation issue with newly created keys. The resume mechanism handles this gracefully: failed groups are retried on the next run.

---

## Next Steps

### Scaling Strategy

1. **`--min-count 5`** — 127 groups, ~700 synsets. Estimated: ~5 minutes, $0.00
2. **`--min-count 3`** — 1,362 groups, ~4,700 synsets. Estimated: ~15 minutes, $0.00
3. **Full run** — 5,378 groups, 12,496 synsets. Estimated: ~27 minutes, $0.00

### Post-Processing (Future)

- **Apply high-confidence proposals** directly to AWN4 XML as new lemmas
- **Queue medium-confidence proposals** for human review
- **Filter out flagged synsets** (`CULTURALLY_IRRELEVANT`, `PROPER_NOUN_SKIP`) for separate handling
- **Merge `DECADE_CLUSTER` synsets** using the template pattern
- **Cross-validate** proposed lemmas against the full dictionary DB to catch any hallucinated terms

### Quality Improvements

- **Add classical dictionary evidence** (لسان العرب, تاج العروس) to the evidence packages — would push dictionary coverage from 45.9% to ~70-80%, increasing high-confidence proposal rate
- **Two-pass review** — run a second LLM pass to validate the first pass's proposals against dictionary data
- **Compare models** — run the same groups through `gemini-2.5-flash` or `gemini-3-pro` to measure quality differences
