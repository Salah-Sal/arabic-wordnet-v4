# مخطط المراجعة — Review YAML Schema (v2)

Reference for every field in `review.yaml`.

---

## Top-Level Fields

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|-------------|-------------|
| `synset_id` | string | always | `awn4-XXXXXXXX-X` | Synset identifier |
| `reviewer` | string | yes | — | Reviewer name |
| `review_date` | string | yes | `YYYY-MM-DD` | Date of review |
| `verdict` | enum | **إلزامي** | `excellent` · `good` · `acceptable` · `poor` | Overall quality verdict |

---

## `lemmas[]` — اللمّات

Each lemma is a mapping:

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|-------------|-------------|
| `lemma` | string | yes | — | اللمّة بالتشكيل |
| `status` | enum | **إلزامي** | `confirmed` · `rejected` · `modified` | الحكم |
| `evidence` | string | **إلزامي** | — | اسم المعجم + اقتباس النص المثبت للمعنى |
| `synonymy_tests` | mapping | confirmed/modified | — | اختبارات الترادف الرباعية (انظر أدناه). يُترك فارغاً إذا `rejected` |
| `nuance` | string | confirmed/modified | — | نوع الترادف (تطابقي/تقاربي) والسمة الفارقة |
| `root` | string | yes | — | الجذر |
| `usage` | enum | yes | `archaic` · `modern` · `common` | مستوى الاستخدام الزمني |
| `eloquence` | enum | yes | `eloquent` · `neologism` · `colloquial` | مستوى الفصاحة |
| `register` | string | recommended | `literal` or `figurative (type)` | حقيقي أم مجازي |
| `connotation` | enum | recommended | `positive` · `negative` · `neutral` | الإيحاء |
| `frame` | string | for verbs | — | لازم · متعدٍ بنفسه · متعدٍ بـ(حرف) |
| `collocate` | string | optional | — | المتلازم النهائي المعتمد (مثال: كلمتين). يختلف عن `synonymy_tests.collocation` المقارَن |
| `flags` | list | optional | flag codes | أعلام خاصة بهذه اللمّة |

### `lemmas[].synonymy_tests` — اختبارات الترادف

Nested mapping within each lemma. All four fields are mandatory for `confirmed`/`modified` lemmas. Leave empty for `rejected` lemmas.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `substitution` | string | **إلزامي** | نتيجة اختبار الاستبدال في جملة شاهد |
| `collocation` | string | **إلزامي** | مقارنة تقاطع المتلازمات مع اللمّات الأخرى (تحليلي) |
| `antonymy` | string | **إلزامي** | المضاد الدلالي المباشر في هذا السياق |
| `componential` | string | **إلزامي** | السمات الدلالية بإشارات (+/-) |

---

## `missing[]` — مرادفات مفقودة

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|-------------|-------------|
| `candidate` | string | yes | — | المرشّح |
| `verdict` | enum | yes | `add` · `new_synset` · `reject` | الحكم |
| `evidence` | string | yes | — | المعجم + التبرير |

---

## `definition` — التعريف

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|-------------|-------------|
| `original` | string | pre-filled | — | تعريف AWN الأصلي (لا تعدّل) |
| `verdict` | enum | **إلزامي** | `retain` · `revise` · `reject` | الحكم |
| `revised` | string | if revise/reject | — | النص البديل |
| `source` | string | recommended | — | المعجم المستنَد إليه |

---

## `examples[]` — الشواهد

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|-------------|-------------|
| `text` | string | yes | — | نص الشاهد |
| `type` | enum | yes | `quran` · `hadith` · `poetry` · `prose` · `authored` | نوع الشاهد |
| `source` | string | recommended | — | المصدر |

---

## `hypernym` — العلاقة مع الأعمّ

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|-------------|-------------|
| `target` | string | yes | `awn4-XXXXXXXX-X` | معرّف الأعمّ |
| `verdict` | enum | yes | `ok` · `flag` | الحكم |
| `note` | string | if flag | — | سبب التعليم |

---

## `flags[]` — الأعلام

Synset-level flags. Per-lemma flags go in `lemmas[].flags`.

| الرمز | متى يُستخدم |
|-------|-------------|
| `WEAK_EVIDENCE` | مصدر واحد فقط أو غياب شواهد كلاسيكية |
| `MEANING_MISMATCH` | المعنى المعجمي يختلف عن المعنى المقصود |
| `LEMMA_NOT_FOUND` | الكلمة غير موثّقة في أي معجم |
| `HOMONYMY_RISK` | الجذر يحمل معاني متعددة غير مرتبطة |
| `SYNONYM_REJECTED` | اللمّات ليست مترادفات فعلاً |
| `DEF_CONTRADICTS` | تعريف الشبكة يناقض المصدر المعجمي |
| `CALQUE_WARNING` | قالب أجنبي مستعار |
| `LEXICAL_GAP` | لا مكافئ عربي من كلمة واحدة |
| `SPLIT_NEEDED` | المعنى الحقيقي والمجازي مختلطان |
| `POS_MISMATCH` | التصنيف النحوي لا يطابق الاستخدام |
| `NEEDS_ESCALATION` | تعارض في الشواهد لا يمكن حلّه |
