# Evidence YAML — Content-Level Redundancy Rules

> Rules of thumb for safely removing data from evidence YAML files without affecting information quality for the linguistic reviewer.

**Date:** 2026-03-09
**Corpus:** 15 sample `.evidence.yaml` files (38 MB raw, 726K lines) + context from `slim_evidence.py` (production: 120K `.evidence.yaml.gz` files)
**Method:** Manual examination of raw YAML content across small, medium, and large files

---

## What `slim_evidence.py` Already Handles

The existing gentle slimmer removes four categories of dead weight:

| Already removed | Rules below |
|----------------|-------------|
| step7_chronological (100% duplicate of step1) | ~~Rule 1~~ |
| Debug metadata (sql_template, query_params, excluded_entry_ids, al_variants_searched) | ~~Rules 13, 16~~ |
| _meta section | ~~Rule 14~~ |
| Empty/null values from entries (cross_refs: [], provenance: null, etc.) | ~~Rules 6, 10, 11~~ |

The rules below document **what remains after slimming** — additional redundancies that could be removed for further savings. Rules already handled by `slim_evidence.py` are marked as such and kept for reference.

---

## Quantified Duplication Baseline (pre-slim, from 15 samples)

| Metric | Value |
|--------|-------|
| Total `entry_id` occurrences (all files, all steps) | 17,060 |
| Unique entry_ids | 12,654 |
| Redundant occurrences | **4,406 (25.8%)** |
| Worst-case file (multi-lemma, shared root) | **1.81x duplication** |
| Single-lemma files | ~1.01x (near-zero) |

---

## Rules of Thumb

### Rule 1 — step7 is always identical to step1. Drop it. `HANDLED`

**Status:** Already removed by `slim_evidence.py`.

**Pattern:** `step7_chronological` returns the exact same entries as `step1_headword`, re-sorted by `dict_death_year`. The YAML itself confirms this — both steps reference the same query anchor (`query_params: *id001`).

**Evidence:** Verified across every lemma in all 15 sample files. Zero exceptions. Confirmed at production scale (120K files).

**Why it's safe:** `dict_death_year` is already present on each step1 entry. The reviewer can sort by date. No information is lost.

---

### Rule 2 — step2 is always a subset of step1. Consider dropping. `NOT YET HANDLED`

**Pattern:** `step2_definitions` returns the subset of step1 entries that have non-empty `definitions_text`. It uses a different key name (`entries_with_senses` instead of `entries`) and adds a `senses` sub-list, but the entries themselves are a strict subset of step1.

**Evidence:** In many lemmas (e.g., `أيّد` with 32 entries), step2 == step1 exactly because all step1 entries already have definitions. When step2 is smaller, every entry in step2 also appears in step1.

**Why it's safe:** The reviewer already sees definitions on each step1 entry via `definitions_text` and `definitions`. step2 adds no new entries — it's a filtered view the reviewer doesn't need pre-computed.

**Caution:** step2 uses `entries_with_senses` which has a `senses` sub-list (sense_index + text + is_raw). If the reviewer needs senses broken out separately from `definitions_text`, step2 is the only place that provides this per-entry. However, the same `definitions` list on each step1 entry already carries this structure — making step2 fully redundant.

**Impact:** Eliminates ~12% of redundant entry occurrences.

---

### Rule 3 — step3 is massively duplicated across lemmas that share a root. Deduplicate it. `NOT YET HANDLED`

**Pattern:** When a synset has multiple lemmas derived from the same Arabic root, their `step3_root_family` results are 99-100% identical. Each lemma gets its own full copy of the root family.

**Evidence:**

| File | Lemma pair | Shared step3 entries | Overlap |
|------|-----------|---------------------|---------|
| `awn4-10691175-n` | خَلَف / خَلِيفَة | 199 of 200 | 99.5% |
| `awn4-00807038-v` | اتّفق / وافق | 245 of 246 | 99.6% |
| `awn4-92450650-n` | ستارة المقهى / ستارة نصفية | 200 of 200 | 100% |

**Why it's safe:** The root family is the same regardless of which lemma triggered the lookup. Showing it once (under the first lemma, or lifted to synset level) preserves all information.

