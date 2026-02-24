# Experiment: Polysemy Disambiguation Pipeline (Quality Pipeline Stages 2–3)

| | |
|---|---|
| **Date** | 2026-02-23 (pipeline), 2026-02-24 (documentation) |
| **Scripts** | `polysemy_packages.py` (Stage 2), `polysemy_review.py` (Stage 3) |
| **Model** | Gemini 3 Flash Preview (free tier) |
| **Status** | Pilot complete (5 groups, 66 synsets); full run pending |

---

## Motivation

The pre-filter (Stage 1) discovered **5,378 groups of synsets sharing identical normalized lemma sets** — 12,496 synsets total (11.4% of AWN4). The worst case: عقد appears as the sole lemma in 18 different noun synsets (legal contract, bridge bid, decade, etc.). A user browsing AWN4 sees 18 entries all labeled "عقد" with no way to tell them apart.

**The core problem is lemma disambiguation** — not synset validation or dictionary grounding. The solution: add disambiguating Arabic synonyms to each synset so they become distinguishable.

## Stage 2: Evidence Package Assembly

**Script:** `polysemy_packages.py`
**Input:** `../prefilter/prefilter_report.json` (Stage 1 output)
**Output:** `polysemy_packages.json` (16.7 MB)
**Runtime:** 3.5 seconds

For each of the 5,378 groups, assembles a self-contained evidence package combining:
1. **AWN4 synset data** — definitions, examples, ILI links
2. **Hypernym context** — first hypernym resolved for each synset, revealing the English sense structure (e.g., عقد "legal contract" → hypernym "written agreement" vs عقد "decade" → hypernym "time period")
3. **Dictionary evidence** — entries from المعجم الوسيط, المعجم الكبير, كتاب العين, مقاييس اللغة, مجمل اللغة (22 sources total)

### Key metrics

| Metric | Value |
|---|---|
| Packages assembled | 5,378 |
| Total synsets covered | 12,496 |
| Packages with dictionary evidence | 2,856 (53.1%) |
| Synsets with hypernym context | 10,248 (82.0%) |

Dictionary coverage is higher for polysemous words (53.1%) than AWN4 overall (24.9%) because polysemous words are by definition high-frequency and well-attested.

## Stage 3: LLM Review

**Script:** `polysemy_review.py`
**Input:** `polysemy_packages.json` (Stage 2 output)
**Output:** `reviews/group_NNNN.json` (one per group), `review_summary.json`

### Prompt design

A focused ~60-line Arabic system prompt (not the 262-line linguist prompt) doing one thing:

> أنت لغوي عربي متخصص في المعجمية الحاسوبية. مهمتك الوحيدة: اقتراح لمات عربية إضافية تميّز كل مجموعة ترادفية عن بقية المجموعات التي تشترك معها في نفس اللمة.

Key instructions:
- Propose 1–2 fully vocalized Arabic lemmas per synset
- Prefer specialized terms (اللفظ المختص) over generic qualifiers
- Cite dictionary evidence where available
- Flag culturally irrelevant concepts, decade clusters, proper nouns, identical senses
- Output structured JSON with confidence levels

### Pilot results (top 5 groups, 66 synsets)

| Group | Lemma | Synsets | Key Disambiguation |
|---|---|---|---|
| 0 | عقد | 18 | تَعَاقُدٌ (contract) vs عَشْرِيَّةٌ (decade) vs عَقْدُ اللَّعِبِ (bridge bid) |
| 1 | رفع | 15 | فَكَّ (lift blockade) vs نَصَبَ (raise flag) vs حَمَّلَ (upload) |
| 2 | رأس | 13 | هَامَةٌ (head/body) vs قِمَّةٌ (top) vs رَأْسُ العَضَلَةِ (muscle origin) |
| 3 | قاعدة | 10 | رِكْزَة (pedestal) vs ضَابِط (rule) vs قَاعِدَةٌ عَسْكَرِيَّة (military base) |
| 4 | سحب | 10 | بَزَلَ (draw liquid) vs قَطَرَ (tow) vs اسْتَرَدَّ (withdraw money) |

### Aggregate stats

