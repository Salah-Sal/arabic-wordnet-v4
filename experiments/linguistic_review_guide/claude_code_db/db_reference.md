# مرجع قاعدة البيانات المعجمية — Arabic Dictionary DB Reference

> اقرأ هذا الملف أولاً — قبل أي استعلام.
> Read this file first — before any query.

---

## أ. نظرة عامة — Overview

| Metric | Value |
|---|---|
| Database engine | SQLite 3 (WAL journal, FTS5) |
| Total entries | 760,660 |
| Dictionaries | 107 |
| Definitions | 614,227 |
| Examples | 86,031 (quran/hadith/poetry/usage/proverb) |
| Size on disk | ~2.1 GB |

### مصادر البيانات — Data Sources

| source_type | Dictionaries | Entries | Content |
|---|---|---|---|
| `ocr` | 5 | 109,769 | Gemini-extracted from classical Arabic lexicons (Al-Waseet, Al-Kabir). Best roots (`root_source='ocr'`). Full multi-sense definitions. |
| `hawramani` | 51 | 233,465 | Classical+medieval lexicons via arabiclexicon.hawramani.com. Rich definitions. Root often NULL (headword IS the root). |
| `arabterm` | 51 | 417,426 | Modern multilingual terminology (ALECSO). Has `translation_en`, `translation_fr`, `domain`. No definitions_text. |

---

## ب. كيفية الاستعلام — How to Query

### الأمر الأساسي — Base command

```bash
sqlite3 -json "DB_PATH" "SELECT ..."
```

`-json` returns a JSON array. Arabic text prints correctly.

> **Important:** Replace `DB_PATH` with the actual database path provided in the user prompt.

### تحسين الأداء — Performance (run once)

```bash
sqlite3 "DB_PATH" "PRAGMA cache_size=-64000; PRAGMA mmap_size=3000000000; SELECT 'OK';"
```

### تسوية النص العربي — Arabic Normalization

The `headword_norm` column is already normalized: diacritics stripped, alef forms (أإآ) → ا, ya (ى) → ي, tatweel (ـ) removed.

**When you construct a search term**, apply the same normalization:
- Strip diacritics: remove all harakat (◌َ◌ُ◌ِ◌ّ◌ْ◌ً◌ٌ◌ٍ etc.)
- Normalize: أإآ → ا, ى → ي, remove ـ

Example: lemma `كَتَبَ` → search for `headword_norm = 'كتب'`

### وعي الـ«ال» — ال-Awareness

**~20% of entries** (154K) store nouns with the definite article ال in `headword_norm`.
**Always search BOTH forms:**

```sql
WHERE headword_norm IN ('ملاذ', 'الملاذ')
```

If the lemma already starts with ال, search both the full form and the stripped form:
```sql
-- lemma = 'الكتاب'
WHERE headword_norm IN ('الكتاب', 'كتاب')
```

---

## ج. الجداول — Schema

### entries (760,660 rows)

```sql
CREATE TABLE entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dictionary_id   INTEGER NOT NULL REFERENCES dictionaries(id),
    headword        TEXT NOT NULL,           -- with diacritics: كَتَبَ
    headword_bare   TEXT NOT NULL,           -- diacritics stripped: كتب
    headword_norm   TEXT NOT NULL,           -- fully normalized (search on this)
    root            TEXT,                    -- trilateral root: كتب (space-free)
    root_source     TEXT,                    -- 'ocr' | 'lane' | 'camel' | NULL
    pos             TEXT,                    -- verb/noun/adj/particle/proper_noun/phrase
    form            TEXT,                    -- verb form I–X, NULL for non-verbs
    is_partial      INTEGER NOT NULL DEFAULT 0,
    definitions_text TEXT NOT NULL DEFAULT '', -- flattened definitions (OCR/Hawramani)
    translation_en  TEXT,                    -- ARABTERM only
    translation_fr  TEXT,                    -- ARABTERM only
    domain          TEXT,                    -- ARABTERM only
    external_id     TEXT                     -- dedup key
);
```

**Root source priority:** ocr (most accurate) > lane > camel > NULL.

### dictionaries (107 rows)

