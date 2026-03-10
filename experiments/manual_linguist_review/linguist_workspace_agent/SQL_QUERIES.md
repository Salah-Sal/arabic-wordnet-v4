# SQL Queries — RLM Evidence Collection Agent

All queries execute against `arabic_dict.db` (760,660 entries, 107 dictionaries).
The agent calls tool functions (defined in `agent_tools.py`) which delegate to
`DictDB` methods (defined in `collect_evidence.py`) that run these SQL templates.

---

## Shared Column Set

Most entry queries select the same column set via `_ENTRY_COLUMNS`:

```sql
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
```

---

## Per-Lemma Queries (run once per lemma in synset)

### Step 1 — Exact Headword Lookup (ال-aware)

**Tool:** `lookup_headword(lemma)` → **Method:** `DictDB.step1_headword(base, al_form)`

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;
```

**Parameters:** `?1` = normalized lemma (e.g., `استشار`), `?2` = ال-variant (e.g., `الاستشار`)

For **multiword lemmas**, the tool also runs Step 1 once per component word.

---

### Step 2 — Structured Definitions with Senses

**Tool:** `lookup_definitions(lemma)` → **Method:** `DictDB.step2_definitions(base, al_form)`

```sql
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
```

**Parameters:** same as Step 1

---

### Step 3a — Root Inference

**Tool:** `lookup_root_family(lemma, excluded_ids)` → **Method:** `DictDB.step3a_roots(base, al_form)`

```sql
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
```

**Parameters:** same as Step 1
**Root sources ranked:** OCR (from original dictionary pages) > Lane's Lexicon > CAMeL morphological analyzer

---

### Step 3b — Root Family Lookup (per root)

**Tool:** `lookup_root_family(lemma, excluded_ids)` → **Method:** `DictDB.step3b_root_family(root, excluded_ids)`

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE (e.root = ?1 OR e.headword_norm = ?1)
  AND e.id NOT IN (?,?,?,...) -- dynamic excluded IDs
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en
LIMIT 200;
```

**Parameters:** `?1` = root string (e.g., `شور`), remaining `?` = entry IDs already seen (from steps 1-2)

---

### Step 6 — Usage Examples

**Tool:** `lookup_examples(lemma)` → **Method:** `DictDB.step6_examples(base, al_form)`

```sql
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
```

**Parameters:** same as Step 1
**Ordering:** Quran > Hadith > Poetry > Prose > Usage (classical sources prioritized)

---

### Step 7 — Chronological Ordering

**Tool:** (computed in-agent by sorting Step 1 entries by `dict_death_year`)
**Method:** `DictDB.step7_chronological(base, al_form)` (used by automated pipeline)

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN (?1, ?2)
ORDER BY d.death_year ASC NULLS LAST;
```

**Parameters:** same as Step 1
**Note:** In the RLM agent, Step 7 is computed by sorting Step 1 results in Python, not a separate query.

---

### Step 8 — Reverse Lookup (FTS)

**Tool:** `reverse_lookup(lemma)` → **Method:** `DictDB.step8_reverse_lookup(lemma_bare, base, al_form)`

```sql
SELECT {_ENTRY_COLUMNS}
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
```

**Parameters:** `?1` = bare lemma (no diacritics), `?2` = base form, `?3` = ال-variant
**FTS5 column weights (bm25):** headword=10, headword_bare=5, definitions_text=5, translation_en=3, domain=1
**Logic:** Find entries that *mention* this lemma in their text but have a *different* headword.

---

## Per-Synset Queries (run once per synset)

### Step 4 — Arabic FTS Keyword Search

**Tool:** `fts_search(query, "arabic", excluded_ids)` → **Method:** `DictDB.step4_fts_keyword(fts_expr, excluded_ids)`

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_fts
    WHERE entries_fts MATCH ?1
    ORDER BY bm25(entries_fts, 10.0, 5.0, 5.0, 3.0, 1.0)
    LIMIT 50
)
AND e.id NOT IN (?,?,?,...) -- dynamic excluded IDs
ORDER BY d.source_type, d.name_en;
```

**Parameters:** `?1` = FTS5 expression (e.g., `ذهب OR لرؤية OR شخص OR لاسباب OR مهنية OR تجارية`), remaining `?` = all entry IDs seen so far
**Keywords extracted from:** synset's Arabic definition via `extract_keywords()`

---

### Step 5 — English Bridge (Translation FTS)

