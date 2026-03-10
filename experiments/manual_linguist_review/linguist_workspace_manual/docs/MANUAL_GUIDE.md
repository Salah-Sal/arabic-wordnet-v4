# دليل الجمع اليدوي — Manual Evidence Collection Guide

> هذا الدليل يرشدك خطوة بخطوة لجمع الشواهد المعجمية يدوياً باستخدام `sqlite3`.
> This guide walks you through collecting dictionary evidence manually using `sqlite3`.

---

## ٠. سير العمل — Workflow Overview

```
١. أنشئ الهيكل          python3 tools/scaffold_synset.py awn4-XXXXX-n
                         → output/evidence/awn4-XXXXX-n.scaffold.yaml

٢. افتح القاعدة          sqlite3 "file:data/arabic_dict.db?mode=ro"

٣. نفّذ الاستعلامات      انسخ من TODO في الهيكل أو من هذا الدليل
                         Run queries from scaffold TODOs or this guide

٤. املأ الهيكل            paste results into the scaffold YAML

٥. أعد التسمية           mv awn4-XXXXX-n.scaffold.yaml awn4-XXXXX-n.evidence.yaml
```

---

## ١. إعداد sqlite3 — Setup

```bash
sqlite3 "file:data/arabic_dict.db?mode=ro"
```

ثم اضبط التنسيق — then set up formatting:

```sql
.mode column
.headers on
.width 8 15 20 10 60
PRAGMA cache_size = -64000;      -- 64 MB cache
PRAGMA mmap_size = 3000000000;   -- memory-mapped IO (faster)
```

> **نصيحة — Tip:** استخدم `.output file.txt` لحفظ النتائج في ملف، ثم `.output stdout` للعودة.
> Use `.output file.txt` to save results to a file, then `.output stdout` to return to screen.

---

## ٢. الاصطلاحات — Placeholder Conventions

| العنصر النائب | الوصف | مثال |
|-------------|-------|------|
| `{LEMMA_NORM}` | اللمّة المطبّعة (بلا تشكيل، أإآ→ا، ى→ي) | `ملاذ` |
| `{AL_VARIANT}` | `'ال' + {LEMMA_NORM}` | `الملاذ` |
| `{LEMMA_BARE}` | بلا تشكيل فقط | `ملاذ` |
| `{ROOT}` | الجذر الثلاثي/الرباعي | `لوذ` |
| `{EXCLUDED_IDS}` | `entry_id` مفصولة بفواصل من الخطوات السابقة | `42,78,156` |

### كيف تطبّع؟ — How to normalize?

| الأصل | المطبّع | القاعدة |
|-------|---------|---------|
| `مَلَاذ` | `ملاذ` | إزالة التشكيل |
| `إنسان` / `أنسان` | `انسان` | أإآ → ا |
| `مستشفى` | `مستشفي` | ى → ي |
| `كتـــاب` | `كتاب` | حذف التطويل |

> **أو** استخدم `scaffold_synset.py` — يحسب `lemma_norm` و `al_variants` تلقائياً.

---

## ٣. تتبع المعرّفات المستبعدة — Tracking Excluded IDs

بعد كل خطوة تسترجع مداخل، أضف `entry_id` إلى مجموعة الاستبعاد:

After each step that returns entries, add entry_ids to the exclusion set:

```
الخطوة ١ → all_ids = {42, 78, 156}
الخطوة ٣ → all_ids = {42, 78, 156, 200, 201, ...}
الخطوة ٨ → all_ids = {42, 78, 156, 200, 201, ..., 500, ...}
الخطوة ٤ → WHERE id NOT IN (42,78,156,200,201,...,500,...)
الخطوة ٥ → WHERE id NOT IN (...)  -- same exclusion set + step 4 ids
```

---

## ٤. الخطوات — The 9 Steps

### الخطوة ١: المطابقة الدقيقة — Step 1: Exact Headword Lookup (ال-aware)

