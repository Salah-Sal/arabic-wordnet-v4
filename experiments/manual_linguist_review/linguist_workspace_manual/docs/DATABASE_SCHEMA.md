# هيكل قاعدة البيانات — Database Schema Reference
# `arabic_dict.db` — 760,660 مدخلاً من 107 معجماً

---

## نظرة عامة — Overview

```
dictionaries (107 معجماً — 107 dictionaries)
    └── entries (760,660 مدخلاً — 760,660 entries)
            ├── definitions  (614,227 تعريفاً)
            ├── examples     (86,031 شاهداً)
            ├── plurals      (24,466 جمعاً)
            ├── derived_forms (50,191 مشتقاً)
            ├── cross_refs   (10,453 إحالة)
            └── provenance   (552,601 مصدراً)

entries_fts              (FTS5: Arabic text search)
entries_translations_fts (FTS5: English/French search)
```

---

## المصادر الثلاثة — Three Data Sources

| المصدر — Source | المعاجم | المداخل | POS؟ | أمثلة؟ | جذور؟ | ترجمات؟ |
|-----------------|:-------:|--------:|:----:|:------:|:-----:|:-------:|
| **OCR** (استخلاص بصري) | 5 | 109,769 | نعم | نعم | نعم (`root_source='ocr'`) | لا |
| **Hawramani** (تصدير رسمي) | 51 | 233,465 | جزئي | جزئي | جزئي — كثيراً `root=NULL` | لا |
| **ARABTERM** (مصطلحات تقنية) | 51 | 417,426 | لا | لا | جزئي (`root_source='lane'`) | نعم (EN/FR) |

### خصوصيات كل مصدر — Source-Specific Notes

- **OCR**: المعاجم الأكثر موثوقية للجذور. `root_source='ocr'` دائماً الأدق.
  OCR dictionaries have the most reliable root assignments.

- **Hawramani**: نمط "العنوان كجذر" — كثير من المداخل `root=NULL` لكن `headword_norm` هو الجذر.
  Many entries have `root=NULL` but the headword IS the root form.
  Query pattern: `WHERE (e.root = ? OR e.headword_norm = ?)`

- **ARABTERM**: جذور من Lane (`root_source='lane'`) قد تكون خاطئة أحياناً.
  Lane roots on ARABTERM can be incorrect (e.g., "ملذ" instead of correct "لوذ" for ملاذ).

---

## الجداول — Tables

### `dictionaries` — فهرس المعاجم

| العمود | النوع | الوصف | مثال |
|--------|-------|-------|------|
| `id` | INTEGER PK | معرّف فريد | `1` |
| `key` | TEXT UNIQUE | مفتاح المعجم | `"waseet"`, `"haw_lisan"`, `"at_UN_terms"` |
| `name_ar` | TEXT | اسم عربي | `"المعجم الوسيط"` |
| `name_en` | TEXT | اسم إنجليزي | `"Al-Waseet"` |
| `source_type` | TEXT | نوع المصدر | `"ocr"` \| `"hawramani"` \| `"arabterm"` |
| `group_key` | TEXT | مجموعة | `"academy"`, `"arabterm_UN"` |
| `period` | TEXT | الفترة | `"classical"` \| `"modern"` |
| `author` | TEXT | المؤلف | `"مجمع اللغة العربية"` |
| `death_year` | INTEGER | وفاة المؤلف (ميلادي) | `1414` (= ابن منظور) |
| `metadata` | TEXT | بيانات إضافية JSON | `"{}"` |

### `entries` — المداخل المعجمية