- 114 proposed lemmas, avg 1.73 per synset
- Confidence: 41% high (dictionary-attested), 56% medium, 3% low
- Flags: 15 `DECADE_CLUSTER`, 2 `CULTURALLY_IRRELEVANT`, 1 `PROPER_NOUN_SKIP`
- Cost: **$0.00** (Gemini free tier)
- Elapsed: ~4 minutes (with retries)

## Key Findings

1. **The LLM identifies semantic clusters.** The عقد group (18 synsets) was correctly split into legal contract (1), generic decade (1), specific decades (15, all flagged `DECADE_CLUSTER`), and bridge game (1, flagged `CULTURALLY_IRRELEVANT`).

2. **Specialized Arabic vocabulary surfaces.** بَزَلَ (draw liquid), قَطَرَ (tow nautically), رِكْزَة (pedestal), دَرْفَلَ (roll metal), هَامَةٌ (head), عَشْرِيَّةٌ (decade) — exactly the kind of vocabulary that distinguishes a quality wordnet from a mechanical translation.

3. **Verb groups are harder than noun groups.** High-confidence proposals: 46.3% for nouns vs 32.0% for verbs. Arabic verbal morphology creates near-synonymous forms that blur distinctions.

4. **Diacritization quality is consistent.** All 114 proposed lemmas include correct full tashkeel.

5. **Dictionary evidence matters.** Higher evidence → higher confidence. The 53.1% of packages with dictionary data produced significantly more high-confidence proposals.

## Assumptions & Scope

### What this experiment assumes
- **Synset sense distinctions (from English WordNet) are valid.** The pipeline does not question whether 18 meanings of عقد should exist as separate synsets.
- **Arabic definitions are roughly correct translations.** Used as context, not validated.

### What this experiment does NOT assume
- **That AWN4 lemma choices are adequate.** The entire pipeline exists because they are not.
- **That all synsets are culturally relevant.** The flag system explicitly identifies irrelevant concepts.
- **That all synsets are unique.** The `IDENTICAL_SENSES` flag acknowledges potential duplicates.

### The role of dictionaries
Dictionary evidence is used as a **tool for finding authentic disambiguating terms**, not as a validation criterion. The problem is lemma disambiguation, not dictionary grounding.

## Scaling Plan

| Phase | Scope | Estimated Time | Cost |
|---|---|---|---|
| 1 | `--min-count 5` → 127 groups, ~700 synsets | ~5 min | $0.00 |
| 2 | `--min-count 3` → 1,362 groups, ~4,700 synsets | ~15 min | $0.00 |
| 3 | Full run → 5,378 groups, 12,496 synsets | ~27 min | $0.00 |

## Post-Processing (Future)

- Apply high-confidence proposals directly to AWN4 XML as new lemmas
- Queue medium-confidence proposals for human review
- Filter flagged synsets (`CULTURALLY_IRRELEVANT`, `PROPER_NOUN_SKIP`) for separate handling
- Cross-validate proposed lemmas against the full dictionary DB

## Outputs

| File | Description |
|---|---|
| `polysemy_packages.py` | Stage 2 — evidence package assembly |
| `polysemy_review.py` | Stage 3 — LLM review with async Gemini calls |
| `polysemy_packages.json` | 5,378 evidence packages (16.7 MB) |
| `reviews/group_NNNN.json` | Per-group LLM review results |
| `review_summary.json` | Aggregate stats across all reviewed groups |
| `PACKAGES_FINDINGS.md` | Detailed Stage 2 analysis |
| `REVIEW_FINDINGS.md` | Detailed Stage 3 analysis |
| `PIPELINE_EXAMPLES.md` | Three worked examples (bilingual) for linguist review |

## Relationship to Other Experiments

```
prefilter/ (Stage 1) ──→ DUPLICATE_SYNSETS list
     │
     └──→ polysemy_packages.py (Stage 2) ──→ evidence packages
              │
              └──→ polysemy_review.py (Stage 3) ──→ disambiguating lemmas
                        │
                        └──→ [future] apply to AWN4 XML

linguist_review/ ──→ Arabic tone/style conventions reused in system prompt
```
