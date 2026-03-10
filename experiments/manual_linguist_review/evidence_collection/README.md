# جمع الشواهد المعجمية — Dictionary Evidence Collection
# مواصفات وحدة جمع الشواهد لمراجعة AWN4

## الغرض — Purpose

هذه الوحدة تجمع **شواهد معجمية خام** من قاعدة البيانات لكل مجموعة ترادفية في AWN4.
لا تحليل، لا أحكام، لا تقييمات — فقط بيانات.

This module collects **raw dictionary evidence** from the database for each AWN4 synset.
No analysis, no verdicts, no quality ratings — just data.

**القاعدة الذهبية — Golden Rule:**
إذا كان الحقل يتطلب حكماً بشرياً (مطابق؟ جيد؟ مرشح؟) → فهو خارج هذه الوحدة.
إذا كان الحقل ناتج استعلام SQL مباشر → فهو يخص هذه الوحدة.

If a field requires human judgment (matching? good? candidate?) → it does NOT belong here.
If a field is a direct SQL query result → it belongs here.

## المحتويات — Contents

| الملف — File | الوصف — Description |
|---|---|
| `EVIDENCE_SCHEMA.yaml` | مواصفات القطعة الشاهدية: جميع الحقول وأنواعها وقيودها — Evidence artifact schema |
| `COLLECTION_ALGORITHM.md` | الخوارزمية المحدّثة من ٩ خطوات — Updated 9-step algorithm |
| `SQL_QUERIES.sql` | قوالب SQL لكل خطوة — SQL templates for every step |
| `EXAMPLE_ARTIFACT.yaml` | مثال عملي كامل — Fully worked example |

## المخرج — Output

المخرج هو ملف YAML واحد لكل مجموعة ترادفية: `{synset_id}.evidence.yaml`

The output is one YAML file per synset: `{synset_id}.evidence.yaml`

## قاعدة البيانات — Database

```
arabic-dictionaries/db/arabic_dict.db
├── dictionaries     (107 dictionaries: OCR + Hawramani + ARABTERM)
├── entries          (760,660 entries)
├── definitions      (per-sense structured definitions)
├── examples         (quran, hadith, poetry, prose)
├── plurals          (broken plural forms)
├── derived_forms    (derivational morphology)
├── cross_refs       (dictionary cross-references)
├── provenance       (page numbers, source URIs)
├── entries_fts      (FTS5: Arabic text search)
└── entries_translations_fts  (FTS5: English/French search)
```