**Tool:** `fts_search(term, "english", excluded_ids)` → **Method:** `DictDB.step5_english_bridge(english_term, excluded_ids)`

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.id IN (
    SELECT rowid FROM entries_translations_fts
    WHERE entries_translations_fts MATCH 'translation_en:' || ?1
    ORDER BY bm25(entries_translations_fts, 5.0, 3.0, 1.0)
    LIMIT 30
)
AND e.id NOT IN (?,?,?,...) -- dynamic excluded IDs
ORDER BY d.source_type, d.name_en;
```

**Parameters:** `?1` = English term (e.g., `see`), remaining `?` = all entry IDs seen so far
**FTS table:** `entries_translations_fts` (separate from `entries_fts`)
**Source:** English lemmas from OEWN (Open English WordNet) via ILI mapping

---

### Step 9a — POS Filtering (automated pipeline only)

**Method:** `DictDB.step9a_pos_filter(root, pos)`

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = ?
  AND e.pos = ?
ORDER BY d.source_type, d.name_en;
```

**Parameters:** `?1` = root, `?2` = POS (noun/verb/adj/adv)

---

### Step 9b — Domain Filtering (automated pipeline only)

**Method:** `DictDB.step9b_domain_filter(domain, headword_norm)`

```sql
SELECT {_ENTRY_COLUMNS}
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.domain = ?
  AND e.headword_norm != ?
  AND d.source_type = 'arabterm'
ORDER BY d.name_en
LIMIT 30;
```

**Parameters:** `?1` = domain string (e.g., `Hygienics and Human Body`), `?2` = headword to exclude

---

## Enrichment Queries (batch, per entry set)

After each step returns entries, `DictDB.enrich_entries()` runs **6 batch queries** to populate child tables:

### Definitions

```sql
SELECT entry_id, sense_index, text, is_raw
FROM definitions
WHERE entry_id IN (?,?,?,...)
ORDER BY entry_id, sense_index;
```

### Examples

```sql
SELECT entry_id, idx, type, text, attribution
FROM examples
WHERE entry_id IN (?,?,?,...)
ORDER BY entry_id, idx;
```

### Plurals

```sql
SELECT entry_id, idx, text
FROM plurals
WHERE entry_id IN (?,?,?,...)
ORDER BY entry_id, idx;
```

### Derived Forms

```sql
SELECT entry_id, idx, text
FROM derived_forms
WHERE entry_id IN (?,?,?,...)
ORDER BY entry_id, idx;
```

### Cross References

```sql
SELECT entry_id, idx, text
FROM cross_refs
WHERE entry_id IN (?,?,?,...)
ORDER BY entry_id, idx;
```

### Provenance

```sql
SELECT entry_id, page_number, page_file, entry_index, volume,
       hawramani_post_id, hawramani_slug, source_uri
FROM provenance
WHERE entry_id IN (?,?,?,...)
```

---

## Utility Queries

### Database Stats

**Tool:** `get_db_stats()` → **Method:** `DictDB.get_stats()`

```sql
SELECT
    (SELECT COUNT(*) FROM entries) AS total_entries,
    (SELECT COUNT(*) FROM dictionaries) AS total_dictionaries;
```

---

## FTS5 Virtual Tables

The database has two FTS5 virtual tables used for full-text search:

### `entries_fts`
Indexes: `headword`, `headword_bare`, `definitions_text`, `translation_en`, `domain`
Used by: Steps 4, 8

### `entries_translations_fts`
Indexes: `translation_en`, `translation_fr`, `domain`
Used by: Step 5

---

## Query Execution Flow for a Single Synset

For a synset with N lemmas, the agent executes:

| Phase | Queries | Count |
|-------|---------|-------|
| `get_db_stats()` | 1 stats query | 1 |
| Per lemma (×N) | Step 1 + enrich (7 queries) | N × 7 |
| Per lemma (×N) | Step 2 | N × 1 |
| Per lemma (×N) | Step 3a + Step 3b per root + enrich | N × (1 + R × 7) where R = roots found |
| Per lemma (×N) | Step 6 | N × 1 |
| Per lemma (×N) | Step 8 + enrich | N × 7 |
| Per synset | Step 4 (FTS arabic) + enrich | 7 |
| Per synset | Step 5 (FTS english, per EN lemma) + enrich | E × 1 + 6 |

**Example:** For `awn4-02493953-v` (3 lemmas, ~3 roots, 1 EN lemma):
- ~3 × (7 + 1 + 1 + 3×7 + 1 + 7) + 7 + 7 = **~120 SQL queries**

---

## PRAGMA Settings

```sql
PRAGMA cache_size = -64000;   -- 64 MB page cache
PRAGMA mmap_size = 3000000000; -- 3 GB memory-mapped I/O
```

Connection opened as **read-only**: `file:{path}?mode=ro`