**Implementation note:** This requires cross-lemma comparison within a file. For each `by_root` key that appears under multiple lemmas, keep the entries only under the first lemma and add a reference marker under subsequent lemmas (e.g., `see_root_under: <first_lemma>`). Alternatively, move all `by_root` data to `per_synset` level.

**Impact:** Eliminates ~24% of redundant entry occurrences. Largest single win for multi-lemma synsets. No effect on single-lemma files.

---

### Rule 4 — step9 empty filters are noise. Drop filters with 0 results. `PARTIALLY HANDLED`

**Status:** `slim_evidence.py` keeps step9 and strips debug keys from each filter. It does NOT drop zero-result filters.

**Updated understanding:** At production scale, step9 has results in ~80% of files (corrected from the 15-sample analysis which showed few results). step9 is valuable and should be kept.

**Pattern:** Each filter in `filters_applied` with `result_count: 0` and `entries: []` adds structural noise. After `slim_evidence.py` strips debug keys, a zero-result filter still contains `filter_type`, `description`, `result_count: 0`, `entries: []`.

**Recommendation:** Drop filters where `result_count == 0`. Keep only filters that found entries. This preserves the 80% of files where step9 contributes meaningful results while removing the noise from the others.

**Impact:** Small per-file, but cleaner.

---

### Rule 5 — Arabterm entries carry no Arabic linguistic content. Consider compressing them. `NOT YET HANDLED`

**Status:** `slim_evidence.py` strips empty/null values (so the empty arrays are already gone), but arabterm entries still carry the full field set. After slimming, an arabterm entry retains: `entry_id`, `dictionary_id`, `headword`, `headword_bare`, `headword_norm`, `root`, `root_source`, `definitions_text` (often empty string — but `""` is not stripped by `_strip_empty` since only `""` matches, and some arabterm entries DO have short definitions_text), `translation_en`, `translation_fr`, `domain`, `external_id`, `dict_key`, `dict_name_ar`, `dict_name_en`, `dict_source_type`, `dict_period`, `dict_death_year` (null → stripped), `dict_author` (null → stripped).

**Pattern:** Arabterm entries (72-84% of all entries) consistently have their linguistic value concentrated in just: `headword` + `translation_en` + `translation_fr` + `domain`. The remaining fields are either identifiers (`entry_id`, `dictionary_id`, `external_id`), normalized headword variants (`headword_bare`, `headword_norm`), or dictionary metadata that repeats per-dictionary (Rule 8).

**Evidence:** Verified across 1,649 arabterm entries in the largest sample file. No exceptions.

**Source type breakdown (large file):**

| Source | Count | % of entries |
|--------|------:|:-------------|
| arabterm | 1,649 | 78% |
| hawramani | 333 | 16% |
| ocr | 226 | 11% |

**Potential action:** For the prompt/reviewer context, arabterm entries could be represented more compactly. But this crosses from "stripping dead weight" into "restructuring" territory — the gentle approach would be to leave them as-is after null/empty stripping.

---

### Rule 6 — Empty arrays and null values. Omit when empty. `HANDLED`

**Status:** Already handled by `slim_evidence.py`'s `_strip_empty()`.

**Pattern for reference:**

| Field | Empty rate | Only populated by |
|-------|-----------|-------------------|
| `cross_refs` | 99.8% | OCR classical |
| `derived_forms` | 98.9% | OCR classical |
| `plurals` | 97.8% | OCR classical |
| `examples` | 94.5% | OCR + hawramani classical |

After slimming, these fields only appear when they carry actual data (from OCR entries).

---

### Rule 7 — `definitions_text` duplicates `definitions[0].text` for single-sense entries. Keep one. `NOT YET HANDLED`

**Pattern:** Every hawramani and arabterm entry has exactly one sense. For these entries, `definitions_text` is a verbatim copy of `definitions[0].text`. The `definitions` list adds `sense_index` and `is_raw` metadata, but `sense_index` is always 0 and `is_raw` is predictable by source type (always 1 for hawramani, always 1 for arabterm).

Only OCR entries with multiple parsed senses have genuinely different content between the two fields — OCR entries split the raw text into numbered senses.

**Evidence:** 100% correlation in all files examined. When `definitions_text: ''`, then `definitions: []` (1,104 cases in large file). When populated, single-sense entries always match.