> **نطاق:** لكل لمّة — per lemma

```sql
SELECT
    e.id AS entry_id, e.dictionary_id, e.headword, e.headword_bare,
    e.headword_norm, e.root, e.root_source, e.pos, e.form, e.is_partial,
    e.definitions_text, e.translation_en, e.translation_fr, e.domain,
    e.external_id,
    d.key AS dict_key, d.name_ar AS dict_name_ar, d.name_en AS dict_name_en,
    d.source_type AS dict_source_type, d.period AS dict_period,
    d.author AS dict_author, d.death_year AS dict_death_year
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm IN ('{LEMMA_NORM}', '{AL_VARIANT}')
ORDER BY d.source_type, d.death_year ASC NULLS LAST, d.name_en;
```

**مثال — Example:** لمّة `ملاذ`:
```sql
WHERE e.headword_norm IN ('ملاذ', 'الملاذ')
-- يسترجع 4 مداخل (لا 1 فقط!) — Returns 4 entries (not just 1!)
```

> **مهم:** ~٢٠% من المداخل (154K) تحتوي `ال` في `headword_norm`.
> بدون البحث بالصيغتين، ستفقد أغنى المداخل (خاصة من المعاجم الكلاسيكية OCR).

**للمّات متعددة الكلمات:** استعلم عن كل كلمة على حدة أيضاً.
For multiword lemmas: also query each component word separately.

---

### الخطوة ٢: التعريفات المهيكلة — Step 2: Structured Definitions

> **نطاق:** لكل لمّة — per lemma

```sql
SELECT
    e.id AS entry_id, e.headword, d.key AS dict_key,
    d.name_en AS dict_name_en, d.name_ar AS dict_name_ar,
    d.source_type AS dict_source_type, d.period AS dict_period,
    d.death_year AS dict_death_year, d.author AS dict_author,
    df.sense_index, df.text, df.is_raw
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm IN ('{LEMMA_NORM}', '{AL_VARIANT}')
ORDER BY d.death_year ASC NULLS LAST, d.name_en, df.sense_index;
```

> **نصيحة:** `sense_index` يفصل بين المعاني المتعددة. قارن مع `definitions_text` (المسطّح).

---

### الخطوة ٣: عائلة الجذر — Step 3: Root Family

> **نطاق:** لكل لمّة — per lemma

#### ٣أ: استنتاج الجذر — Root Inference

```sql
SELECT DISTINCT e.root, e.root_source, e.id AS from_entry_id
FROM entries e
WHERE e.headword_norm IN ('{LEMMA_NORM}', '{AL_VARIANT}')
  AND e.root IS NOT NULL
ORDER BY
    CASE e.root_source
        WHEN 'ocr' THEN 1
        WHEN 'lane' THEN 2
        WHEN 'camel' THEN 3
        ELSE 4
    END;
```

**مثال:** لمّة `ملاذ`:
```
root | root_source | from_entry_id
لوذ  | ocr         | 42          ← الأدق — most reliable
ملذ  | lane        | 200         ← خاطئ! Lane miscalculated
```
→ استخدم `لوذ` (الأولوية: ocr > lane > camel)

#### ٣ب: مداخل عائلة الجذر — Root Family Entries

```sql
SELECT
    e.id AS entry_id, e.headword, e.headword_norm, e.root,
    e.definitions_text, d.key AS dict_key, d.name_en, d.source_type
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE (e.root = '{ROOT}' OR e.headword_norm = '{ROOT}')
  AND e.id NOT IN ({EXCLUDED_IDS})
ORDER BY d.source_type, d.death_year ASC NULLS LAST
LIMIT 200;
```

> **مهم:** الشرط `e.headword_norm = '{ROOT}'` يلتقط مداخل Hawramani حيث العنوان = الجذر لكن `root IS NULL`.

---

### الخطوة ٦: الشواهد — Step 6: Examples

> **نطاق:** لكل لمّة — per lemma

