# الملحق أ: دليل استعلام المعاجم — Appendix A: Dictionary Query Training Guide

> هذا الملحق دليل تدريبي للمراجع اللغوي لاستعلام قاعدة بيانات المعاجم يدوياً.
> الهدف: استرجاع شواهد موثوقة تدعم أو تدحض أو تُثري محتوى المجموعات الترادفية — فيما يتجاوز ما يوفره خط الأنابيب الآلي.

---

## أ.1 المقدمة — Introduction

### لماذا الاستعلام اليدوي؟ — Why Manual Queries?

خط الأنابيب الآلي يسترجع شواهد معجمية لكل مجموعة ترادفية عبر خمس استراتيجيات (مطابقة الكلمة الرئيسية، توسيع الجذر، بحث نصي كامل BM25، بحث دلالي ColBERT، جسر الترجمة الإنجليزية). لكنه يعاني من قيود:

| القيد | الأثر |
|-------|------|
| **اقتطاع التعريفات عند 300 حرف** | المداخل متعددة المعاني تُبتر — تفقد المعاني الثانوية والثالثية |
| **استخلاص كلمات مفتاحية ثابت** | الخوارزمية تستخلص من تعريف المجموعة فقط — قد تفوتها مصطلحات يفكر فيها المراجع |
| **عدم وجود مقارنة زمنية** | لا يعرض التطور الدلالي عبر القرون (من الكلاسيكي إلى الحديث) |
| **عدم إتاحة الاستكشاف الحر** | المراجع لا يستطيع طرح أسئلة مخصصة على البيانات |

**الاستعلام اليدوي** يسدّ هذه الفجوات: تعريفات كاملة، كلمات مفتاحية مخصصة، مقارنة زمنية، واستكشاف حر.

### طرق الوصول — Access Methods

| الطريقة | المستوى | متى تستخدمها |
|---------|---------|-------------|
| **DB Browser for SQLite** | متوسط | واجهة رسومية مع دعم SQL |
| **sqlite3 CLI** | متقدم | استعلامات معقدة وأتمتة |

---

## أ.2 بيئة العمل — Setup

### أ.2.1 سطر الأوامر sqlite3 — sqlite3 CLI

افتح الطرفية وشغّل:

```bash
sqlite3 "file:arabic-dictionaries/db/arabic_dict.db?mode=ro"
```

> **ملاحظة:** المعامل `?mode=ro` يفتح قاعدة البيانات **للقراءة فقط** — لا خطر على البيانات.

ثم اضبط التنسيق:

```sql
.mode column
.headers on
.width 20 15 10 60
PRAGMA cache_size = -64000;      -- 64 ميغا ذاكرة مؤقتة
PRAGMA mmap_size = 3000000000;   -- تعيين ذاكرة مباشرة (أسرع)
```

للخروج:

```
.quit
```

### أ.2.2 DB Browser for SQLite — واجهة رسومية