```sql
CREATE TABLE dictionaries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    key           TEXT NOT NULL UNIQUE,       -- e.g. 'Al_Waseet'
    name_ar       TEXT,                       -- المعجم الوسيط
    name_en       TEXT,                       -- Al-Mu'jam Al-Wasit
    source_type   TEXT NOT NULL DEFAULT 'ocr', -- 'ocr' | 'hawramani' | 'arabterm'
    group_key     TEXT,
    period        TEXT,                        -- 'modern' | 'classical'
    author        TEXT,
    death_year    INTEGER,                     -- CE year of author's death
    metadata      TEXT DEFAULT '{}'
);
```

### definitions (614,227 rows) — per-sense breakdown

```sql
CREATE TABLE definitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    sense_index INTEGER NOT NULL DEFAULT 0,  -- 0-based
    text        TEXT NOT NULL,
    is_raw      INTEGER NOT NULL DEFAULT 0   -- 1 = unparsed blob (Hawramani)
);
```

### examples (86,031 rows) — citations

```sql
CREATE TABLE examples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL DEFAULT 0,
    type        TEXT,     -- 'quran' | 'hadith' | 'poetry' | 'usage' | 'proverb'
    text        TEXT NOT NULL,
    attribution TEXT
);
```

### plurals (24,466), derived_forms (50,191), cross_refs (10,453)

All follow the same pattern: `entry_id FK`, `idx`, `text`.

### provenance (552,601 rows) — source tracking

```sql
CREATE TABLE provenance (
    entry_id          INTEGER PRIMARY KEY REFERENCES entries(id) ON DELETE CASCADE,
    page_number       TEXT,
    page_file         TEXT,          -- e.g. 'page_0031'
    entry_index       INTEGER,
    volume            TEXT,
    hawramani_post_id INTEGER,
    hawramani_slug    TEXT,
    source_uri        TEXT           -- e.g. 'https://arabiclexicon.hawramani.com/'
);
```

### FTS5 Virtual Tables

```sql
-- Arabic full-text search
CREATE VIRTUAL TABLE entries_fts USING fts5(
    headword, headword_bare, headword_norm, root, definitions_text,
    content=entries, content_rowid=id,
    tokenize='unicode61 remove_diacritics 2'
);

-- Multilingual search (ARABTERM translations)
CREATE VIRTUAL TABLE entries_translations_fts USING fts5(
    translation_en, translation_fr, domain,
    content=entries, content_rowid=id,
    tokenize='unicode61 remove_diacritics 2'
);
```

---

## د. كفاءة الاستعلام — Query Efficiency (CRITICAL)

**Each query costs a tool-call turn. Minimize total queries by batching aggressively.**

### القواعد الذهبية — Golden Rules

1. **Batch ALL lemmas in one headword query.** Never query lemmas one-by-one.
   Include both forms (bare + ال) for every lemma in a single `WHERE headword_norm IN (...)`:
   ```sql
   -- 3 lemmas = 1 query (not 3)
   WHERE headword_norm IN ('ترامواي','الترامواي','تلفريك','التلفريك','قطار هوائي','القطار الهوائي')
   ```

2. **English bridge = ONE query with ALL English lemmas.** Combine all OEWN lemmas:
   ```sql
   WHERE entries_translations_fts MATCH 'translation_en:"tramway" OR translation_en:"tram" OR translation_en:"cable car" OR translation_en:"ropeway" OR translation_en:"aerial tramway"'
   ```
   Never run a second English bridge query. If you need more English terms, you should have included them in the first query.

3. **Arabic FTS = at most 2 queries.** One broad keyword search from the definition, one for compound candidate terms. Never run 4-5 overlapping FTS queries.

4. **Never re-query the same lemma.** Note the `entry_id` values from your first headword query. Use `WHERE entry_id IN (id1, id2, ...)` for enrichment — never re-query by headword_norm for data you already retrieved.

5. **Batch Step 0.5 candidate validation** into one or two headword queries:
   ```sql
   -- Validate ALL generated candidates at once
   WHERE headword_norm IN ('candidate1','الcandidate1','candidate2','الcandidate2',...)
   ```

