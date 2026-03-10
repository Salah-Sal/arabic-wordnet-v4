-- ════════════════════════════════════════════════════════════════════════════════
-- Evidence Collection — قوالب الاستعلامات — SQL Query Templates
-- ════════════════════════════════════════════════════════════════════════════════
--
-- قوالب SQL لكل خطوة من خطوات الخوارزمية التسع.
-- Fresh SQL templates for each of the 9 algorithm steps.
--
-- Database: arabic_dict.db (read-only mode)
-- Access:   sqlite3 "file:data/arabic_dict.db?mode=ro"
--
-- All 8 tables covered:
--   entries, dictionaries, definitions, examples,
--   plurals, derived_forms, cross_refs, provenance
--
-- Conventions:
--   ? = positional parameter
--   {excluded_ids} = comma-separated list of entry_ids to exclude
--   {entry_ids}    = comma-separated list of entry_ids to enrich
-- ════════════════════════════════════════════════════════════════════════════════


-- ──────────────────────────────────────────────────────────────────────────────
-- § SHARED: Expanded entry columns
-- ──────────────────────────────────────────────────────────────────────────────
--
-- Every main query returns this column set.
-- Compared to the old _ENTRY_COLUMNS, adds:
--   form, external_id, translation_fr, dict_author, dict_death_year, headword_norm

-- _ENTRY_COLUMNS:
--     e.id              AS entry_id,
--     e.dictionary_id,
--     e.headword,
--     e.headword_bare,
--     e.headword_norm,
--     e.root,
--     e.root_source,
--     e.pos,
--     e.form,
--     e.is_partial,
--     e.definitions_text,
--     e.translation_en,
--     e.translation_fr,
--     e.domain,
--     e.external_id,
--     d.key             AS dict_key,
--     d.name_ar         AS dict_name_ar,
--     d.name_en         AS dict_name_en,
--     d.source_type     AS dict_source_type,
--     d.period          AS dict_period,
--     d.author          AS dict_author,
--     d.death_year      AS dict_death_year


-- ══════════════════════════════════════════════════════════════════════════════
-- PER-LEMMA QUERIES (Steps 1, 2, 3, 6, 7, 8)
-- ══════════════════════════════════════════════════════════════════════════════


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 1: المطابقة الدقيقة — Exact Headword Lookup (with ال awareness)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  normalized lemma (e.g., 'ملاذ')
-- Uses:   idx_entries_headword_norm_cover (covering index)
--
-- CRITICAL: Arabic classical dictionaries list nouns with definite article ال.
-- ~20% of entries (154K) have ال in headword_norm.
-- Example: lemma 'ملاذ' must also match 'الملاذ' (Al-Waseet, Hawramani, etc.)
--
-- Strategy: query both bare form and ال-prefixed form.
-- If lemma already starts with ال, also query stripped form.
-- Params: ?1 = lemma_norm, ?2 = 'ال' || lemma_norm
--         (if lemma starts with ال: ?1 = lemma_norm, ?2 = strip_al(lemma_norm))

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 2: التعريفات المُهيكلة — Structured Definitions (per-sense)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  normalized lemma (same ال-aware params as Step 1)
-- Joins:  definitions child table for per-sense breakdown
-- Order:  chronological (death_year ASC), then by sense_index

SELECT
    e.id              AS entry_id,
    e.headword,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year,
    def.sense_index,
    def.text          AS definition_text,
    def.is_raw
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions def ON def.entry_id = e.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.death_year ASC NULLS LAST, d.name_en, def.sense_index;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 3a: استنتاج الجذر — Root Inference (multi-strategy)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  normalized lemma (same ال-aware params as Step 1)
-- Returns all (root, root_source) pairs found for this headword.
-- Priority: ocr > lane > camel > null
--
-- CRITICAL: Uses ال-aware matching so we find the correct root.
-- Example: 'ملاذ' alone → root 'ملذ' (wrong, from ARABTERM)
--          'الملاذ' → root 'لوذ' (correct, from Al-Waseet OCR)

SELECT DISTINCT
    e.root,
    e.root_source,
    e.id AS from_entry_id
FROM entries e
WHERE e.headword_norm IN (?1, ?2)
  AND e.root IS NOT NULL
ORDER BY
    CASE e.root_source
        WHEN 'ocr'  THEN 1
        WHEN 'lane' THEN 2
        WHEN 'camel' THEN 3
        ELSE 4
    END;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 3b: عائلة الجذر — Root Family Entries (root column + headword match)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  root string (e.g., 'لوذ')
