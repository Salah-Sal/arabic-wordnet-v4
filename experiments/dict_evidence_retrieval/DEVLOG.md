# Development Log — Dictionary Evidence Retrieval

Chronological record of observations, decisions, and progress.

---

## 2026-03-02 — Retrieval Engine (`retrieve_dict_evidence.py`)

### Session 1: Building the 5-Strategy Pipeline

Built `retrieve_dict_evidence.py` with 5 complementary retrieval strategies against the 760K-entry Arabic dictionary database.

**Strategy design rationale:**
- Strategies A→E form a funnel from high-precision (exact headword) to high-recall (semantic search). Each strategy excludes entry IDs already found by previous ones, so the diagnostic report shows unique contributions.
- Strategy B (root family) is chained to A: it extracts roots from A's entries, then finds morphological relatives. This means B's quality depends on A's root extraction.
- Strategy D (ColBERT) uses 3 sub-queries (lemma, definition, combined) to maximize recall from the semantic index.
- Strategy E (translation bridge) exploits ARABTERM's bilingual structure: AWN4 synset → ILI → OEWN English lemmas → ARABTERM English field → Arabic entries.

**Diverse synset selection:** Implemented `select_diverse_synsets()` to pick synsets across all 4 POS categories (noun, verb, adjective, adverb) with a mix of lemma counts, multi-word expressions, and potential loanwords. This ensures the diagnostic report covers edge cases.

**ColBERT PLAID index:** Used the pre-built index from the `colbertv2 exp/` experiment. The `colbert_index.py` module provides `search()`, `load_model()`, `load_index()`, `load_metadata()`. The PLAID backend is significantly faster than brute-force scoring.

### Observations

- Strategy A alone finds entries for most common Arabic words (high coverage for nouns/verbs, weaker for adjectives/adverbs).
- Strategy B produces 200 entries (capped) but is dominated by ARABTERM noise for common roots like مول, ميل.
- Strategy C (FTS5) is effective for finding definition-similar entries but can return false positives for short/generic definitions.
- Strategy D (ColBERT) takes ~4-7s per synset on CPU. Worth the cost — it finds entries that keyword methods miss entirely.
- Strategy E depends on ILI availability (97.2% of synsets have ILI) and ARABTERM coverage (strong for technical/scientific terms, weak for everyday vocabulary).

**Output:** `report.md` (79 KB) + `results.json` (673 KB) for 10 diverse synsets.

---

## 2026-03-02 — Review Document Generator (`generate_review_doc.py`)

### Session 2: Planning the Linguist Review Format

**Problem:** The engineering diagnostic report (`report.md`) is organized by strategy, making it hard for a linguist to review a single synset. A linguist needs evidence organized by lemma, with clear instructions on what to evaluate.

**Design decisions after user consultation:**
1. **Decision recording format:** Chose YAML sidecar over inline markdown or JSON. YAML is human-readable/editable, version-control friendly, and parseable for downstream automation.
2. **Evidence organization:** Chose per-lemma over per-strategy or unified list. This matches the linguist's mental model: "Is this word (مال) correctly used with this meaning?"
3. **Bilingual headers:** All section headers and labels in Arabic + English, since the linguist may be more comfortable reading Arabic but needs English labels for OEWN cross-reference.

### Session 3: Implementation

**Monkey-patching approach:** Rather than modifying `retrieve_dict_evidence.py`, the review doc generator imports it and monkey-patches `_row_to_dict` to:
- Extend definition truncation from 300 → 500 characters (linguists need fuller context)
- Add `dict_name_ar` and `root_source` fields (needed for bilingual dictionary display)

**`merge_evidence_by_lemma()` — the core function:**
- Takes flat strategy results (keyed by A/B/C/D/E) and reorganizes into per-lemma groups
- Strategy A entries → matched by `normalize_arabic(headword_bare)` == `normalize_arabic(lemma)`
- Strategy B entries → matched via shared root using `root_to_lemma` mapping built from A's results
- Strategy C/D entries → classified as `synonym_candidate` if `definition_similarity > 0.30` and headword differs from all lemmas
- Strategy E entries → matched by headword to the appropriate lemma, or first lemma as fallback

**Two-pass AWN4 parsing:** Added `parse_awn4_relations()` as a second iterparse pass for `<SynsetRelation>` elements. Returns `{synset_id: [{"relType": str, "target": str}, ...]}`. This avoids modifying the shared `parse_awn4()` function. Together, both passes take ~3.2s for the full 109K-synset + 271K-relation XML.