6. **Enrich by entry_id, not by headword.** For examples, definitions, plurals — always use entry_id from earlier results:
   ```sql
   SELECT ... FROM examples WHERE entry_id IN (857316, 68214, 362484) ...
   ```

### Target query budget per synset

| Phase | Queries | Purpose |
|---|---|---|
| Step 0: Evidence | 1 | Batch headword lookup for ALL lemmas |
| Step 0: Evidence | 1 | Examples + enrichment by entry_id |
| Step 0: Evidence | 0-1 | Root inference (only if needed, already in headword results) |
| Step 0.5: Generation | 1 | English bridge (ALL English lemmas at once) |
| Step 0.5: Generation | 1 | Arabic FTS keyword search (broad) |
| Step 0.5: Validation | 1 | Batch headword lookup for ALL candidates |
| Step 1: Validation | 0-1 | Follow-up if specific evidence needed |
| Step 5: Enrichment | 0-1 | Examples/plurals by entry_id |
| **Total** | **~6-8** | **(not 20+)** |

---

## ه. الاستعلامات المُثبتة — Proven Query Patterns

### مجموعة الأعمدة المشتركة — Shared Column Set

For brevity, templates below use `{ENTRY_COLS}` to mean:

```sql
    e.id AS entry_id, e.dictionary_id,
    e.headword, e.headword_bare, e.headword_norm,
    e.root, e.root_source, e.pos, e.form,
    e.definitions_text, e.translation_en, e.translation_fr, e.domain,
    d.key AS dict_key, d.name_ar AS dict_name_ar, d.name_en AS dict_name_en,
    d.source_type AS dict_source_type, d.period AS dict_period,
    d.author AS dict_author, d.death_year AS dict_death_year
```

> **Tip:** Select fewer columns when you only need specific fields (e.g., `e.headword, e.definitions_text, d.name_ar`). This reduces output size.

---

### ١. المطابقة الدقيقة — Batch Headword Lookup (ALL lemmas at once)

**الغرض:** Find all dictionary entries matching ANY synset lemma. **This is your first and most important query — include ALL lemmas.**

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (
    '<lemma1_norm>', 'ال<lemma1_norm>',
    '<lemma2_norm>', 'ال<lemma2_norm>',
    '<lemma3_norm>', 'ال<lemma3_norm>'
)
ORDER BY e.headword_norm, d.source_type, d.death_year ASC NULLS LAST, d.name_en;
```

**Example (3 lemmas = 1 query):**
```bash
sqlite3 -json "DB_PATH" "SELECT e.id AS entry_id, e.headword, e.headword_norm, e.root, e.root_source, e.definitions_text, e.translation_en, e.domain, d.name_ar, d.source_type, d.period FROM entries e JOIN dictionaries d ON e.dictionary_id=d.id WHERE e.headword_norm IN ('ترامواي','الترامواي','تلفريك','التلفريك','قطار هوائي','القطار الهوائي') ORDER BY e.headword_norm, d.source_type, d.death_year ASC NULLS LAST;"
```

**For multiword lemmas** that return empty: also query component words, but batch them together in ONE follow-up query:
```sql
WHERE e.headword_norm IN ('قطار','القطار','هوائي','الهوائي')
```

**Note entry_ids** from this query — you will reuse them for enrichment. Never re-query the same lemma by headword_norm.

---

### ٢. استنتاج الجذر — Root Inference (from headword results)

**الغرض:** Find the trilateral root for a lemma, prioritizing more reliable sources.

**First:** Check the `root` and `root_source` columns already returned in Query ١. Often sufficient.

**Only if root is NULL in all results:**
```sql
SELECT DISTINCT e.root, e.root_source
FROM entries e
WHERE e.headword_norm IN ('<norm>', 'ال<norm>')
  AND e.root IS NOT NULL
ORDER BY CASE e.root_source
    WHEN 'ocr'  THEN 1
    WHEN 'lane' THEN 2
    WHEN 'camel' THEN 3
    ELSE 4
