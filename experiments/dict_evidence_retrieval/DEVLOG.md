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
- **Loanword (غافوت/gavotte):** No direct dictionary entries found (correctly flagged with ⚠). But FTS5 found synonym candidates: ARABTERM has "كافوت" (alternative transliteration) with 0.36 similarity, and Al-Mawrid has البوريه/الكوتليون (other French dances) at 0.46/0.42 similarity. YAML pre-populates these as `missing_lemmas`.
- **Root issues (نقود):** CAMeL morphological analyzer returns root "قد" for نقود, which is incorrect (should be "نقد"). This is a data quality issue in the root source, not a pipeline bug. Only 1 ARABTERM entry found, with empty definition.
- **Verbs (دنس):** 23 entries across 20 dictionaries, with excellent classical coverage. The definition "الدَّنَسُ: لَطْخُ الوَسَخِ" (defilement: a stain of filth) from Ibn Sida nicely attests the meaning.

### YAML Validation

```bash
python -c "import yaml; yaml.safe_load(open('output/reviews/awn4-00534261-n.yaml')); print('valid')"
python -c "import yaml; yaml.safe_load(open('output/reviews/awn4-13271441-n.yaml')); print('valid')"
# Both: valid
```

---

## Open Issues / Future Work

1. **Root quality for نقود:** CAMeL returns "قد" instead of "نقد". Consider adding Lane's Lexicon or manual root overrides as a fallback root source.

2. **Hawramani headword conflation:** The Hawramani database stores entries under normalized headwords, so مأل entries appear under مال queries. The sort fix mitigates this in the UI, but a deeper fix would add a `headword_original` field to the DB.

3. **Multi-word lemma handling:** Currently splits multi-word lemmas and searches individual words. Could be improved with phrase-level FTS5 queries.

4. **ARABTERM noise in root family:** Strategy B returns up to 200 entries, often dominated by ARABTERM. The render filter (non-ARABTERM + non-empty definition) works but could be replaced with a relevance score.

5. **Batch processing at scale:** Current approach parses AWN4 XML + relations on every run (~3.2s overhead). For processing all 109K synsets, consider a pre-parsed cache or database.

6. **Linguist workflow integration:** The YAML sidecar format is designed for git-based review workflows. A future web UI could read/write the same YAML files.