**OEWN English data:** `get_oewn_data(ili)` uses the `wn` library to look up English definitions, lemmas, and examples by ILI. Returns `None` for the 2.8% of synsets without ILI mapping (shown as a warning in the .md).

### First Test: `awn4-13271441-n` (مال/نقود — money)

```
python generate_review_doc.py --synset-ids awn4-13271441-n --no-colbert
→ awn4-13271441-n.md (9 KB) + .yaml  in 3.9s
```

**Observations:**
- Section 1 (Overview): English source ("wealth reckoned in terms of money") alongside Arabic translation ("الثروة المحسوبة من حيث المال") renders cleanly. Good side-by-side comparison.
- Section 4 (Connected Synsets): Hypernym (ثروة/wealth) and hyponym (ثروة كبيرة/pile) both show bilingual tables correctly.
- Section 5 (Instructions): Bilingual review checklist looks clear.

**Two issues identified:**
1. **Headword conflation (مأل vs مال):** Entries for مأل (fatness/heaviness) appeared before actual مال (money) entries in the table. Root cause: `normalize_arabic()` strips hamza, so مأل normalizes to مال. The sort only considered dictionary period, not headword match quality.
2. **Root family section empty:** Despite Strategy B returning 200 entries, the "Root Family" section didn't render. Investigated and found: 197 of 200 entries were ARABTERM (filtered out by render logic). The 3 OCR entries (مول from Kitab Al-Ayn, Maqayis, Mujmal) with actual money-related definitions were present but hadn't rendered in the initial output.

---

## 2026-03-03 — Bug Fixes and Validation

### Fix 1: Headword Match Quality Sort

**Changed `_entry_sort_key()`** to accept a `lemma_bare` parameter. Added a primary sort dimension: entries where `headword_bare` exactly matches the lemma (stripped of diacritics) sort before entries that only match after hamza normalization.

Sort order is now: `(match_quality, authority_level, dict_name)` where:
- `match_quality`: 0 = exact headword_bare match, 1 = normalized-only match
- `authority_level`: 1 = classical, 2 = modern OCR, 3 = modern Hawramani, 4 = ARABTERM, 5 = other

**Result:** After fix, the مال entry table starts with:
1. Firuzabadi (مال, classical) — "مالَ إليه مَيْلاً..."
2. Sultan Qaboos Encyclopedia (مال, classical) — "كل ما يملكه الفرد أو الجماعة من متاع أو تجارة أو نقود" (the actual money definition)
3. Dozy (مال, classical)
4-7. Al-Wasit entries (مال, modern)
8. مأل entry (now correctly at the end)

### Fix 2: Root Family Rendering

After regeneration, the root family section renders correctly. The 3 OCR entries now show:

| Headword | Dictionary | Definition |
|----------|-----------|------------|
| مول | Kitab Al-Ayn | المال: الأنعام عند العرب وما يملك من متاع |
| مول | Maqayis Al-Lugha | اتخاذ المال وكثرته |
| مول | Mujmal Al-Lugha | المال معروف |

These are exactly the entries a linguist needs — root family members that discuss the concept of money/wealth from classical lexicographic sources.

### Fix 3: YAML Missing Lemmas Headword Extraction

**Problem:** Some dictionaries (e.g., Al-Mawrid Al-Hadeeth) store the full entry text in the `headword` field. This caused YAML `missing_lemmas` to contain entries like `lemma: 'البوريه: رقصة فرنسية قديمة أو موسيقاها.'` instead of just `lemma: البوريه`.

**Fix:** Use `headword_bare` (diacritics stripped) instead of `headword`, and extract the word before any `:` separator. Also applied the same `headword_bare` preference to the synonym candidates table in the .md.

### ColBERT Test

```
python generate_review_doc.py --synset-ids awn4-13271441-n
→ awn4-13271441-n.md (11 KB) + .yaml  in 21.6s (includes 3.8s model load)
```

Section 3 (ColBERT-only) now shows 10 semantic-only entries with excellent results:
- المال (with article) — "كل ما يملكه الفرد من متاع أو عروض تجارة أو عقار أو نقود أو حيوان"
- مويلي — diminutive of مال, "تصغير مال بمعنى كل ما يملك..."
- الدثر — "المال الكثير" (abundant wealth)

These are entries that keyword strategies missed because they have different headword forms or use the definite article.

### Batch Test (5 diverse synsets)

```
python generate_review_doc.py --count 5 --seed 42 --no-colbert
```