-- Excludes: entry_ids already retrieved in step 1
-- Limit:   200 entries per root (caps worst-case for prolific roots)
--
-- CRITICAL: Many Hawramani entries have root=NULL but headword IS the root form.
-- Example: 10+ Hawramani dicts have headword 'لوذ' with root=NULL.
-- These contain rich definitions (Jawhari, Zamakhshari, Lisān al-ʿArab, Lane, etc.)
-- We match on BOTH root column AND headword to capture these.
-- Params: ?1 = root string

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE (e.root = ?1 OR e.headword_norm = ?1)
  AND e.id NOT IN ({excluded_ids})
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en
LIMIT 200;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 6: الشواهد — Examples
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  normalized lemma (same ال-aware params as Step 1)
-- Returns ALL examples for entries matching this headword.
-- No filtering by type or relevance.

SELECT
    ex.entry_id,
    e.headword,
    d.key             AS dict_key,
    d.name_en         AS dict_name_en,
    d.name_ar         AS dict_name_ar,
    ex.idx,
    ex.type,
    ex.text           AS example_text,
    ex.attribution
FROM examples ex
JOIN entries e ON ex.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY
    CASE ex.type
        WHEN 'quran'   THEN 1
        WHEN 'hadith'  THEN 2
        WHEN 'poetry'  THEN 3
        WHEN 'prose'   THEN 4
        WHEN 'usage'   THEN 5
        ELSE 6
    END,
    ex.idx;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 7: الترتيب الزمني — Chronological Ordering
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  normalized lemma (same ال-aware params as Step 1)
-- Same entries as step 1, but sorted by death_year.
-- Entries without death_year are placed last.
-- NO semantic classification — just the chronological FACT.

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.death_year ASC NULLS LAST;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 8: البحث العكسي — Reverse Lookup (headword + definitions FTS)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  lemma (as FTS5 term)
-- Finds entries that MENTION this lemma in their headword OR definitions_text,
-- but whose normalized headword is DIFFERENT from this lemma.
-- Returns raw entries — no "synonym candidate" labels.
--
-- CRITICAL: Searching headword column (not just definitions_text) captures
-- Al-Mawrid compound headwords like "(1) ملاذ؛ ملجأ؛ مفزع" where the
-- lemma appears as one of several Arabic translations of an English word.
-- These provide rich synonym chains for the evidence.
--
-- BM25 weights: headword(10), headword_bare(5), headword_norm(5), root(3), definitions_text(1)
-- Params: ?1 = lemma, ?2 = lemma_norm, ?3 = 'ال' || lemma_norm

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH '{headword headword_bare definitions_text}:' || ?1
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 100
)
AND e.headword_norm NOT IN (?2, ?3)
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;


-- ══════════════════════════════════════════════════════════════════════════════
-- PER-SYNSET QUERIES (Steps 4, 5, 9)
-- ══════════════════════════════════════════════════════════════════════════════


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 4: البحث النصي الكامل — FTS5 Keyword Search
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  Arabic keywords extracted from synset definition_ar
-- FTS5 MATCH expression: OR-joined quoted terms
-- Excludes: entry_ids already found in steps 1-3

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH ?
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 50
)
AND e.id NOT IN ({excluded_ids})
ORDER BY d.source_type, d.name_en;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 5: الجسر الإنجليزي — English Bridge (ARABTERM)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  English term(s) from OEWN lemmas
-- Searches the entries_translations_fts virtual table.
-- BM25 weights: translation_en(5), translation_fr(3), domain(1)

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_translations_fts
    WHERE entries_translations_fts MATCH 'translation_en:' || ?
    ORDER BY bm25(entries_translations_fts, 5.0, 3.0, 1.0)
    LIMIT 30
)
AND e.id NOT IN ({excluded_ids})
ORDER BY d.source_type, d.name_en;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 9a: التصفية حسب الصنف — POS Filtering
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  root string, POS string
-- Restricts root family by part of speech.

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = ?
  AND e.pos = ?
ORDER BY d.source_type, d.name_en;


-- ──────────────────────────────────────────────────────────────────────────────
-- STEP 9b: التصفية حسب المجال — Domain Filtering (ARABTERM)
-- ──────────────────────────────────────────────────────────────────────────────
-- Input:  domain string, headword_norm to exclude