**Why it's safe:** Keep `definitions_text` (the flat string). For single-sense entries, drop `definitions`. For multi-sense OCR entries, keep both (or merge).

**Caution:** The `definitions` list carries `is_raw` which distinguishes OCR-parsed (0) from raw-scraped (1) text. If this distinction matters to the reviewer, keep `definitions` for OCR entries.

---

### Rule 8 — Six dictionary metadata fields are per-dictionary constants. Factor them out. `NOT YET HANDLED`

**Pattern:** These fields have the same value for every entry from a given dictionary:

| Field | Unique values (large file) | Total occurrences |
|-------|---------------------------|-------------------|
| `dict_name_ar` | ~158 | 2,208 |
| `dict_name_en` | ~158 | 2,208 |
| `dict_source_type` | 3 (`arabterm`, `hawramani`, `ocr`) | 2,208 |
| `dict_period` | 2 (`classical`, `modern`) | 2,208 |
| `dict_author` | ~3 non-null + null | 2,208 |
| `dict_death_year` | ~30-40 integers + null | 2,208 |

Each dictionary's entries carry all 6 fields repeated identically. Across 15 sample files, this means ~16,700 repetitions of the same dictionary metadata strings. At 120K files production scale, this is enormous.

**Why it's safe:** Move these to a `_dictionaries` lookup table keyed by `dict_key` (or `dict_name_ar`). Each entry then carries only the key as a foreign reference. The reviewer can look up period/author/death_year from the table when needed.

**Caution:** This changes the entry structure. Downstream consumers (prompt template, reviewer LLM) would need to understand the lookup table. This is a "restructuring" change, not just stripping.

**Impact:** ~10-15% reduction in post-slim file size.

---

### Rule 9 — `dict_period` has only 2 values. It's redundant with source type. `NOT YET HANDLED`

**Pattern:** `dict_period` is either `classical` or `modern`. In practice:
- `arabterm` → always `modern`
- `hawramani` → always `classical`
- `ocr` → mixed (some classical like كتاب العين, some modern like المعجم الوسيط)

So for 90%+ of entries, `dict_period` is fully predictable from `dict_source_type`. After `slim_evidence.py` strips nulls, this field still appears on every entry.

**Why it's safe:** If dictionary metadata is factored out (Rule 8), this becomes a single value in the lookup table rather than repeated on every entry. Standalone, it's low-value since the reviewer can infer period from dictionary name.

---

### Rule 10 — `hawramani_post_id` and `hawramani_slug` are always null. `HANDLED`

**Status:** Already handled by `slim_evidence.py`'s `_strip_empty()` — null values are omitted.

**Pattern for reference:** Both fields appear in the raw `provenance` block of hawramani entries but are never populated. 100% null across all files.

---

### Rule 11 — `form` is null 97.5%, `pos` null 91%, `is_partial` always 0. `HANDLED`

**Status:** Mostly handled by `slim_evidence.py`'s `_strip_empty()` — null values are omitted. `is_partial: 0` is NOT stripped (0 is not in `_EMPTY_VALUES`).

**Remaining:** `is_partial: 0` appears on every entry and is never 1. Could be added to stripping logic or treated as a known constant.

**Pattern for reference:** `pos` and `form` are only populated on OCR-parsed entries from structured dictionaries (كتاب العين, مقاييس اللغة, المعجم الوسيط). After slimming, they only appear when non-null (correct behavior).

---

### Rule 12 — `provenance` structure varies by source type. `PARTIALLY HANDLED`

**Status:** `slim_evidence.py` strips null sub-fields within provenance, which effectively simplifies it. But the `provenance` key itself still appears when it has at least one non-null sub-field.

**Post-slim pattern:**
- **arabterm:** `provenance` entirely removed (was `null`)
- **hawramani:** `provenance: {source_uri: "https://arabiclexicon.hawramani.com/..."}` (only non-null field survives)
- **ocr:** `provenance: {page_number: "٤٥١", page_file: "page_0483", entry_index: 25}` (meaningful fields survive)

This is already clean after slimming. No further action needed.

---

### Rule 13 — `sql_template` repeated per query block. `HANDLED`

**Status:** Already removed by `slim_evidence.py` (in `STEP_DEBUG_KEYS`).

---