| Synset | POS | Lemmas | Output Size | Notes |
|--------|-----|--------|-------------|-------|
| `awn4-13271441-n` | noun | مال, نقود | 8 KB | Money — well-attested |
| `awn4-00534261-n` | noun | غافوت | 5 KB | Gavotte (loanword) — no direct entries, but found synonym candidates (كافوت, البوريه) |
| `awn4-11537927-n` | noun | شفط, مص | 11 KB | Suction — good coverage |
| `awn4-00912746-n` | noun | بناء, تشييد, عمارة | 15 KB | Construction — rich evidence, 3 lemmas |
| `awn4-00493346-v` | verb | دنس, لوث | 14 KB | To pollute — 23 entries across 20 dictionaries |

**Edge case observations:**
- **Loanword (غافوت/gavotte):** No direct dictionary entries found (correctly flagged with ⚠). But FTS5 found synonym candidates: ARABTERM has "كافوت" (alternative transliteration) with 0.36 similarity, and Al-Mawrid has البوريه/الكوتليون (other French dances) at 0.46/0.42 similarity. These are shown in the .md for the linguist to review.
- **Root issues (نقود):** CAMeL morphological analyzer returns root "قد" for نقود, which is incorrect (should be "نقد"). This is a data quality issue in the root source, not a pipeline bug. Only 1 ARABTERM entry found, with empty definition.
- **Verbs (دنس):** 23 entries across 20 dictionaries, with excellent classical coverage. The definition "الدَّنَسُ: لَطْخُ الوَسَخِ" (defilement: a stain of filth) from Ibn Sida nicely attests the meaning.

### YAML Validation

```bash
python -c "import yaml; yaml.safe_load(open('output/reviews/awn4-00534261-n.yaml')); print('valid')"
python -c "import yaml; yaml.safe_load(open('output/reviews/awn4-13271441-n.yaml')); print('valid')"
# Both: valid
```

---

## 2026-03-03 — Review Feedback Improvements

### External Review

An external reviewer evaluated the 10 sample `.md` review documents. Their feedback was verified against the actual code — some claims were accurate, others were not.

**Reviewer claims verified:**

| # | Claim | Accurate? | Action taken |
|---|-------|-----------|--------------|
| 1 | Section 1 layout stacked vertically | True | Replaced with side-by-side 3-column table |
| 2 | MWE search polluted by stop words like «في» | **False** — `strategy_a` already filters `len(word) > 2` | Fixed misleading display note only |
| 3 | ColBERT returns phonetic noise for Named Entities | True | Added `instance_hypernym` detection + warning badge |
| 4 | Hard truncation cuts definitions mid-word | True | Removed all truncation |

### Change 1: No Definition Truncation

Removed the `_trunc()` function and all its call sites. The monkey-patch no longer caps at 500 chars — full `definitions_text` from the DB is passed through. All 6 render sites (core definitions, root family, synonym candidates, ColBERT-only, connected synsets) now show complete text.

**Impact on file sizes:** Common Arabic words with deep lexicographic coverage produce much larger files. Example: `awn4-01663142-v.md` (شكّل/صاغ/قولب) grew from ~14 KB to 156 KB because «شكّل» has 60 entries across 45 dictionaries, all with full definitions.

### Change 2: No Result Count Limits

Removed all `[:N]` caps on displayed entries:
- Core dictionary definitions: was `[:8]`, now shows all
- Root family: was `[:5]`, now shows all (non-ARABTERM with definitions)
- Synonym candidates: was `[:5]` render + `[:10]` merge, now shows all
- ARABTERM translations: was `[:5]`, now shows all
- ColBERT-only: was `[:10]`, now shows all
- Removed all "+N more entries not shown" messages

### Change 3: Side-by-Side Section 1

Replaced the two stacked `###` subsections (English Source / Arabic Translation) with a single 3-column comparison table:

```
| الحقل — Field | الإنجليزية (OEWN) | العربية (AWN4) |
|---|---|---|
| **التعريف — Def** | wealth reckoned in terms of money | الثروة المحسوبة من حيث المال |
| **الوحدات — Lemmas** | money | مال ، نقود |
| **أمثلة — Examples** | all his money is in real estate | كل ماله في العقارات |
```

This reduces vertical eye movement when comparing translation against source.

### Change 4: MWE Note Fix

The MWE note previously listed all split words naively (e.g., "في, الحقيقة"), but `strategy_a` silently filters words with `len ≤ 2`. The reviewer incorrectly concluded that «في» polluted the results — it was never actually searched. Fixed the display note to apply the same `len > 2` filter, so it now correctly shows only "الحقيقة".

### Change 5: Named Entity Badge

Added detection of instance synsets (Named Entities) via the `instance_hypernym` relation, which is already parsed by `parse_awn4_relations()`. Two badges added:

1. **Section 1 badge:** After the comparison table, instance synsets show:
   > **كيان مُسمّى — Named Entity (instance synset).** نتائج البحث الدلالي قد تعكس تشابهاً صوتياً/صرفياً وليس دلالياً.

2. **Section 3 warning:** Before ColBERT results, instance synsets show a phonetic-similarity warning.

This addresses the Khabarovsk (خاباروفسك) issue where ColBERT returned entries for the Khabur (خابور) river — phonetic overlap, not semantic relevance.

### Regeneration Test (10 synsets, SQL-only)

| Synset | POS | Lemmas | Size | Notes |
|--------|-----|--------|------|-------|
| `awn4-13271441-n` | noun | مال, نقود | 20 KB | Was 8 KB — full definitions for 16 entries |
| `awn4-00534261-n` | noun | غافوت | 8 KB | Was 5 KB — all 14 synonym candidates shown |
| `awn4-11537927-n` | noun | شفط, مص | 24 KB | Was 11 KB |
| `awn4-00912746-n` | noun | بناء, تشييد, عمارة | 18 KB | Was 15 KB |
| `awn4-00493346-v` | verb | دنس, لوث | 103 KB | Was 14 KB — many full classical definitions |
| `awn4-01663142-v` | verb | شكّل, صاغ, قولب | 156 KB | Was ~14 KB — 60 entries for شكّل alone |
| `awn4-00865514-a` | adj | نظري | 6 KB | Minimal change |
| `awn4-02410992-a` | adj | جامح, غير معتدل | 122 KB | Large root family |
| `awn4-00203457-r` | adv | بذكاء | 3 KB | Minimal — sparse evidence |
| `awn4-00038407-r` | adv | بصدق, حقاً, في الحقيقة | 49 KB | MWE note fixed |

Named Entity badge verified on `awn4-09027827-n` (Khabarovsk) — renders correctly in both Section 1 and Section 3.

---

## 2026-03-03 — Pipeline Improvements Round 2 (Post-Consultant Feedback)

### External Review

Two external reviewers evaluated the 11 sample `.md` review documents. Their feedback was verified claim-by-claim against the code and output. Verified issues fell into three categories: noise reduction, readability, and coverage.

**Reviewer claims verified:**

| # | Claim | Verdict | Action |
|---|-------|---------|--------|
| 1 | Empty definitions create blank rows in tables | TRUE | Change 1: filter empty defs |
| 2 | MWE splitting passes stop words like غير (3 chars > 2) | TRUE | Change 2: ARABIC_STOPWORDS filter |
| 3 | Long definitions create walls of text | TRUE | Change 3: 500-char word-boundary truncation |
| 4 | Noun synonym candidates appear for verb synsets | TRUE | Change 4: POS compatibility filter |
| 5 | Adverbs like بذكاء return zero entries (proclitic prefix) | TRUE | Change 5: prefix-stripping fallback |
| 6 | Dictionary sorting by author death date | FALSE | Already sorted by match quality → period → name |
| 7 | Root conflation (ميل in مال family) | TRUE | Deferred — requires root-sense disambiguation |

### Change 1: Filter Empty Definitions from Core Dictionary Tables

Split `headword_entries` into entries with definitions, entries without definitions, and prefix-stripped entries. Only entries with definitions appear in the main table. Empty-definition entries are summarized in a compact line:

> أيضاً موثّق (بدون تعريف) في — Also attested (no definitions) in: [dict names]

Attestation count still reflects the total across both groups.

**Verification:** نظري: was 6/7 empty rows → now 1 Core row + 5 attested-without-def summary. بناء: was 11/17 empty → now 6 Core rows + 9 attested summary.

### Change 2: Arabic Stop-Word Filter for MWE Splitting

Imported `ARABIC_STOPWORDS` (37-entry frozenset from `rag.similarity`) and added it to the MWE word filter in Strategy A. The guard `len(word) > 2` was insufficient — words like غير (3 chars) are grammatical particles, not content words.

Updated both the retrieval filter and the MWE display note in `generate_review_doc.py` to use the same logic: `len(word) > 2 and word not in ARABIC_STOPWORDS`.

**Verification:** غير معتدل: MWE note now shows only "معتدل", no غير entries in results.

### Change 3: Smart Truncation for Long Definitions

Added `_trunc_word(text, limit=500)` — truncates at the last word boundary before the limit and appends " …". Applied at all 4 definition render sites: Core Dictionary, Root Family, Synonym Candidates, and ColBERT-only tables. ARABTERM translations excluded (already short).

This reverses the previous "no truncation" decision after consultants confirmed that walls of text in table cells harm readability.

**Verification:** شكّل: 20 definitions truncated at ~500 chars. File size dropped from 156 KB to 117 KB.