| العمود | النوع | الوصف | مثال |
|--------|-------|-------|------|
| `id` | INTEGER PK | معرّف فريد | `42` |
| `dictionary_id` | INTEGER FK | ← `dictionaries.id` | `1` |
| `headword` | TEXT | بالتشكيل كما في المعجم | `"المَلَاذُ"` |
| `headword_bare` | TEXT | بلا تشكيل | `"الملاذ"` |
| `headword_norm` | TEXT | مطبّع بالكامل | `"الملاذ"` |
| `root` | TEXT | الجذر الثلاثي/الرباعي | `"لوذ"` أو `NULL` |
| `root_source` | TEXT | مصدر الجذر | `"ocr"` \| `"lane"` \| `"camel"` \| `NULL` |
| `pos` | TEXT | نوع الكلمة | `"noun"`, `"verb"`, `"adj"`, `"proper_noun"` |
| `form` | TEXT | الوزن الصرفي | `"I"` إلى `"X"`, `"Q"` (رباعي), `NULL` |
| `is_partial` | INTEGER | هل المدخل ناقص | `0` أو `1` |
| `definitions_text` | TEXT | النص الكامل (مسطّح) | `"ما يُلاذ به ويُحتمى..."` |
| `translation_en` | TEXT | ترجمة إنجليزية (ARABTERM) | `"refuge; shelter"` |
| `translation_fr` | TEXT | ترجمة فرنسية (ARABTERM) | `"refuge; abri"` |
| `domain` | TEXT | المجال (ARABTERM) | `"law"`, `"medicine"` |
| `external_id` | TEXT UNIQUE | مفتاح إزالة التكرار | `"ocr:waseet:p123:0"` |

#### مستويات تطبيع العنوان — Headword Normalization Levels

| المستوى | العمود | التحويلات | الاستخدام |
|---------|--------|----------|-----------|
| **أصلي** | `headword` | لا شيء — كما في المعجم | العرض |
| **بلا تشكيل** | `headword_bare` | إزالة الحركات فقط | المطابقة الدقيقة |
| **مطبّع** | `headword_norm` | + أإآ→ا + ى→ي + حذف التطويل | **البحث** ← استخدم هذا |

> **مهم:** استخدم دائماً `headword_norm` في استعلامات البحث. المطابقة ال-aware:
> `WHERE headword_norm IN ('ملاذ', 'الملاذ')`

#### أولوية الجذور — Root Priority

عند وجود أكثر من مصدر جذر لنفس اللمّة:

| الأولوية | `root_source` | السبب |
|---------|---------------|-------|
| **١** | `ocr` | استخلاص مباشر من المعجم — الأدق |
| **٢** | `lane` | حسابي — أحياناً خاطئ |
| **٣** | `camel` | حسابي — أحياناً خاطئ |

### `definitions` — التعريفات المهيكلة

| العمود | النوع | الوصف |
|--------|-------|-------|
| `entry_id` | INTEGER FK | ← `entries.id` |
| `sense_index` | INTEGER | رقم المعنى (من 0) |
| `text` | TEXT | نص التعريف الكامل |
| `is_raw` | INTEGER | `0` = مُحلَّل, `1` = خام |

### `examples` — الشواهد والأمثلة

| العمود | النوع | الوصف |
|--------|-------|-------|
| `entry_id` | INTEGER FK | ← `entries.id` |
| `idx` | INTEGER | ترتيب (من 0) |
| `type` | TEXT | `"quran"` \| `"hadith"` \| `"poetry"` \| `"prose"` \| `"usage"` |
| `text` | TEXT | نص الشاهد |
| `attribution` | TEXT | النسبة / المصدر |

### `plurals` — الجموع

| العمود | النوع | الوصف |
|--------|-------|-------|
| `entry_id` | INTEGER FK | ← `entries.id` |
| `idx` | INTEGER | ترتيب |
| `text` | TEXT | صيغة الجمع |

### `derived_forms` — المشتقات

| العمود | النوع | الوصف |
|--------|-------|-------|
| `entry_id` | INTEGER FK | ← `entries.id` |
| `idx` | INTEGER | ترتيب |
| `text` | TEXT | المشتق |

### `cross_refs` — الإحالات

| العمود | النوع | الوصف |
|--------|-------|-------|
| `entry_id` | INTEGER FK | ← `entries.id` |
| `idx` | INTEGER | ترتيب |
| `text` | TEXT | نص الإحالة |

### `provenance` — المصادر والصفحات

| العمود | النوع | الوصف |
|--------|-------|-------|
| `entry_id` | INTEGER PK/FK | ← `entries.id` |
| `page_number` | TEXT | رقم الصفحة |
| `page_file` | TEXT | ملف الصفحة |
| `entry_index` | INTEGER | ترتيب في الصفحة |
| `volume` | TEXT | المجلد |
| `hawramani_post_id` | INTEGER | معرّف منشور Hawramani |
| `hawramani_slug` | TEXT | الرابط المختصر |
| `source_uri` | TEXT | رابط المصدر |