END;
```

**Root source priority:** ocr (most accurate) > lane > camel > NULL. The first row has the most reliable root.

---

### ٣. عائلة الجذر — Root Family (per-root)

**الغرض:** Find sibling derivations sharing the same root — useful for lemma generation and validation.

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE (e.root = '<root>' OR e.headword_norm = '<root>')
  AND e.id NOT IN (<already_seen_ids>)
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en
LIMIT 200;
```

**Important:** The `OR e.headword_norm = '<root>'` clause catches Hawramani entries where the headword IS the root form but the `root` column is NULL. Use `-1` if you have no IDs to exclude: `AND e.id NOT IN (-1)`.

---

### ٤. الشواهد والإثراء بالمعرّف — Examples & Enrichment (by entry_id)

**الغرض:** Retrieve examples, definitions, plurals for entries you already found.

**Always use entry_id from earlier queries — never re-query by headword_norm.**

```sql
SELECT ex.entry_id, e.headword, d.name_ar,
       ex.type, ex.text AS example_text, ex.attribution
FROM examples ex
JOIN entries e ON ex.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE ex.entry_id IN (<entry_ids_from_query_1>)
ORDER BY CASE ex.type
    WHEN 'quran'  THEN 1
    WHEN 'hadith' THEN 2
    WHEN 'poetry' THEN 3
    WHEN 'prose'  THEN 4
    WHEN 'usage'  THEN 5
    ELSE 6
END, ex.idx;
```

---

### ٥. البحث العكسي — Reverse Lookup / FTS (per-lemma)

**الغرض:** Find entries that MENTION this lemma in their headword or definitions (synonym chains, cross-references).

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH '{headword headword_bare definitions_text}:"<bare_lemma>"'
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 100
)
AND e.headword_norm NOT IN ('<norm>', 'ال<norm>')
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;
```

**FTS5 notes:**
- Quote the search term with double quotes inside the MATCH: `"ملاذ"`
- Column filter `{headword headword_bare definitions_text}:` restricts search to those 3 columns
- BM25 weights: headword(10), headword_bare(5), headword_norm(5), root(3), definitions_text(1)

---

### ٦. البحث بالكلمات المفتاحية — FTS Keyword Search (per-synset, ONE query)

**الغرض:** Search by Arabic keywords from the synset's definition to find related entries.

**Combine all keywords into ONE query. Include both single words and compound terms:**

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH '"<keyword1>" OR "<keyword2>" OR "<compound term>" OR "<keyword3>"'
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 50
)
AND e.id NOT IN (<already_seen_ids>)
ORDER BY d.source_type, d.name_en;
```

**Tip:** Extract meaningful content words from the Arabic definition (skip stop words like من، في، على، إلى، عن، هو، هي، هذا، ما، لا، أن، كل). Normalize them (strip diacritics, أإآ→ا, ى→ي).

---

### ٧. الجسر الإنجليزي — English Bridge (per-synset, ONE query)

**الغرض:** Use English lemmas from OEWN to find ARABTERM entries with Arabic translations.

**Include ALL English lemmas and their synonyms in ONE query:**

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_translations_fts
    WHERE entries_translations_fts MATCH 'translation_en:"<en_lemma1>" OR translation_en:"<en_lemma2>" OR translation_en:"<en_lemma3>" OR translation_en:"<en_lemma4>"'
    ORDER BY bm25(entries_translations_fts, 5.0, 3.0, 1.0)
    LIMIT 50
)
AND e.id NOT IN (<already_seen_ids>)
ORDER BY d.source_type, d.name_en;
```

**Include related English terms too** (not just OEWN lemmas). E.g., for "cable car" synset, also add "gondola", "ropeway", "aerial", "telpher" in the same query.

---

### ٨. التصفية حسب الصنف — POS-filtered Root Family (per-synset)

**الغرض:** Restrict root family to entries matching the synset's POS.

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = '<root>'
  AND e.pos = '<pos>'
ORDER BY d.source_type, d.name_en;
```

POS values: `noun`, `verb`, `adj`, `particle`, `proper_noun`, `phrase`.

---

### ٩. التصفية حسب المجال — Domain-filtered ARABTERM (per-synset)

**الغرض:** Find same-domain technical terms in ARABTERM.