1. حمّل البرنامج من [sqlitebrowser.org](https://sqlitebrowser.org/dl/)
2. افتح الملف: `arabic-dictionaries/db/arabic_dict.db`
3. فعّل وضع القراءة فقط: `Edit → Preferences → Database → Open databases read-only`
4. انتقل إلى تبويب `Execute SQL` لكتابة الاستعلامات

---

## أ.3 هيكل قاعدة البيانات — Database Structure

### نظرة عامة — Overview

قاعدة البيانات تضم **760,660 مدخلاً** من **107 معجماً** في مخطط موحّد:

```
dictionaries (107 معجماً)
    └── entries (760,660 مدخلاً)
            ├── definitions  (614,227 تعريفاً)
            ├── examples     (86,031 شاهداً)
            ├── plurals      (24,466 جمعاً)
            ├── derived_forms (50,191 مشتقاً)
            ├── cross_refs   (10,453 إحالة)
            └── provenance   (552,601 مصدراً)
```

### المصادر الثلاثة — Three Data Sources

| المصدر | المعاجم | المداخل | POS؟ | أمثلة؟ | ترجمات؟ |
|--------|:-------:|--------:|:----:|:------:|:-------:|
| **OCR** (استخلاص بصري) | 5 | 109,769 | نعم | نعم | لا |
| **Hawramani** (تصدير رسمي) | 51 | 233,465 | جزئي | جزئي | لا |
| **ARABTERM** (مصطلحات تقنية) | 51 | 417,426 | لا | لا | نعم (EN/FR) |

### الجداول الرئيسية — Key Tables

#### `dictionaries` — فهرس المعاجم

| العمود | الوصف | مثال |
|--------|------|------|
| `id` | المعرّف | `1` |
| `key` | مفتاح فريد | `Al_Waseet` |
| `name_ar` | الاسم بالعربية | المعجم الوسيط |
| `name_en` | الاسم بالإنجليزية | Al-Mu'jam Al-Wasit |
| `source_type` | نوع المصدر | `ocr` / `hawramani` / `arabterm` |
| `period` | العصر | `classical` / `modern` |
| `death_year` | سنة وفاة المؤلف | `1311` (ابن منظور) |

#### `entries` — المداخل الموحّدة

| العمود | الوصف | مثال |
|--------|------|------|
| `id` | المعرّف | `42` |
| `dictionary_id` | FK إلى `dictionaries` | `3` |
| `headword` | الكلمة الرئيسية **بالتشكيل** | كَتَبَ |
| `headword_bare` | بدون تشكيل | كتب |
| `headword_norm` | مطبّعة (همزة/ألف موحّدة) | كتب |
| `root` | الجذر الثلاثي/الرباعي | كتب |
| `root_source` | مصدر الجذر | `ocr` / `lane` / `camel` |
| `pos` | نوع الكلمة | `noun` / `verb` / `adj` |
| `form` | الوزن الصرفي (للأفعال) | `I` / `IV` / `VIII` / `Q` |
| `definitions_text` | التعريفات مسطّحة (للبحث النصي) | الكِتَابَ: خَطَّهُ... |
| `translation_en` | ترجمة إنجليزية (ARABTERM فقط) | `book` |
| `translation_fr` | ترجمة فرنسية (ARABTERM فقط) | `livre` |
| `domain` | المجال التخصصي (ARABTERM فقط) | `Biology` |

#### `definitions` — التعريفات المهيكلة

| العمود | الوصف |
|--------|------|
| `entry_id` | FK إلى `entries` |
| `sense_index` | ترتيب المعنى (0، 1، 2...) |
| `text` | نص التعريف |
| `is_raw` | 1 = نص خام من Hawramani |

#### `examples` — الشواهد

| العمود | الوصف |
|--------|------|
| `entry_id` | FK إلى `entries` |
| `type` | النوع: `quran` / `poetry` / `hadith` / `proverb` / `usage` |
| `text` | نص الشاهد |
| `attribution` | النسبة (الشاعر، السورة، إلخ.) |

---

## أ.4 مستويات تطبيع الكلمة الرئيسية — Headword Normalization Levels

القاعدة تحتفظ بثلاث نسخ من كل كلمة رئيسية بمستويات تطبيع متزايدة:

| المستوى | العمود | ما يفعله | مثال: أحمد | مثال: مُسْتَشْفَى |
|---------|--------|---------|-----------|----------------|
| الأصلي | `headword` | يحتفظ بكل التشكيل | أَحْمَدُ | مُسْتَشْفَى |
| مجرّد | `headword_bare` | يزيل التشكيل فقط | أحمد | مستشفى |
| مطبّع | `headword_norm` | يزيل التشكيل + يوحّد الهمزة/الألف + يحوّل ى→ي | احمد | مستشفي |

### قواعد التطبيع (من `common.py`)

```
أ / إ / آ  →  ا      (الهمزات فوق/تحت الألف → ألف مجرّدة)
ى         →  ي      (الألف المقصورة → ياء)
ـ          →  (حذف)   (التطويل يُزال)
```

### متى تستخدم كل مستوى؟

| الموقف | العمود المناسب | السبب |
|--------|--------------|------|
| تعرف الإملاء الدقيق | `headword_bare` | مطابقة دقيقة بدون تشكيل |
| لا تعرف شكل الهمزة | `headword_norm` | يوحّد أ/إ/آ/ا |
| تبحث عن كلمة بألف مقصورة | `headword_norm` | يوحّد ى/ي |
| تريد التشكيل الأصلي | `headword` | للتمييز بين مثل: عِلم/عَلَم |

**مثال عملي:**

```sql
-- لن يجد "إبراهيم" لأن الهمزة مختلفة:
SELECT COUNT(*) FROM entries WHERE headword_bare = 'ابراهيم';

-- سيجدها لأن headword_norm يوحّد الهمزة:
SELECT COUNT(*) FROM entries WHERE headword_norm = 'ابراهيم';
```

---

## أ.5 وصفات الاستعلام حسب المهمة — Query Recipes by Review Task

> **تعليمات:** انسخ الاستعلام والصقه في sqlite3 أو DB Browser. استبدل الكلمة العربية بالكلمة التي تبحث عنها.

### أ.5.1 المقارنة عبر المعاجم — Cross-Dictionary Comparison

**الغرض:** رؤية كيف تعرّف جميع المعاجم نفس الكلمة — بتعريفات **كاملة** (بدون اقتطاع).

**متى تستخدمه:** عند الحاجة إلى التعريف الكامل الذي اقتطعه خط الأنابيب عند 300 حرف.

```sql
-- التعريفات الكاملة حسب المعنى لكل معجم
SELECT d.name_ar, d.death_year, df.sense_index, df.text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm = 'مال'
ORDER BY d.death_year, e.id, df.sense_index;
```

**نسخة مبسّطة** (التعريفات المسطّحة):

```sql
SELECT d.name_ar, d.period, d.death_year, e.pos, e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'مال'
ORDER BY d.death_year, d.name_en;
```

---

### أ.5.2 استكشاف عائلة الجذر — Root Family Exploration

**الغرض:** إيجاد كل الكلمات المشتقة من جذر واحد عبر جميع المعاجم — مفيد لإيجاد مرادفات ومشتقات.

**متى تستخدمه:** عند البحث عن لمات مفقودة (`add_lemma`) أو فهم العلاقات الاشتقاقية.

```sql
-- كل المداخل المشتقة من الجذر
SELECT e.headword_bare, e.pos, e.form, d.name_ar,
       SUBSTR(e.definitions_text, 1, 150) AS def_preview
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'مول'
ORDER BY e.pos, e.headword_bare, d.death_year;
```

**نسخة مختصرة** — الكلمات الفريدة فقط مع عدد المعاجم:

```sql
SELECT e.headword_bare, e.pos,
       COUNT(DISTINCT d.id) AS dict_count,
       GROUP_CONCAT(DISTINCT d.name_ar) AS dictionaries
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'مول'
GROUP BY e.headword_bare, e.pos
ORDER BY dict_count DESC;
```

> **تلميح:** إذا لم تعرف جذر الكلمة، ابحث عنها أولاً:
> ```sql
> SELECT DISTINCT root FROM entries
> WHERE headword_norm = 'تمويل' AND root IS NOT NULL;
> ```

---

### أ.5.3 البحث النصي الكامل — Full-Text Definition Search (FTS5)

**الغرض:** إيجاد مداخل تحتوي تعريفاتها على كلمات مفتاحية محددة — مفيد عند البحث عن مفاهيم مرتبطة.

**متى تستخدمه:** عند الحاجة لإيجاد مداخل تصف مفهوماً بكلمات مختلفة عن اللمات.

```sql
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def_preview
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH '"ثروة" OR "نقود"'
ORDER BY rank
LIMIT 30;
```

> **مهم:** لفظ الكلمات العربية بين علامتي تنصيص `"..."` دائماً — لتفادي أخطاء بناء جملة FTS5. انظر §أ.6 لتفاصيل بناء الجملة.

---

### أ.5.4 الجسر الإنجليزي — English Translation Bridge (ARABTERM)

**الغرض:** إيجاد المصطلحات العربية التقنية عبر مقابلها الإنجليزي — مفيد للمجموعات العلمية والتخصصية.

**متى تستخدمه:** عند العمل على مجموعة ترادفية تقنية (طبية، هندسية، بيولوجية، إلخ.) ولا تعرف المقابل العربي.

```sql
SELECT e.headword_bare, e.translation_en, e.translation_fr,
       e.domain, d.name_ar
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_translations_fts ON e.id = entries_translations_fts.rowid
WHERE entries_translations_fts MATCH '"money" OR "currency"'
ORDER BY rank
LIMIT 20;
```

> **تحذير:** الكلمة الإنجليزية قد تكون متعددة المعاني — `"bank"` تجلب نتائج مصرفية وجغرافية (ضفة). فلتر بالمجال عند الحاجة:
> ```sql
> ... AND e.domain = 'Commerce and Accounting'
> ```

---

### أ.5.5 الشواهد حسب النوع — Usage Examples by Type

**الغرض:** إيجاد شواهد قرآنية أو شعرية أو حديثية أو مثلية لكلمة معينة.

**متى تستخدمه:** عند الحاجة لأمر `add_example` — خاصة عند انعدام الشواهد في الملف المرجعي.

```sql
-- شواهد لكلمة محددة
SELECT e.headword_bare, ex.type, ex.text, ex.attribution, d.name_ar
FROM entries e
JOIN examples ex ON ex.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'مال'
  AND ex.type IN ('quran', 'hadith', 'poetry')
ORDER BY ex.type, d.death_year;
```

```sql
-- شواهد قرآنية لكل كلمات الجذر
SELECT e.headword_bare, ex.text
FROM entries e
JOIN examples ex ON ex.entry_id = e.id
WHERE e.root = 'مول' AND ex.type = 'quran'
ORDER BY e.headword_bare;
```

**أنواع الشواهد المتاحة:**

| النوع | العدد | الوصف |
|-------|------:|------|
| `poetry` | 49,747 | أبيات شعرية |
| `usage` | 16,811 | استعمال عام |
| `hadith` | 9,617 | أحاديث نبوية |
| `quran` | 7,411 | آيات قرآنية |
| `proverb` | 2,438 | أمثال عربية |

---

### أ.5.6 التطور الدلالي عبر الزمن — Chronological Semantic Evolution

**الغرض:** تتبع كيف تطور معنى الكلمة من المعاجم الكلاسيكية إلى الحديثة.

**متى تستخدمه:** عند الشك في أن المعنى المقصود تغيّر عبر الزمن — أو عند تعارض الشواهد بين المعاجم القديمة والحديثة.

```sql
SELECT d.death_year, d.name_ar, d.period, df.text AS definition
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm = 'مال'
  AND d.death_year IS NOT NULL
  AND df.sense_index = 0
ORDER BY d.death_year;
```

**ماذا تبحث عنه:**

| الظاهرة | المؤشر | مثال |
|---------|--------|------|
| **توسيع دلالي** | المعنى الحديث أعم من القديم | «مال» كانت تعني الإبل فقط، ثم توسعت لتشمل كل ثروة |
| **تضييق دلالي** | المعنى الحديث أخص من القديم | «سيّارة» كانت القافلة، ثم تخصصت للمركبة |
| **انزياح دلالي** | المعنى تغيّر جذرياً | «طيّارة» كانت الورقة التي تطير، ثم أصبحت الطائرة |

---

### أ.5.7 المقارنة بين التراثي والحديث — Classical vs. Modern Comparison

**الغرض:** مقارنة تعريفات ما قبل 1900 (كلاسيكية) مع الحديثة لنفس المفهوم.

**متى تستخدمه:** لتحديد ما إذا كان المفهوم المقصود هو المعنى الكلاسيكي أم الحديث.

```sql
SELECT d.period, d.name_ar, d.death_year,
       df.sense_index, df.text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm = 'حاسوب'
ORDER BY d.period DESC, d.death_year;
```

> **ملاحظة:** الكلمات المولّدة حديثاً (مثل «حاسوب») لن تظهر في المعاجم الكلاسيكية — غياب النتائج الكلاسيكية نفسه معلومة مفيدة (يؤكد أن الكلمة حديثة).

---

### أ.5.8 إيجاد مرشحات المرادف — Finding Synonym Candidates

**الغرض:** إيجاد كلمات أخرى تُذكر الكلمة المستهدفة في تعريفاتها — مرشحات لأمر `add_lemma`.

**متى تستخدمه:** عند الشك في وجود مرادفات لم يكتشفها خط الأنابيب.

```sql
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def_preview
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"مال"'
  AND e.headword_bare <> 'مال'
  AND d.source_type IN ('ocr', 'hawramani')
ORDER BY rank
LIMIT 20;
```

> **تلميح:** البادئة `definitions_text:` تحصر البحث في عمود التعريفات فقط — لتفادي النتائج التي تطابق الكلمة الرئيسية أو الجذر.

---

### أ.5.9 تصفية حسب نوع الكلمة والوزن — POS and Verb Form Filtering

**الغرض:** إيجاد أفعال بوزن صرفي محدد من جذر معيّن.

**متى تستخدمه:** عند تقييم الوزن الصرفي لفعل أو البحث عن أفعال مشتقة من نفس الجذر.

```sql
SELECT e.headword, e.form, d.name_ar,
       SUBSTR(e.definitions_text, 1, 150) AS def_preview
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'كتب' AND e.pos = 'verb'
ORDER BY e.form, d.death_year;
```

**أوزان الأفعال المتاحة:**

| الوزن | العدد | الوزن | العدد |
|-------|------:|-------|------:|
| I (فَعَلَ) | 17,425 | VII (اِنْفَعَلَ) | 688 |
| II (فَعَّلَ) | 3,218 | VIII (اِفْتَعَلَ) | 1,685 |
| III (فَاعَلَ) | 1,375 | IX (اِفْعَلَّ) | 170 |
| IV (أَفْعَلَ) | 3,687 | X (اِسْتَفْعَلَ) | 1,100 |
| V (تَفَعَّلَ) | 2,485 | Q (رباعي) | 2,321 |
| VI (تَفَاعَلَ) | 1,080 | | |

---

### أ.5.10 المصطلحات التخصصية حسب المجال — Domain-Specific Terminology

**الغرض:** تصفح مصطلحات ARABTERM في مجال تخصصي محدد.

**متى تستخدمه:** عند العمل على مجموعة ترادفية تقنية وتريد معرفة المصطلحات المعتمدة في المجال.

```sql
-- البحث في مجال محدد
SELECT e.headword_bare, e.translation_en, e.translation_fr
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE d.source_type = 'arabterm'
  AND e.domain = 'Biology'
  AND e.headword_bare LIKE '%خلي%'
ORDER BY e.headword_bare
LIMIT 30;
```

```sql
-- عرض المجالات المتاحة مع عدد المصطلحات
SELECT domain, COUNT(*) AS cnt
FROM entries
WHERE domain IS NOT NULL
GROUP BY domain
ORDER BY cnt DESC;
```

**أبرز المجالات:**

| المجال | المصطلحات |
|--------|----------:|
| The Unified Medical Dictionary | 132,975 |
| Al-Mawrid Al-Hadeeth | 62,266 |
| AGROVOC | 22,212 |
| Electropedia | 20,609 |
| Commerce and Accounting | 8,862 |

---

## أ.6 بناء جملة FTS5 — FTS5 Query Syntax Guide

### أنماط البحث — Query Patterns

| النمط | الصيغة | مثال | الشرح |
|-------|--------|------|-------|
| كلمة واحدة | `'"كلمة"'` | `'"مال"'` | يبحث عن الكلمة في أي عمود |
| عبارة حرفية | `'"كلمة1 كلمة2"'` | `'"جمع المال"'` | الكلمات متتالية بنفس الترتيب |
| OR (أيّ منها) | `'"أ" OR "ب"'` | `'"ثروة" OR "نقود" OR "أموال"'` | أي واحدة من الكلمات |
| NOT (استبعاد) | `'"أ" NOT "ب"'` | `'"مال" NOT "ميل"'` | استبعاد معنى «الميل» |
| بادئة | `'كلم*'` | `'مال*'` | كل ما يبدأ بـ «مال»: مالك، مالية، مال |
| عمود محدد | `'column:"كلمة"'` | `'definitions_text:"ثروة"'` | يبحث في عمود التعريفات فقط |

### ملاحظات مهمة

1. **التشكيل يُزال تلقائياً** — المحلل اللغوي (`unicode61 remove_diacritics 2`) يزيل التشكيل عند الفهرسة والاستعلام. لذا `كتب` تطابق `كَتَبَ` و`كِتَاب` و`كُتُب`.

2. **جدولان للبحث النصي:**
   - `entries_fts` — للنصوص العربية (الكلمة الرئيسية، الجذر، التعريفات)
   - `entries_translations_fts` — للترجمات الإنجليزية/الفرنسية والمجالات

3. **الترتيب بالأهمية** — استخدم `ORDER BY rank` للحصول على النتائج مرتبة بالأهمية (BM25).

4. **لفّ الكلمات العربية بعلامات تنصيص دائماً** — لتفادي أخطاء بناء جملة FTS5.

### أمثلة عملية

```sql
-- بحث بكلمات مفتاحية متعددة في التعريفات
SELECT e.headword_bare, d.name_ar, SUBSTR(e.definitions_text, 1, 200)
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"ثروة" OR definitions_text:"نقود"'
ORDER BY rank
LIMIT 20;

-- بحث بالبادئة في الكلمات الرئيسية
SELECT e.headword_bare, d.name_ar
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'headword_bare:مال*'
ORDER BY rank
LIMIT 20;

-- بحث إنجليزي في ترجمات ARABTERM
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
JOIN entries_translations_fts ON e.id = entries_translations_fts.rowid
WHERE entries_translations_fts MATCH '"computer" OR "computing"'
ORDER BY rank
LIMIT 20;
```

---

## أ.7 بناء منهجية استكشاف — Building an Exploration Methodology

### الإطار المنهجي — Step-by-Step Framework

اتبع هذه الخطوات بالترتيب، وتوقف عند أي خطوة تعطيك ما تحتاج:

| الخطوة | ماذا تفعل | أداة البحث | متى تتوقف |
|--------|----------|-----------|----------|
| **1** | ابدأ من لمات المجموعة ← مطابقة دقيقة | `headword_norm = ?` | وجدتَ تعريفات واضحة تطابق المفهوم |
| **2** | توسّع إلى الجذر | `root = ?` | وجدتَ مشتقات ومرادفات |
| **3** | ابحث بكلمات مفتاحية في التعريفات | FTS5 MATCH | وجدتَ مفاهيم مترادفة |
| **4** | استخدم الجسر الإنجليزي (ARABTERM) | `entries_translations_fts` | للمصطلحات التخصصية |
| **5** | قارن تاريخياً | `ORDER BY death_year` | لتتبع التطور الدلالي |
| **6** | تحقق من الشواهد الحقيقية | `examples WHERE type = ...` | لتأكيد الاستعمال في سياق حقيقي |

### متى توسّع البحث ومتى تضيّقه — Broadening vs. Narrowing

| الموقف | الإجراء | مثال |
|--------|---------|------|
| نتائج قليلة أو معدومة | وسّع: انتقل من `headword_norm` إلى `root` | لم تجد «حاسوب» ← ابحث بالجذر «حسب» |
| نتائج كثيرة جداً | ضيّق: أضف فلتر POS أو معجم محدد | «مال» تجلب 50+ نتيجة ← أضف `AND e.pos = 'noun'` |
| خلط بين معانٍ مختلفة | ضيّق: استخدم NOT في FTS5 | «مال» تجلب معنى الميل ← أضف `NOT "ميل"` |
| النتائج لا تطابق المفهوم | وسّع: جرّب كلمات مفتاحية مختلفة في FTS5 | بدلاً من «ثروة» جرّب «نقود» أو «أموال» |

### التعامل مع الشواهد المتعارضة — Handling Conflicting Evidence

عند تعارض المعاجم الكلاسيكية مع الحديثة:

| القاعدة | الشرح |
|---------|------|
| **للاستعمال المعاصر** ← أعطِ الأولوية للمعاجم الحديثة | المعجم الوسيط، المعاصرة (أحمد مختار)، الدوحة |
| **للنواة الدلالية** ← أعطِ الأولوية للمعاجم الكلاسيكية | لسان العرب، تاج العروس، القاموس المحيط |
| **سجّل كليهما** | في حقل `notes` — لا تُهمل أياً من الشواهد |
| **عند عدم اليقين** ← صعّد | استخدم أمر `escalate` وسجّل التعارض |

### ترتيب الحجية — Dictionary Authority Heuristic

هذا هو ترتيب الحجية الذي يستخدمه خط الأنابيب:

| المصدر | درجة الحجية | السبب |
|--------|:-----------:|------|
| معاجم كلاسيكية (Hawramani) | 1.00 | لسان العرب، تاج العروس، القاموس المحيط — مراجع تراثية موثوقة |
| معاجم OCR (مجمع اللغة) | 0.95 | المعجم الوسيط والكبير — معاجم معيارية حديثة |
| معاجم حديثة (Hawramani) | 0.85 | معاجم معاصرة |
| ARABTERM | 0.80 | مصطلحات تقنية — موثوقة في مجالها لكن محدودة خارجه |

---

## أ.8 أمثلة تطبيقية — Worked Examples

### مثال 1: اسم شائع — مال (المال / الثروة)

**السياق:** المجموعة الترادفية `awn4-13271441-n` (money, wealth). خط الأنابيب يوفر شواهد لكنها مقتطعة.

#### الخطوة 1 — المطابقة الدقيقة

```sql
SELECT d.name_ar, d.death_year, d.period
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'مال'
ORDER BY d.death_year;
```

**ما نبحث عنه:** كم معجماً يحتوي هذه الكلمة؟ هل موجودة في الكلاسيكي والحديث؟

#### الخطوة 2 — التعريفات الكاملة

```sql
SELECT d.name_ar, d.death_year, df.sense_index, df.text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm = 'مال' AND e.pos = 'noun'
ORDER BY d.death_year, df.sense_index;
```

**ما نبحث عنه:** هل المعنى 0 (الأول) يطابق «المال» بمعنى الثروة النقدية؟ أم أن المعنى الأول كان مختلفاً تاريخياً؟

**اكتشاف مهم:** في لسان العرب (1311م)، المعنى الأول لـ «مال» هو **الإبل** (ما يملكه الإنسان من إبل)، ثم توسع ليشمل كل ثروة. هذا تطور دلالي مهم يغيب عن التعريف الآلي.

#### الخطوة 3 — عائلة الجذر

```sql
SELECT e.headword_bare, e.pos, COUNT(DISTINCT d.id) AS dict_count
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'مول'
GROUP BY e.headword_bare, e.pos
ORDER BY dict_count DESC
LIMIT 15;
```

**ما نبحث عنه:** مشتقات مثل «تمويل»، «ممول»، «أموال» — هل أيّ منها مرشحة كلمة لم يكتشفها خط الأنابيب؟

#### الخطوة 4 — الجسر الإنجليزي

```sql
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
JOIN entries_translations_fts ON e.id = entries_translations_fts.rowid
WHERE entries_translations_fts MATCH '"money" OR "wealth" OR "capital"'
ORDER BY rank
LIMIT 15;
```

**ما نبحث عنه:** مصطلحات تقنية مثل «رأس المال»، «رصيد»، «نقد».

#### الخطوة 5 — الشواهد القرآنية

```sql
SELECT e.headword_bare, ex.text
FROM entries e
JOIN examples ex ON ex.entry_id = e.id
WHERE e.headword_norm = 'مال' AND ex.type = 'quran';
```

**ما نبحث عنه:** آيات تستعمل «مال» بالمعنى المقصود — تأكيد الاستعمال الحقيقي.

#### الحصيلة

الاستكشاف اليدوي كشف:
1. **تطور دلالي**: مال = إبل (كلاسيكي) → مال = كل ثروة (حديث) — معلومة غائبة عن التعريف الآلي
2. **تعريفات كاملة** لم يعرضها خط الأنابيب بسبب الاقتطاع
3. **شاهد قرآني** يؤكد الاستعمال بالمعنى المالي

---

### مثال 2: مصطلح مولّد — حاسوب (الحاسوب / الكمبيوتر)

**السياق:** مجموعة ترادفية تقنية. الكلمة حديثة النشأة ولن تظهر في المعاجم الكلاسيكية.

#### الخطوة 1 — المطابقة الدقيقة

```sql
SELECT d.name_ar, d.death_year, d.period, d.source_type
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'حاسوب'
ORDER BY d.death_year;
```

**المتوقع:** نتائج من المعاجم الحديثة و ARABTERM فقط — لا نتائج كلاسيكية.

#### الخطوة 2 — التعريف الكامل من المعاجم الحديثة

```sql
SELECT d.name_ar, df.text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm = 'حاسوب'
ORDER BY d.death_year;
```

#### الخطوة 3 — عائلة الجذر (حسب)

```sql
SELECT e.headword_bare, e.pos, COUNT(DISTINCT d.id) AS dict_count
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'حسب'
GROUP BY e.headword_bare, e.pos
HAVING e.pos IN ('noun', 'verb')
ORDER BY dict_count DESC
LIMIT 15;
```

**ما نبحث عنه:** هل الجذر «حسب» يدعم بنية «حاسوب» (وزن فاعول من الحساب)؟ ما الكلمات المجاورة؟

#### الخطوة 4 — مصطلحات ARABTERM في مجال الحوسبة

```sql
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
WHERE e.domain IN ('Dictionary of Information Technology Terms',
                    'Information and Communication')
  AND (e.headword_bare LIKE '%حاسوب%'
       OR e.headword_bare LIKE '%حاسب%'
       OR e.headword_bare LIKE '%كمبيوتر%')
ORDER BY e.headword_bare
LIMIT 20;
```

**ما نبحث عنه:** هل ARABTERM تستخدم «حاسوب» أم «حاسب» أم «كمبيوتر»؟ ما المصطلح المعتمد؟

#### الخطوة 5 — الجسر الإنجليزي

```sql
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
JOIN entries_translations_fts ON e.id = entries_translations_fts.rowid
WHERE entries_translations_fts MATCH '"computer"'
ORDER BY rank
LIMIT 15;
```

#### الحصيلة

الاستكشاف اليدوي كشف:
1. **غياب كلاسيكي** — يؤكد أن «حاسوب» كلمة مولّدة (مفيد لحقل `usage: modern`)
2. **بنية صرفية** — وزن «فاعول» (حاسوب) مبني على الجذر ح-س-ب (الحساب) — مفيد لـ `nuance_note`
3. **تعدد المقابلات** — ARABTERM تستخدم أشكالاً مختلفة (حاسوب، حاسب آلي، كمبيوتر) — مفيد لأمر `add_lemma`

---

## أ.9 تدريبات تحليلية — Analytical Exercises

> هذا القسم يختلف عن الأمثلة التطبيقية في أ.8: هناك عرضنا **الخطوات الإجرائية** (افعل 1 ثم 2 ثم 3). هنا نطبّق **منهجية تحقيقية ثابتة** — تسلسل تحليلي يتّبعه اللغوي عند مراجعة أي مجموعة ترادفية، حيث كل خطوة تبني على سابقتها.

### المنهجية التحليلية — The Investigative Methodology

عند مراجعة أي مجموعة ترادفية، يتّبع اللغوي هذا التسلسل التحليلي الثابت:

| الخطوة | السؤال المحوري | الهدف |
|--------|---------------|-------|
| **1. التحقق من اللمّات** | هل كل لمّة في المجموعة تحمل فعلاً المعنى المقصود؟ | إثبات أو دحض صحة كل لمّة بدليل معجمي |
| **2. اكتشاف لمّات مفقودة** | هل هناك كلمات أخرى تحمل نفس المعنى لكنها غائبة عن المجموعة؟ | توسيع المجموعة إن لزم (`add_lemma`) |
| **3. تدقيق التعريف** | هل تعريف المجموعة يطابق ما تقوله المعاجم؟ أوسع؟ أضيق؟ | ضبط التعريف (`nuance_note`) |
| **4. فحص العلاقات** | هل الأعلى (hypernym) والأدنى (hyponyms) في مكانهما الصحيح؟ | تأكيد أو تعديل الشبكة الدلالية |
| **5. الحصيلة** | ما الإجراءات المطلوبة؟ | قائمة أوامر المراجعة الملموسة |

> **مبدأ أساسي:** لا تنتقل إلى الخطوة التالية قبل إتمام السابقة. **التحقق من اللمّات أولاً** — لأنه إذا كانت اللمّة خاطئة، فلا فائدة من تدقيق التعريف.

---

### تدريب 1: اسم محسوس — شجرة (tree)

**المجموعة الترادفية:**

| الحقل | القيمة |
|-------|--------|
| المعرّف | `awn4-13124818-n` |
| اللمّات | شجرة |
| نوع الكلمة | اسم |
| التعريف | نبات خشبي معمر طويل له جذع رئيسي وفروع تشكل تاجاً مرتفعاً متميزاً |
| الأعلى (hypernym) | `awn4-13123895-n` (نبات خشبي / woody plant) |

#### الخطوة 1: التحقق من اللمّات

**اللمّة الوحيدة: شجرة** — هل تحمل معنى «نبات خشبي معمر طويل»؟

```sql
SELECT d.name_ar, d.period, d.death_year, e.pos,
       e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'شجر'
ORDER BY d.death_year;
```

**النتيجة:** 22 مدخلاً عبر المعاجم. التعريفات تؤكد المعنى النباتي:
- كتاب العين: «من النبات ما له ساق»
- المفردات: «ما له ساق يقال شجرة وشجر»
- المعجم الكبير: «نبتة ذات ساق صلبة»

**⚠️ ملاحظة:** الجذر ش-ج-ر متعدد المعاني — المعنى الفعلي «شَجَرَ بينهم» = تنازعوا. لعزل المعنى النباتي:

```sql
SELECT e.headword_bare, e.pos, d.name_ar,
       SUBSTR(e.definitions_text, 1, 150) AS def_preview
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'شجر' AND e.pos = 'noun'
ORDER BY d.death_year;
```

**الحكم:** اللمّة **مؤكَّدة** ✓ — كل المعاجم تتفق على أن شجرة = نبات ذو ساق.

#### الخطوة 2: اكتشاف لمّات مفقودة

هل هناك كلمات أخرى تعني «شجرة» لكنها غائبة عن المجموعة؟

```sql
SELECT e.headword_bare, e.pos,
       COUNT(DISTINCT d.id) AS dict_count
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'شجر'
GROUP BY e.headword_bare, e.pos
ORDER BY dict_count DESC;
```

**النتيجة:** شجرة (7 معاجم)، شجري (7)، تشجير (5)، شجار (4)، أشجار (2).

- «تشجير» (afforestation) = مفهوم مختلف (عملية الغرس) — ليس مرادفاً لشجرة
- «أشجار» = جمع شجرة — ليس مرشحاً كلمّة مستقلة
- لا يوجد مرادف مفقود واضح

```sql
-- هل هناك كلمات أخرى تُعرَّف بـ «نبات خشبي» أو «ذو ساق»؟
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"نبات" AND definitions_text:"ساق"'
  AND e.headword_bare <> 'شجر'
  AND d.source_type IN ('ocr', 'hawramani')
ORDER BY rank
LIMIT 10;
```

**الحكم:** لا مرادفات مفقودة. المجموعة بلمّة واحدة كافية.

#### الخطوة 3: تدقيق التعريف

تعريف AWN: «نبات خشبي معمر طويل له **جذع رئيسي** و**فروع تشكل تاجاً** مرتفعاً متميزاً»

التعريف الكلاسيكي: «من النبات **ما له ساق**»

```sql
SELECT e.headword_bare, ex.text, d.name_ar
FROM entries e
JOIN examples ex ON ex.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'شجر' AND ex.type = 'quran'
ORDER BY e.headword_bare;
```

**النتيجة:** 10 شواهد قرآنية — منها ﴿وَأَنْبَتْنَا عَلَيْهِ شَجَرَةً مِنْ يَقْطِينٍ﴾ (اليقطين نبات متسلّق لا شجرة بالتعريف العلمي) — التعريف الكلاسيكي **أوسع** من AWN.

**الحكم:** تعريف AWN أدق علمياً (يميّز الشجرة عن الشجيرة بشرط الجذع والتاج)، لكن التعريف الكلاسيكي أوسع — يستحق `nuance_note`.

#### الخطوة 4: فحص العلاقات

الأعلى: نبات خشبي (woody plant) — هل شجرة نوع من النبات الخشبي؟

```sql
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 150) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"خشبي" OR definitions_text:"خشب"'
  AND d.source_type IN ('ocr', 'hawramani')
ORDER BY rank
LIMIT 10;
```

**الحكم:** العلاقة بالأعلى منطقية — الشجرة نوع من النبات الخشبي.

#### الخطوة 5: الحصيلة

| الإجراء | التفصيل |
|---------|---------|
| ✓ تأكيد | اللمّة «شجرة» مؤكَّدة بإجماع المعاجم |
| `nuance_note` | التعريف الكلاسيكي «ما له ساق» أوسع من AWN — يشمل الشجيرات |
| ملاحظة تقنية | الجذر ش-ج-ر متعدد المعاني — عند البحث بالجذر، صفِّ بـ `pos = 'noun'` لعزل المعنى النباتي |

---

### تدريب 2: اسم مجرّد — حب / محبة (love)

**المجموعة الترادفية:**

| الحقل | القيمة |
|-------|--------|
| المعرّف | `awn4-07558676-n` |
| اللمّات | حب، محبة |
| نوع الكلمة | اسم |
| التعريف | عاطفة إيجابية قوية من التقدير والمودة |
| أمثلة | حبه لعمله؛ يحتاج الأطفال الكثير من الحب |
| الأعلى | `awn4-07495208-n` (شعور / feeling) |
| الأدنى (13) | إعجاب، ولع، حب أمومي، عبادة... |

#### الخطوة 1: التحقق من اللمّات

مجموعة بلمّتين — يجب التحقق من كل واحدة.

**اللمّة 1: حب** — هل تحمل معنى «عاطفة إيجابية قوية»؟

```sql
SELECT d.name_ar, e.pos, SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'حب'
ORDER BY d.death_year;
```

**⚠️ فخ تعدد المعاني:** النتائج مختلطة:
- الوسيط (فعل): «صار محبوباً» ← المعنى العاطفي ✓
- المعجم الكبير (اسم): «الوِدادُ والمَحَبَّةُ» ← المعنى العاطفي ✓
- المعجم الكبير (اسم): «يابِسُ البَقْلِ» ← حَبّ = grain ✗ (معنى نباتي!)
- المفردات: «الحَبُّ والحَبَّة يقال في الحنطة والشعير» ← حبوب ✗

**كيف أميّز؟** المفردات تفرّق بالتشكيل: الحُبّ (بالضم = love) vs الحَبّ (بالفتح = grain). لكن `headword_norm` يمسح هذا الفرق. الحل: اقرأ التعريف أو استخدم `headword` (مع التشكيل).

**الحكم:** اللمّة «حب» **مؤكَّدة** ✓ — بشرط التمييز عن المعنى النباتي.

**اللمّة 2: محبة** — هل هي مرادفة لحب؟

```sql
SELECT d.name_ar, e.headword_bare, e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'محبه';
```

**⚠️ فخ أداة التعريف:** صفر نتائج! قاعدة البيانات تخزّنها بأل: **المحبة**.

```sql
-- الحل: بحث مع ال
SELECT d.name_ar, e.headword, e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_bare = 'المحبة';
```

**النتيجة:** 7 مداخل. التعريفات تؤكد المعنى العاطفي:
- المعجم الكبير: «الودُّ، إرادة الخير»
- «وَالحُبُّ أَعَمُّ مِنَ العِشْقِ» ← الحب أشمل من العشق

**الحكم:** اللمّة «محبة» **مؤكَّدة** ✓ — مرادفة لحب. ملاحظة: محبة أعلى سجلاً (أدبي/قرآني).

#### الخطوة 2: اكتشاف لمّات مفقودة

المعاجم تعرّف الحب بـ «الوِداد والمحبة» — هل ود / مودة مرشحتان كلمّتان إضافيتان؟

```sql
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH '"ود" OR "مودة" OR "عشق"'
  AND d.source_type IN ('ocr', 'hawramani')
ORDER BY rank
LIMIT 15;
```

**ما أبحث عنه:** مرادفات مرشحة: ود، مودة، عشق، هوى، غرام.

```sql
-- شواهد شعرية تكشف عن الكلمات المستعملة في نفس السياق
SELECT ex.text, ex.attribution, d.name_ar
FROM entries e
JOIN examples ex ON ex.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'حب'
  AND ex.type = 'poetry'
ORDER BY d.death_year
LIMIT 10;
```

**النتيجة:** شواهد شعرية غنية: «وَزَادَه كَلَفًا في الحُبِّ أَنْ مَنَعَتْ» — تؤكد المعنى العاطفي.

**الحكم:** «ود» و«مودة» مرشحتان لـ `add_lemma` إن لم تكونا في مجموعات مجاورة. «عشق» و«هوى» أقرب لمجموعات أخرى (شغف، هيام).

#### الخطوة 3: تدقيق التعريف

تعريف AWN: «عاطفة إيجابية قوية من **التقدير** و**المودة**»

المعاجم: «الوِداد والمحبة» — تعريف AWN يزيد «التقدير» و«القوة».

المفردات (الراغب): «الحُبُّ أَعَمُّ مِنَ العِشْقِ» ← الحب أشمل، وهذا يتسق مع تعريف AWN الواسع.

**الحكم:** التعريف مناسب — يغطي المعنى العام دون تضييقه إلى العشق أو الهوى.

#### الخطوة 4: فحص العلاقات

الأعلى: شعور (feeling) — هل الحب نوع من الشعور؟ نعم، بلا خلاف.

13 أدنى (إعجاب، ولع، حب أمومي...) — هل تؤيدها المعاجم؟

```sql
-- هل «ولع» موجودة بمعنى نوع من الحب؟
SELECT d.name_ar, e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'ولع'
ORDER BY d.death_year;
```

**الحكم:** العلاقات مقبولة.

#### الخطوة 5: الحصيلة

| الإجراء | التفصيل |
|---------|---------|
| ✓ تأكيد | «حب» مؤكَّدة — مع التحذير من خلطها بمعنى الحبوب |
| ✓ تأكيد | «محبة» مؤكَّدة — مرادفة لحب بسجل أعلى (أدبي/قرآني) |
| ملاحظة عملية | **فخ أداة التعريف**: محبة مخزّنة كـ «المحبة» — ابحث دائماً بأل وبدونها |
| ملاحظة عملية | **فخ تعدد المعاني**: حب = حُبّ (love) + حَبّ (grain) — اقرأ التعريف للتمييز |
| مرشح `add_lemma` | ود، مودة — إن لم تكونا في مجموعات مجاورة |

---

### تدريب 3: فعل — كَتَبَ (to write/inscribe)

**المجموعة الترادفية:**

| الحقل | القيمة |
|-------|--------|
| المعرّف | `awn4-01694952-v` |
| اللمّات | كَتَبَ |
| نوع الكلمة | فعل |
| التعريف | خطّ كلمات أو رموز على سطح |
| أمثلة | كتب الفنان أحرفاً صينية على ورقة بيضاء كبيرة |
| الأعلى | `awn4-01585566-v` (خطّ / mark) |
| الأدنى (12) | خطّ اليد، اختزال، طباعة، نقش، نسخ حرفي... |

#### الخطوة 1: التحقق من اللمّات

**اللمّة الوحيدة: كَتَبَ** — هل تحمل معنى «خطّ كلمات على سطح»؟

الأفعال العربية تتميز بتعدد المعاني داخل الباب الواحد وتعدد الأبواب من الجذر نفسه. يجب التحقق من أن المعنى المقصود موجود **وأنه المعنى الأول** (أو على الأقل معنى مركزي).

```sql
SELECT d.name_ar, df.sense_index, df.text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN definitions df ON df.entry_id = e.id
WHERE e.headword_norm = 'كتب' AND e.pos = 'verb'
  AND d.name_ar LIKE '%الوسيط%'
ORDER BY e.id, df.sense_index;
```

**النتيجة:** الوسيط يقسّم كَتَبَ إلى معانٍ متعددة:
- المعنى 0: «الكتاب: خطّه» ← **هذا ما تغطيه المجموعة** ✓
- المعنى 1: «السقاء ونحوه: خرزه بسيرين» ← خياطة الجلد! ✗
- المعنى 2: «القربة: شدّها بالوكاء» ← ربط/شدّ ✗
- المعنى 3: «الله الشيء: قضاه وأوجبه» ← قدر إلهي ✗

**الحكم:** اللمّة «كتب» **مؤكَّدة** ✓ — لكن فقط بالمعنى 0 (خطّ). المعاني الأخرى (خرز، شدّ، قضى) مجموعات ترادفية مختلفة.

**⚠️ تحقق إضافي — الأبواب الصرفية:** هذه المجموعة تغطي الباب I فقط. ما الأبواب الأخرى؟

```sql
SELECT e.headword, e.form, d.name_ar,
       SUBSTR(e.definitions_text, 1, 120) AS def_preview
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'كتب' AND e.pos = 'verb'
ORDER BY e.form, d.death_year;
```

**النتيجة:** 8 أبواب مُثبتة في قاعدة البيانات:

| الباب | الوزن | المعنى (الوسيط) |
|-------|-------|----------------|
| I | كَتَبَ | خطّ / خرز / شدّ / قضى |
| II | كَتَّبَ | علّم الكتابة |
| III | كَاتَبَ | راسل / كاتَبَ العبدَ (عقد المكاتبة) |
| IV | أَكْتَبَ | أملى / علّم الكتابة |
| V | تَكَتَّبَ | تجمّعوا |
| VI | تَكَاتَبَ | تراسلا |
| VIII | اكْتَتَبَ | كتب نفسه في ديوان / استنسخ |
| X | اسْتَكْتَبَ | اتخذه كاتباً / سأله أن يكتب |

كل باب يحتاج مجموعة ترادفية مستقلة — كاتَبَ (III) = «correspond by letter»، أكتَبَ (IV) = «dictate»، إلخ.

#### الخطوة 2: اكتشاف لمّات مفقودة

هل هناك أفعال أخرى من الباب I تعني «خطّ على سطح» — مرادفات لكتب؟

```sql
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"خطّ"'
  AND e.pos = 'verb'
  AND e.headword_bare <> 'كتب'
  AND d.source_type IN ('ocr', 'hawramani')
ORDER BY rank
LIMIT 10;
```

**ما أبحث عنه:** سطّر، خطّ، دوّن، حرّر — أفعال كتابة مرشحة.

```sql
-- المشتقات الاسمية من ك-ت-ب (للإحاطة بحجم العائلة)
SELECT e.headword_bare, e.pos,
       COUNT(DISTINCT d.id) AS dict_count
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'كتب'
GROUP BY e.headword_bare, e.pos
ORDER BY dict_count DESC
LIMIT 20;
```

**النتيجة:** كتاب (5)، كتابة (6)، كاتب (5)، مكتب (5)، كتيب (4)، مكتبة (3)، + مركّبات ARABTERM: كتاب إلكتروني، كتابة صوتية.

**الحكم:** «سطّر» و«خطّ» و«دوّن» مرشحات — لكنها قد تنتمي إلى مجموعات فرعية (hyponyms) أكثر من كونها مرادفات مباشرة لكتب.

#### الخطوة 3: تدقيق التعريف

تعريف AWN: «خطّ كلمات أو رموز على سطح»

الوسيط (المعنى 0): «الكتاب: خطّه» — مطابقة وثيقة.

```sql
-- لفصل المعاني: استخدم جدول definitions بدلاً من definitions_text
SELECT df.sense_index, df.text
FROM entries e
JOIN definitions df ON df.entry_id = e.id
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'كتب' AND e.pos = 'verb'
  AND d.name_ar LIKE '%الوسيط%'
ORDER BY e.id, df.sense_index;
```

**الدرس التقني:** الحقل `definitions_text` يدمج كل المعاني في نص واحد. لفصلها، استخدم جدول `definitions` مع `sense_index`.

**الحكم:** التعريف مناسب ودقيق — يغطي المعنى الأول للباب I.

#### الخطوة 4: فحص العلاقات

الأعلى: خطّ (mark) — هل الكتابة نوع من التخطيط؟ منطقي.

12 أدنى: خط اليد، اختزال، طباعة — كل منها طريقة كتابة.

```sql
-- هل مركّبات ARABTERM تتطابق مع الأدنى (hyponyms)؟
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE d.source_type = 'arabterm'
  AND e.headword_bare LIKE '%كتاب%'
ORDER BY e.headword_bare
LIMIT 15;
```

**الحكم:** العلاقات مقبولة. مركّبات ARABTERM (كتاب إلكتروني، كتابة صوتية) تشير إلى مفاهيم قد تحتاج مجموعات مستقلة.

#### الخطوة 5: الحصيلة

| الإجراء | التفصيل |
|---------|---------|
| ✓ تأكيد | اللمّة «كتب» مؤكَّدة — بالتحديد المعنى 0 (خطّ) من الباب I |
| ملاحظة | 8 أبواب فعلية مُثبتة — كل باب يحتاج مجموعة مستقلة |
| مرشح `add_lemma` | سطّر، خطّ، دوّن — مرشحات كمرادفات أو أدنى |
| تقنية | لفصل المعاني استخدم جدول `definitions` + `sense_index` بدلاً من `definitions_text` |

---

### تدريب 4: صفة متعددة اللمّات — جميل / حسن / لطيف (pleasant / beautiful)

**المجموعة الترادفية:**

| الحقل | القيمة |
|-------|--------|
| المعرّف | `awn4-01590750-a` |
| اللمّات | جميل، حسن، لطيف |
| نوع الكلمة | صفة |
| التعريف | سارّ أو مبهج أو مقبول في الطبيعة أو المظهر |
| أمثلة | وجه جميل؛ أخلاق حسنة؛ يا لك من رفيق لطيف |
| العلاقات | also → `awn4-01805299-a` (جذّاب)؛ attribute → `awn4-04786760-n` (جمال) |

#### الخطوة 1: التحقق من اللمّات

ثلاث لمّات من ثلاثة جذور مختلفة (ج-م-ل، ح-س-ن، ل-ط-ف) — يجب التحقق من كل واحدة على حدة.

**اللمّة 1: جميل (ج-م-ل)**

```sql
SELECT d.name_ar, e.definitions_text
FROM entries e JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'جميل'
ORDER BY d.death_year;
```

**النتيجة:**
- ياقوت: «ضد القبيح» ← مطابق ✓
- السلطان قابوس: «من حسن خِلقة أو خُلقاً» ← مطابق ✓

**الحكم:** مؤكَّدة ✓

**اللمّة 2: حسن (ح-س-ن)**

```sql
SELECT d.name_ar, SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'حسن'
ORDER BY d.death_year;
```

**النتيجة:**
- الوسيط: «جَمُلَ» ← تعريف بالمرادف (= صار جميلاً)! ✓
- المفردات: «كل مبهج مرغوب فيه — ثلاثة أضرب: عقلي وحسّي وهوائي» ← أوسع من «سارّ» لكن يتضمنه ✓

**الحكم:** مؤكَّدة ✓ — مع ملاحظة أن حسن **أعمّ** من جميل (يشمل الحسن العقلي والحسي).

**اللمّة 3: لطيف (ل-ط-ف)**

```sql
SELECT d.name_ar, e.definitions_text
FROM entries e JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'لطيف'
ORDER BY d.death_year;
```

**النتيجة:**
- السلطان قابوس: «**العالم بخفايا الأمور ودقائقها، واسم من أسماء الله**» ← ليس «سارّ» بل «خبير بالدقائق»! ⚠️

```sql
-- هل المعنى الحديث «ظريف/لطيف المعشر» موجود أيضاً؟
SELECT e.headword_bare, d.name_ar, d.period,
       SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.root = 'لطف'
ORDER BY d.death_year;
```

**اكتشاف مهم:** لطيف في العربية الكلاسيكية = «رقيق، خفيّ، عالم بالدقائق» (اسم إلهي). المعنى الحديث «ظريف/محبوب/pleasant» تحوّل دلالي.

**الحكم:** مؤكَّدة **بتحفظ** ⚠️ — صالحة للعربية المعاصرة فقط. في الكلاسيكية، لطيف يقع في حقل دلالي مختلف تماماً.

#### الخطوة 2: اكتشاف لمّات مفقودة

**اختبار الترادف الدائري:** هل تعريفات كل لمّة تذكر اللمّات الأخرى؟

```sql
-- هل تعريفات «جميل» تذكر «حسن»؟
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"حسن"'
  AND e.headword_bare = 'جميل'
LIMIT 5;
```

**الحكم:** الوسيط يعرّف حسن بـ «جمُل» وجميل بما يتضمن «حسن» — ترادف دائري مُثبت.

```sql
-- كلمات أخرى تُعرَّف بـ «جميل» — مرشحات إضافية
SELECT e.headword_bare, d.name_ar,
       SUBSTR(e.definitions_text, 1, 200) AS def
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
JOIN entries_fts ON e.id = entries_fts.rowid
WHERE entries_fts MATCH 'definitions_text:"جميل"'
  AND e.headword_bare NOT IN ('جميل', 'حسن', 'لطيف')
  AND d.source_type IN ('ocr', 'hawramani')
ORDER BY rank
LIMIT 10;
```

**ما أبحث عنه:** وسيم، بهيّ، حلو — مرشحات كلمّات إضافية.

#### الخطوة 3: تدقيق التعريف

تعريف AWN: «سارّ أو مبهج أو مقبول في الطبيعة أو المظهر»

| اللمّة | التعريف المعجمي | الموافقة |
|--------|----------------|----------|
| جميل | «ضد القبيح» — الجمال المرئي/الخَلقي | ✓ يطابق «مقبول في المظهر» |
| حسن | «كل مبهج مرغوب فيه» — أوسع (عقلي + حسي) | ✓ يتضمن تعريف AWN |
| لطيف | «العالم بخفايا الأمور» — ليس «سارّ» كلاسيكياً | ⚠️ يتطلب `nuance_note` |

**الحكم:** التعريف مناسب **للمعاصرة**. يحتاج ملاحظة عن التحول الدلالي للطيف.

#### الخطوة 4: فحص العلاقات

- also → جذّاب (attractive): منطقي — الجمال والجاذبية متقاربان
- attribute → جمال (beauty): منطقي — جميل صفة الجمال

**الحكم:** العلاقات مقبولة.

#### الخطوة 5: الحصيلة

| الإجراء | التفصيل |
|---------|---------|
| ✓ تأكيد | «جميل» و«حسن» مؤكَّدتان بإجماع المعاجم |
| ⚠️ تحفظ | «لطيف» صالحة للمعاصرة فقط — المعنى الكلاسيكي = «خفيّ/دقيق» (اسم إلهي) |
| `nuance_note` | تحول دلالي: لطيف = subtle/knowing (كلاسيكي) → pleasant/kind (حديث) |
| تأكيد | ترادف دائري مُثبت: حسن ↔ جميل (الوسيط يعرّف أحدهما بالآخر) |
| تقنية | **اختبار الترادف الدائري**: ابحث في FTS5 عن كل لمّة في تعريفات اللمّات الأخرى |

---

### تدريب 5: مصطلح تقني حديث — خوارزمية (algorithm)

**المجموعة الترادفية:**

| الحقل | القيمة |
|-------|--------|
| المعرّف | `awn4-05855965-n` |
| اللمّات | خوارزمية |
| نوع الكلمة | اسم |
| التعريف | قاعدة دقيقة (أو مجموعة من القواعد) تحدد كيفية حل مشكلة معينة |
| الأعلى | `awn4-05855459-n` (قاعدة / rule) |
| الأدنى | خوارزمية فرز، خوارزمية اشتقاقية، الطريقة السمبلكسية، خوارزمية جينية... |

#### الخطوة 1: التحقق من اللمّات

**اللمّة الوحيدة: خوارزمية** — هل مثبتة معجمياً؟

```sql
SELECT d.name_ar, d.period, d.source_type,
       e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_norm = 'خوارزميه';
```

**النتيجة:** **صفر نتائج** من المعاجم الكلاسيكية والحديثة. هذا متوقع لمصطلح تقني مولّد.

```sql
-- هل خوارزم (الاسم الأصلي) موجود؟
SELECT d.name_ar, d.source_type, e.pos,
       e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE e.headword_bare = 'خوارزم';
```

**النتيجة:** نتيجة واحدة — المعجم الكبير (OCR) يُدرج «خوارزم» كاسم عَلَم فقط (اسم المدينة/العالم). المصطلح التقني بُني بإضافة لاحقة «-ية» (على وزن فَعَالِيَّة).

**الحكم:** اللمّة **غير مثبتة كلاسيكياً** لكنها مصطلح مولّد معتمد — مفيد لحقل `usage: modern`.

#### الخطوة 2: اكتشاف لمّات مفقودة

هل هناك أشكال إملائية بديلة أو مصطلحات مقابلة؟

```sql
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
JOIN entries_translations_fts ON e.id = entries_translations_fts.rowid
WHERE entries_translations_fts MATCH '"algorithm"'
ORDER BY rank
LIMIT 15;
```

**النتيجة — مفاجأة:**

| الشكل العربي | المجال | ملاحظة |
|-------------|--------|--------|
| خوارزمية | التعليم، المدنية، الاستشعار، الاتصالات، الرياضيات | الشكل المعياري ✓ |
| خورازمية | الهندسة الكهربائية | **تهجئة بديلة** (قلب حرفين!) |
| ألغوريتم | التعليم | اقتراض مباشر من الإنجليزية |
| لوغاريتم | هندسة السيارات | **خطأ!** لوغاريتم ≠ خوارزمية (logarithm ≠ algorithm) |

**الحكم:** «خورازمية» تهجئة بديلة مرشحة لـ `add_lemma`. «لوغاريتم» خطأ يجب تجاهله.

#### الخطوة 3: تدقيق التعريف

تعريف AWN: «قاعدة دقيقة (أو مجموعة من القواعد) تحدد كيفية حل مشكلة معينة»

```sql
SELECT e.headword_bare, e.translation_en, e.domain,
       e.definitions_text
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE d.source_type = 'arabterm'
  AND e.headword_bare LIKE '%خوارزمي%'
ORDER BY e.headword_bare;
```

**النتيجة:** المورد الحديث: «طريقة مقننة **في الرياضيات**» — أضيق من AWN (يحصرها في الرياضيات فقط). تعريف AWN أدق لأنه يشمل الحوسبة.

**الحكم:** تعريف AWN أفضل من المورد الحديث — لا يحتاج تعديلاً.

#### الخطوة 4: فحص العلاقات

الأعلى: قاعدة (rule) — هل الخوارزمية نوع من القواعد؟ نعم، بالمعنى الواسع.

الأدنى: خوارزمية فرز، خوارزمية جينية...

```sql
SELECT e.headword_bare, e.translation_en, e.domain
FROM entries e
JOIN dictionaries d ON e.dictionary_id = d.id
WHERE d.source_type = 'arabterm'
  AND e.headword_bare LIKE '%خوارزمي%'
ORDER BY e.headword_bare;
```

**ما أبحث عنه:** هل المركّبات (خوارزمية موازية، خوارزمية جينية) تتطابق مع الأدنى في المجموعة؟

**الحكم:** العلاقات مقبولة.

#### الخطوة 5: الحصيلة

| الإجراء | التفصيل |
|---------|---------|
| `usage: modern` | غياب كلاسيكي كامل — مصطلح مولّد |
| `nuance_note` | مبني على اسم العالم الخوارزمي + لاحقة -ية (وزن فعالية) |
| مرشح `add_lemma` | خورازمية (تهجئة بديلة في الهندسة الكهربائية) |
| **تحذير** | لوغاريتم ≠ خوارزمية — خلط شائع في بعض المصادر |
| ملاحظة | تعريف المورد الحديث «في الرياضيات» أضيق من AWN — تعريف AWN أدق |

---

> **تذكير:** هذا الملحق مُكمّل لخط الأنابيب الآلي، لا بديل عنه. ابدأ دائماً من ملف `.md` المرجعي، ثم انتقل إلى الاستعلام اليدوي عند الحاجة لمزيد من العمق.