---

## جداول البحث النصي — FTS5 Virtual Tables

### `entries_fts` — بحث عربي

| العمود | الوصف | الوزن (BM25) |
|--------|-------|:------------:|
| `headword` | العنوان بالتشكيل | 10 |
| `headword_bare` | بلا تشكيل | 5 |
| `headword_norm` | مطبّع | 5 |
| `root` | الجذر | 3 |
| `definitions_text` | نص التعريفات | 1 |

**المُرمِّز (Tokenizer):** `unicode61 remove_diacritics 2`

**أمثلة على MATCH:**

```sql
-- بحث بسيط
SELECT * FROM entries_fts WHERE entries_fts MATCH 'ملاذ';

-- بحث في أعمدة محددة (الخطوة ٨)
SELECT * FROM entries_fts
WHERE entries_fts MATCH '{headword headword_bare definitions_text}:ملاذ';

-- بحث متعدد الكلمات (OR)
SELECT * FROM entries_fts WHERE entries_fts MATCH 'ملاذ OR ملجأ OR معتصم';

-- بحث بالبادئة
SELECT * FROM entries_fts WHERE entries_fts MATCH 'ملا*';
```

### `entries_translations_fts` — بحث إنجليزي/فرنسي

| العمود | الوصف | الوزن (BM25) |
|--------|-------|:------------:|
| `translation_en` | ترجمة إنجليزية | 5 |
| `translation_fr` | ترجمة فرنسية | 3 |
| `domain` | المجال | 1 |

**مثال:**

```sql
-- الخطوة ٥: الجسر الإنجليزي
SELECT e.id, e.headword, e.translation_en, e.domain, d.name_en
FROM entries_translations_fts
JOIN entries e ON entries_translations_fts.rowid = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE entries_translations_fts MATCH 'translation_en:refuge'
ORDER BY bm25(entries_translations_fts, 5, 3, 1)
LIMIT 30;
```

---

## الفهارس المهمة — Key Indexes

| الفهرس | الأعمدة | الغرض |
|--------|--------|-------|
| `idx_entries_headword_norm_cover` | `headword_norm, dictionary_id, headword, headword_bare, root, root_source, pos, form` | **فهرس تغطية** — الاستعلام الرئيسي (الخطوة ١) لا يحتاج قراءة الجدول |
| `idx_entries_root` | `root` | بحث عائلة الجذر (الخطوة ٣) |
| `idx_entries_root_notnull` | `root WHERE root IS NOT NULL` | فهرس جزئي — يتجاوز المداخل بلا جذر |
| `idx_entries_headword_norm` | `headword_norm` | بحث العنوان المطبّع |
| `idx_defs_entry` | `definitions.entry_id` | ربط التعريفات بالمداخل |
| `idx_examples_entry` | `examples.entry_id` | ربط الشواهد بالمداخل |

---

## استعلامات مرجعية سريعة — Quick Reference Queries

```sql
-- فتح القاعدة للقراءة فقط
sqlite3 "file:data/arabic_dict.db?mode=ro"
.mode column
.headers on
PRAGMA cache_size = -64000;

-- عدد المداخل
SELECT COUNT(*) AS total FROM entries;

-- قائمة المعاجم مع عدد المداخل
SELECT d.key, d.name_en, d.source_type, d.period, d.death_year,
       COUNT(e.id) AS entries
FROM dictionaries d
LEFT JOIN entries e ON e.dictionary_id = d.id
GROUP BY d.id
ORDER BY d.source_type, entries DESC;

-- التحقق من وجود لمّة (ال-aware)
SELECT COUNT(*) FROM entries WHERE headword_norm IN ('ملاذ', 'الملاذ');

-- إحصائيات الجداول
SELECT 'entries' AS tbl, COUNT(*) AS n FROM entries
UNION ALL SELECT 'definitions', COUNT(*) FROM definitions
UNION ALL SELECT 'examples', COUNT(*) FROM examples
UNION ALL SELECT 'plurals', COUNT(*) FROM plurals
UNION ALL SELECT 'derived_forms', COUNT(*) FROM derived_forms
UNION ALL SELECT 'cross_refs', COUNT(*) FROM cross_refs
UNION ALL SELECT 'provenance', COUNT(*) FROM provenance;
```