```sql
SELECT
    e.id AS entry_id, e.headword, d.key AS dict_key, d.name_en,
    ex.type, ex.text, ex.attribution
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN examples ex ON ex.entry_id = e.id
WHERE e.headword_norm IN ('{LEMMA_NORM}', '{AL_VARIANT}')
ORDER BY
    CASE ex.type
        WHEN 'quran' THEN 1
        WHEN 'hadith' THEN 2
        WHEN 'poetry' THEN 3
        WHEN 'prose' THEN 4
        WHEN 'usage' THEN 5
        ELSE 6
    END,
    d.death_year ASC NULLS LAST;
```

---

### الخطوة ٧: الترتيب الزمني — Step 7: Chronological Ordering

> **نطاق:** لكل لمّة — per lemma

نفس الخطوة ١ لكن مرتبة بسنة الوفاة. Same as Step 1 but sorted by death_year:

```sql
-- Same SELECT as Step 1, but:
ORDER BY d.death_year ASC NULLS LAST, d.name_en;
```

---

### الخطوة ٨: البحث العكسي — Step 8: Reverse Lookup (Enhanced FTS)

> **نطاق:** لكل لمّة — per lemma

```sql
SELECT
    e.id AS entry_id, e.headword, e.headword_norm, e.root,
    e.definitions_text, d.key AS dict_key, d.name_en, d.source_type,
    bm25(entries_fts, 10, 5, 5, 3, 1) AS rank
FROM entries_fts
JOIN entries e ON entries_fts.rowid = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE entries_fts MATCH '{headword headword_bare definitions_text}:{LEMMA_BARE}'
  AND e.headword_norm NOT IN ('{LEMMA_NORM}', '{AL_VARIANT}')
ORDER BY rank
LIMIT 100;
```

> **ما يلتقطه:** معاجم مثل "المورد الحديث" تحتوي سلاسل مرادفات كعناوين:
> `"(1) ملاذ؛ ملجأ؛ مفزع"` — هذه مداخل مختلفة تذكر لمّتك.

---

### الخطوة ٤: البحث النصي الكامل — Step 4: FTS Keyword Search

> **نطاق:** لكل مجموعة — per synset

١. استخلص كلمات مفتاحية من `definition_ar` (احذف الأحرف القصيرة وكلمات التوقف)
   Extract keywords from `definition_ar` (remove short words and stopwords)

٢. ابنِ تعبير FTS — Build FTS expression:
```sql
SELECT
    e.id AS entry_id, e.headword, e.definitions_text,
    d.key AS dict_key, d.name_en,
    bm25(entries_fts) AS rank
FROM entries_fts
JOIN entries e ON entries_fts.rowid = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE entries_fts MATCH '{KEYWORD1} OR {KEYWORD2} OR {KEYWORD3}'
  AND e.id NOT IN ({EXCLUDED_IDS})
ORDER BY rank
LIMIT 50;
```

> **كلمات التوقف العربية** (احذفها): من، في، على، إلى، عن، مع، هو، هي، هذا، هذه، ذلك، ما، لا، أن، إن، كان، كانت، يكون، قد، بل، أو، ثم، حتى، لم، لن، كل، بعض، غير، بين، عند، أي، ليس...

---

### الخطوة ٥: الجسر الإنجليزي — Step 5: English Bridge (ARABTERM)

> **نطاق:** لكل مجموعة — per synset
> يتطلب: رابط ILI في المجموعة الترادفية — Requires ILI link

```sql
SELECT
    e.id AS entry_id, e.headword, e.translation_en, e.translation_fr,
    e.domain, d.key AS dict_key, d.name_en,
    bm25(entries_translations_fts, 5, 3, 1) AS rank
FROM entries_translations_fts
JOIN entries e ON entries_translations_fts.rowid = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE entries_translations_fts MATCH 'translation_en:{ENGLISH_TERM}'
  AND e.id NOT IN ({EXCLUDED_IDS})
ORDER BY rank
LIMIT 30;
```