SELECT
    e.id              AS entry_id,
    e.dictionary_id,
    e.headword,
    e.headword_bare,
    e.headword_norm,
    e.root,
    e.root_source,
    e.pos,
    e.form,
    e.is_partial,
    e.definitions_text,
    e.translation_en,
    e.translation_fr,
    e.domain,
    e.external_id,
    d.key             AS dict_key,
    d.name_ar         AS dict_name_ar,
    d.name_en         AS dict_name_en,
    d.source_type     AS dict_source_type,
    d.period          AS dict_period,
    d.author          AS dict_author,
    d.death_year      AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.domain = ?
  AND e.headword_norm != ?
  AND d.source_type = 'arabterm'
ORDER BY d.name_en
LIMIT 30;


-- ══════════════════════════════════════════════════════════════════════════════
-- CHILD TABLE ENRICHMENT QUERIES
-- ══════════════════════════════════════════════════════════════════════════════
--
-- Run AFTER main queries. Input: batch of entry_ids from any step.
-- These hydrate the full entry object with child table data.


-- ──────────────────────────────────────────────────────────────────────────────
-- ENRICH: التعريفات — Definitions (per-sense)
-- ──────────────────────────────────────────────────────────────────────────────

SELECT entry_id, sense_index, text, is_raw
FROM definitions
WHERE entry_id IN ({entry_ids})
ORDER BY entry_id, sense_index;


-- ──────────────────────────────────────────────────────────────────────────────
-- ENRICH: الشواهد — Examples
-- ──────────────────────────────────────────────────────────────────────────────

SELECT entry_id, idx, type, text, attribution
FROM examples
WHERE entry_id IN ({entry_ids})
ORDER BY entry_id, idx;


-- ──────────────────────────────────────────────────────────────────────────────
-- ENRICH: الجموع — Plurals
-- ──────────────────────────────────────────────────────────────────────────────

SELECT entry_id, idx, text
FROM plurals
WHERE entry_id IN ({entry_ids})
ORDER BY entry_id, idx;


-- ──────────────────────────────────────────────────────────────────────────────
-- ENRICH: المشتقات — Derived Forms
-- ──────────────────────────────────────────────────────────────────────────────

SELECT entry_id, idx, text
FROM derived_forms
WHERE entry_id IN ({entry_ids})
ORDER BY entry_id, idx;


-- ──────────────────────────────────────────────────────────────────────────────
-- ENRICH: الإحالات — Cross References
-- ──────────────────────────────────────────────────────────────────────────────

SELECT entry_id, idx, text
FROM cross_refs
WHERE entry_id IN ({entry_ids})
ORDER BY entry_id, idx;


-- ──────────────────────────────────────────────────────────────────────────────
-- ENRICH: المصدر — Provenance
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    entry_id,
    page_number,
    page_file,
    entry_index,
    volume,
    hawramani_post_id,
    hawramani_slug,
    source_uri
FROM provenance
WHERE entry_id IN ({entry_ids});


-- ══════════════════════════════════════════════════════════════════════════════
-- HELPER QUERIES
-- ══════════════════════════════════════════════════════════════════════════════


-- ──────────────────────────────────────────────────────────────────────────────
-- HELPER: قائمة المعاجم — List All Dictionaries
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    d.id,
    d.key,
    d.name_ar,
    d.name_en,
    d.source_type,
    d.period,
    d.author,
    d.death_year,
    COUNT(e.id) AS entry_count
FROM dictionaries d
LEFT JOIN entries e ON e.dictionary_id = d.id
GROUP BY d.id
ORDER BY d.source_type, d.death_year NULLS LAST;


-- ──────────────────────────────────────────────────────────────────────────────
-- HELPER: فحص سريع — Quick Existence Check (ال-aware)
-- ──────────────────────────────────────────────────────────────────────────────

SELECT COUNT(*) AS match_count
FROM entries
WHERE headword_norm IN (?1, ?2);


-- ──────────────────────────────────────────────────────────────────────────────
-- HELPER: إحصائيات القاعدة — Database Stats
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    (SELECT COUNT(*) FROM entries) AS total_entries,
    (SELECT COUNT(*) FROM dictionaries) AS total_dictionaries,
    (SELECT COUNT(*) FROM definitions) AS total_definitions,
    (SELECT COUNT(*) FROM examples) AS total_examples,
    (SELECT COUNT(*) FROM plurals) AS total_plurals,
    (SELECT COUNT(*) FROM derived_forms) AS total_derived_forms,
    (SELECT COUNT(*) FROM cross_refs) AS total_cross_refs,
    (SELECT COUNT(*) FROM provenance) AS total_provenance;