### Rule 14 — `_meta` identical across all files. `HANDLED`

**Status:** Already replaced with `{slimmed: True}` by `slim_evidence.py`.

---

### Rule 15 — `result_count` always equals `len(entries)`. `NOT YET HANDLED`

**Pattern:** Every query block has `result_count: N` followed by an `entries` list of exactly N items. It's a pre-computed count that adds no information.

**Evidence:** 405 occurrences across 15 sample files. `result_count` matches `len(entries)` in every case.

**Why it's safe:** The count is derivable from the list length. Drop it.

**Impact:** Small (~1%), but removes noise from every step in every file.

---

### Rule 16 — `excluded_entry_ids` in steps 4 and 5. `HANDLED`

**Status:** Already removed by `slim_evidence.py` (in `STEP_DEBUG_KEYS`).

---

### Rule 17 — `identity.lemma_bare` and `identity.lemma_norm` are derivable. `NOT YET HANDLED`

**Pattern:** Each lemma's `identity` block contains:
```yaml
lemma: سَاقَ        # with diacritics
lemma_bare: ساق     # strip diacritics
lemma_norm: ساق     # normalize (usually == lemma_bare)
is_multiword: false
components: []       # empty when not multiword
```

`lemma_bare` = strip diacritics from `lemma`. `lemma_norm` usually equals `lemma_bare`. `components: []` is already stripped by `slim_evidence.py` (empty list).

**Why it's safe:** Keep only `lemma` and `is_multiword`. For multiword entries, keep `components` (already conditional after slimming).

**Impact:** Negligible per file, but cleaner.

---

## Source Type Quick Reference

The single most powerful rule: **source type determines which fields carry information.**

| | arabterm (72-84%) | hawramani (10-16%) | ocr (7-11%) |
|---|---|---|---|
| **Carries** | headword, translation_en/fr, domain | headword, definitions_text (long prose) | headword, definitions (multi-sense), examples, plurals, derived_forms |
| **Always empty** | definitions_text (often), examples, plurals, derived_forms, cross_refs, dict_author, dict_death_year, provenance | examples, plurals, derived_forms, cross_refs, translation_en/fr, domain | translation_en/fr, domain |
| **Minimal entry** | headword + translation_en + domain | headword + definitions_text + dict_name_ar | headword + definitions + dict_name_ar (+ optional examples, plurals, etc.) |

---

## Priority: What Remains After `slim_evidence.py`

### Already handled (no further action)

| Rule | What was removed |
|------|-----------------|
| 1 | step7_chronological |
| 6 | Empty arrays/null values on entries |
| 10 | Always-null hawramani provenance fields |
| 11 | Null form/pos (is_partial:0 remains) |
| 12 | Null provenance sub-fields |
| 13 | sql_template + query_params |
| 14 | _meta section |
| 16 | excluded_entry_ids |

### Next tier — safe, moderate savings

| Rule | Description | Difficulty | Est. additional savings |
|------|-------------|------------|------------------------|
| 3 | Deduplicate step3 across same-root lemmas | Medium (cross-lemma logic) | ~10-20% (multi-lemma files only) |
| 2 | Drop step2 (⊆ step1) | Easy (delete step) | ~5-10% |
| 8 | Factor dictionary metadata into lookup table | Medium (restructuring) | ~10-15% |
| 7 | Drop `definitions` when it duplicates `definitions_text` | Easy (conditional) | ~3-5% |
| 15 | Drop `result_count` | Trivial | ~1% |
| 4 | Drop zero-result step9 filters | Easy | ~1-2% |

### Future / requires restructuring

| Rule | Description | Why it's harder |
|------|-------------|-----------------|
| 5 | Compress arabterm entries | Changes entry shape by source type |
| 8 | Dictionary metadata lookup table | Downstream consumers need updating |
| 9 | dict_period removal | Only useful if Rule 8 is done first |
| 17 | Simplify identity block | Minor savings, may affect downstream |

### Estimated combined savings (post-slim)

| Scope | Est. additional reduction |
|-------|--------------------------|
| Rules 2 + 3 (structural) | ~15-25% beyond slim |
| + Rules 7, 15, 4 (field cleanup) | ~20-30% beyond slim |
| + Rule 8 (dict metadata refactor) | ~30-40% beyond slim |