### Change 4: POS Filtering for Synonym Candidates

Added `_pos_compatible(synset_pos, entry_pos)` using a compatibility map:
- Noun synsets: accept `noun`, `proper_noun`
- Verb synsets: accept `verb`
- Adjective synsets: accept `adj`

Conservative filter: entries with NULL/empty POS or non-standard POS values (phrase, other, particle, root) are kept. Only entries with explicit, clear POS that conflicts are excluded.

**Verification:** The filter works for entries with POS data (noun: 55K, verb: 37K, adj: 8K in DB). ARABTERM entries from Al-Mawrid lack POS data, so "شيء مقدس" still appears for verb synset دنس — this is an accepted trade-off of the conservative approach.

### Change 5: Adverb Prefix Stripping Fallback

After Strategy A runs, any lemma with zero results that starts with a single-character proclitic (ب, ك, ل, ف, و) triggers a fallback: strip the prefix and re-run `tier1_lookup` on the base form. Results are tagged with `_prefix_stripped=True` and rendered in a separate sub-section:

```
#### مطابقة بعد حذف البادئة — Prefix-stripped matches
> البحث عن «ذكاء» بعد حذف البادئة «ب» — Searched for "ذكاء" after stripping prefix "ب"
```

In `merge_evidence_by_lemma()`, prefix-stripped entries are routed back to their `_original_lemma` instead of using headword matching (since the headword is the stripped form, not the original lemma).

**Verification:** بذكاء: was 0 entries → now 16 entries across 15 dictionaries after stripping "ب" → "ذكاء".

### Regeneration Test (10 synsets, SQL-only, seed 42)

| Synset | POS | Lemmas | Size | Notes |
|--------|-----|--------|------|-------|
| `awn4-13271441-n` | noun | مال, نقود | 15 KB | Empty-def filter reduced noise |
| `awn4-00534261-n` | noun | غافوت | 8 KB | Unchanged |
| `awn4-11537927-n` | noun | شفط, مص | 16 KB | Truncation shrank long entries |
| `awn4-00912746-n` | noun | بناء, تشييد, عمارة | 18 KB | 6 with-def + 9 attested summary |
| `awn4-00493346-v` | verb | دنس, لوث | 71 KB | Was 103 KB — truncation helped |
| `awn4-01663142-v` | verb | شكّل, صاغ, قولب | 117 KB | Was 156 KB — 20 defs truncated |
| `awn4-00865514-a` | adj | نظري | 6 KB | 1 Core row + 5 attested summary |
| `awn4-02410992-a` | adj | جامح, غير معتدل | 7 KB | Was 122 KB — stop-word filter + truncation |
| `awn4-00203457-r` | adv | بذكاء | 50 KB | Was 3 KB — 16 prefix-stripped entries |
| `awn4-00038407-r` | adv | بصدق, حقاً, في الحقيقة | 44 KB | Unchanged |

---

## Open Issues / Future Work

1. **Root quality for نقود:** CAMeL returns "قد" instead of "نقد". Consider adding Lane's Lexicon or manual root overrides as a fallback root source.

2. **Hawramani headword conflation:** The Hawramani database stores entries under normalized headwords, so مأل entries appear under مال queries. The sort fix mitigates this in the UI, but a deeper fix would add a `headword_original` field to the DB.

3. **Multi-word lemma handling:** Currently splits multi-word lemmas and searches individual words (with ARABIC_STOPWORDS filter). Could be improved with phrase-level FTS5 queries.

4. **ARABTERM noise in root family:** Strategy B returns up to 200 entries, often dominated by ARABTERM. The render filter (non-ARABTERM + non-empty definition) works but could be replaced with a relevance score.

5. **Batch processing at scale:** Current approach parses AWN4 XML + relations on every run (~3.2s overhead). For processing all 109K synsets, consider a pre-parsed cache or database.

6. **Linguist workflow integration:** The YAML sidecar format is designed for git-based review workflows. A future web UI could read/write the same YAML files.

7. **Root conflation in Strategy B:** Roots like م-و-ل match both مال (money) and ميل (inclination). A root-sense disambiguation layer would improve root family quality, but this is complex and deferred.

8. **POS inference for ARABTERM:** Al-Mawrid entries lack POS tags, so the conservative POS filter can't catch mismatches. Future: infer POS from headword morphology (e.g., يُـ prefix → verb) or definition patterns.

9. **Multi-character proclitic stripping:** The current prefix-stripping only handles single-character proclitics (ب, ك, ل, ف, و). Multi-character prefixes like بال, وال, كال are not yet handled.