```sql
SELECT {ENTRY_COLS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.domain = '<domain>'
  AND e.headword_norm != '<lemma_norm>'
  AND d.source_type = 'arabterm'
ORDER BY d.name_en
LIMIT 30;
```

---

## و. استعلامات الإثراء — Enrichment Queries

**After finding entries, use their `entry_id` values for enrichment. Batch all IDs in ONE query per child table.**

### التعريفات المُفصّلة — Definitions (per-sense)

```sql
SELECT entry_id, sense_index, text, is_raw
FROM definitions
WHERE entry_id IN (<ids>)
ORDER BY entry_id, sense_index;
```

### الشواهد — Examples

```sql
SELECT entry_id, idx, type, text, attribution
FROM examples
WHERE entry_id IN (<ids>)
ORDER BY entry_id, idx;
```

### الجموع — Plurals

```sql
SELECT entry_id, idx, text FROM plurals WHERE entry_id IN (<ids>) ORDER BY entry_id, idx;
```

### المشتقات — Derived Forms

```sql
SELECT entry_id, idx, text FROM derived_forms WHERE entry_id IN (<ids>) ORDER BY entry_id, idx;
```

### الإحالات — Cross References

```sql
SELECT entry_id, idx, text FROM cross_refs WHERE entry_id IN (<ids>) ORDER BY entry_id, idx;
```

### المصدر — Provenance

```sql
SELECT entry_id, page_number, page_file, volume, source_uri
FROM provenance WHERE entry_id IN (<ids>);
```

### استعلام إثراء مُدمج — Combined enrichment (recommended)

**Fetch examples + definitions + plurals in ONE compound query** to save turns:

```bash
sqlite3 -json "DB_PATH" "
SELECT 'def' AS _table, entry_id, sense_index AS idx, text, NULL AS type, NULL AS attribution FROM definitions WHERE entry_id IN (<ids>)
UNION ALL
SELECT 'ex' AS _table, entry_id, idx, text, type, attribution FROM examples WHERE entry_id IN (<ids>)
UNION ALL
SELECT 'pl' AS _table, entry_id, idx, text, NULL, NULL FROM plurals WHERE entry_id IN (<ids>)
ORDER BY entry_id, _table, idx;
"
```

---

## ز. إحصائيات سريعة — Quick Stats

```sql
SELECT
    (SELECT COUNT(*) FROM entries) AS total_entries,
    (SELECT COUNT(*) FROM dictionaries) AS total_dictionaries,
    (SELECT COUNT(*) FROM definitions) AS total_definitions,
    (SELECT COUNT(*) FROM examples) AS total_examples;
```

---

## ح. الأدلة المُسبقة الجلب — Pre-fetched Evidence

If `evidence.json` exists in the synset's prepared directory, it contains pre-computed
results for the three deterministic queries: headword lookup (Pattern ١), combined
enrichment (section و), and English bridge (Pattern ٧).

**Read `evidence.json` first — it replaces your first 3 queries.**

### الهيكل — Structure

```json
{
  "headword_entries": [...],    // Pattern ١ results (all lemmas + ال-forms)
  "enrichment": [...],          // Combined definitions + examples + plurals by entry_id
  "english_bridge": [...],      // Pattern ٧ results (all OEWN English lemmas)
  "query_meta": {
    "lemma_terms": ["كيان", "الكيان", ...],
    "english_terms": ["entity", "being", ...],
    "entry_ids": [766454, 534694, ...],
    "timestamp": "2026-03-12T10:00:00Z"
  }
}
```

### الاستعلامات المتبقية — Remaining Queries

When `evidence.json` is available, you still need to run yourself:

| # | Query | Purpose |
|---|-------|---------|
| 1 | Pattern ٦ (Arabic FTS keyword) | You choose the keywords from the definition |
| 2 | Pattern ١ (candidate validation) | Validate Step 0.5 candidates by headword |

**Target: ~2-3 queries per synset** when evidence.json is available (down from 6-8).

### الرجوع — Fallback

If `evidence.json` does NOT exist, run the standard query sequence as documented above:
Pattern ١ → enrichment → Pattern ٧ → Pattern ٦ → candidate validation.