كرّر لكل مصطلح إنجليزي من `oewn.lemmas_en`.
Repeat for each English term from `oewn.lemmas_en`.

---

### الخطوة ٩: التصفية التخصصية — Step 9: Specialized Filtering

> **نطاق:** لكل مجموعة — per synset (اختياري — optional)

#### ٩أ: تصفية بنوع الكلمة — POS Filtering

```sql
SELECT e.id, e.headword, e.pos, e.definitions_text, d.name_en
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = '{ROOT}' AND e.pos = '{POS}'
ORDER BY d.death_year ASC NULLS LAST;
```

#### ٩ب: تصفية بالمجال — Domain Filtering (ARABTERM)

```sql
SELECT e.id, e.headword, e.domain, e.translation_en, d.name_en
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.domain = '{DOMAIN}'
  AND e.headword_norm != '{LEMMA_NORM}'
  AND d.source_type = 'arabterm'
LIMIT 30;
```

---

## ٥. الإثراء — Enrichment

بعد كل خطوة تسترجع مداخل، أحضر الجداول الفرعية بدفعة واحدة:

After each step that returns entries, fetch child tables in one batch:

```sql
-- استبدل {ENTRY_IDS} بقائمة المعرّفات: 42,78,156,...
-- Replace {ENTRY_IDS} with comma-separated entry IDs

SELECT * FROM definitions   WHERE entry_id IN ({ENTRY_IDS}) ORDER BY entry_id, sense_index;
SELECT * FROM examples      WHERE entry_id IN ({ENTRY_IDS}) ORDER BY entry_id, idx;
SELECT * FROM plurals       WHERE entry_id IN ({ENTRY_IDS}) ORDER BY entry_id, idx;
SELECT * FROM derived_forms WHERE entry_id IN ({ENTRY_IDS}) ORDER BY entry_id, idx;
SELECT * FROM cross_refs    WHERE entry_id IN ({ENTRY_IDS}) ORDER BY entry_id, idx;
SELECT * FROM provenance    WHERE entry_id IN ({ENTRY_IDS});
```

---

## ٦. تجميع YAML — Assembling the YAML

١. ابدأ من الهيكل: `output/evidence/{synset_id}.scaffold.yaml`
   Start from scaffold

٢. لكل خطوة: الصق `sql_template`، `query_params`، `result_count`، وقائمة المداخل
   For each step: paste sql_template, query_params, result_count, and entries list

٣. كل مدخل يتبع شكل `_entry_object` (انظر `docs/EVIDENCE_SCHEMA.yaml`)
   Each entry follows the `_entry_object` shape

٤. أعد التسمية: `{synset_id}.scaffold.yaml` → `{synset_id}.evidence.yaml`

> **انظر:** `docs/EXAMPLE_ARTIFACT.yaml` لمثال كامل على `awn4-05162506-n`.

---

## ٧. ورقة مرجعية — Quick Reference

### بنية FTS5 — FTS5 Syntax

| النمط | المعنى |
|-------|--------|
| `word` | بحث بسيط |
| `word1 OR word2` | أي من الكلمتين |
| `word1 AND word2` | كلتا الكلمتين |
| `word1 NOT word2` | الأولى بدون الثانية |
| `word*` | بادئة |
| `{col1 col2}:word` | بحث في أعمدة محددة |
| `"exact phrase"` | عبارة حرفية |

### قواعد التطبيع — Normalization Rules

| الأصل | النتيجة | القاعدة |
|-------|---------|---------|
| حركات (فتحة، ضمة، ...) | تُزال | `strip_diacritics` |
| أ / إ / آ | ا | توحيد الهمزة |
| ى | ي | توحيد الألف المقصورة |
| ـ (تطويل) | يُزال | |

### أولوية الجذور — Root Priority

`ocr` (1) > `lane` (2) > `camel` (3)
