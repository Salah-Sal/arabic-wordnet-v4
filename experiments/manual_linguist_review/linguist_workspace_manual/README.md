# جمع الشواهد المعجمية اليدوي — Manual Dictionary Evidence Collection Workspace

> هذا المجلد يحتوي على كل ما يحتاجه المراجع لجمع الشواهد المعجمية **يدوياً** لمجموعات AWN4 الترادفية.
> This folder contains everything needed to collect dictionary evidence **manually** for AWN4 synsets.

---

## الإعداد السريع — Quick Setup

```bash
chmod +x setup.sh
./setup.sh
```

هذا سيربط قاعدة البيانات المعجمية ويتحقق من المتطلبات.
This links the dictionary database and verifies prerequisites.

> إذا لم يُعثر على القاعدة تلقائياً:
> ```bash
> ./setup.sh /path/to/arabic_dict.db
> ```

---

## سير العمل — Workflow

### ١. أنشئ الهيكل — Generate scaffold

```bash
python3 tools/scaffold_synset.py awn4-05162506-n
```

**المخرج:** `output/evidence/awn4-05162506-n.scaffold.yaml`
يحتوي: بيانات المجموعة الترادفية (من مكتبة wn) + هيكل فارغ مع تعليمات TODO لكل خطوة.

### ٢. استعلم من القاعدة — Query the database

```bash
sqlite3 "file:data/arabic_dict.db?mode=ro"

# إعداد التنسيق — Setup formatting
.mode column
.headers on
PRAGMA cache_size = -64000;
```

انسخ الاستعلامات من تعليقات TODO في الهيكل أو من `docs/MANUAL_GUIDE.md`.
Copy queries from scaffold TODO comments or from `docs/MANUAL_GUIDE.md`.

### ٣. املأ الهيكل — Fill the scaffold

الصق نتائج كل استعلام في القسم المناسب من ملف YAML.
Paste each query's results into the appropriate section of the YAML file.

### ٤. أعد التسمية — Rename when done

```bash
mv output/evidence/awn4-05162506-n.scaffold.yaml \
   output/evidence/awn4-05162506-n.evidence.yaml
```

---

## ابدأ من هنا — Starting Synsets

هذه المجموعات العشر تم معالجتها أيضاً بالخط الآلي (`linguist_workspace/`). ابدأ بها للمقارنة.
These 10 synsets were also processed by the automated pipeline. Start with them for comparison.

| # | Synset ID | POS | اللمّات — Lemmas | التعريف — Definition |
|---|-----------|-----|-----------------|---------------------|
| 1 | `awn4-02493953-v` | v | استشار / راجع / قابل | go to see for professional or business reasons |
| 2 | `awn4-00641523-a` | a | غير مصاب بالإمساك / منتظم الإخراج | not constipated |
| 3 | `awn4-02730750-n` | n | ترتيب / جهاز / معدّة | equipment designed to serve a specific function |
| 4 | `awn4-01953825-v` | v | طوّف / نقل بالطوف | transport on a raft |
| 5 | `awn4-00848000-s` | s | قابل للتشكيل / لدن | capable of being molded or modeled |
| 6 | `awn4-02248412-s` | s | مهروس / مجعّد | treated so as to have a permanently wrinkled appearance |
| 7 | `awn4-08770504-n` | n | سانتياغو / سانتياغو دي لوس كاباليروس | city in the northern Dominican Republic |
| 8 | `awn4-05223370-n` | n | حراجية / كثافة شجرية | the quality of abounding in trees |
| 9 | `awn4-00679361-s` | s | بالتبادل / كل ثان | every second one of a series |
| 10 | `awn4-01846632-v` | v | يأخذ / يستقل | travel or go by means of a certain kind of transportation |

```bash
# أنشئ الهياكل دفعة واحدة — Generate all scaffolds at once
python3 tools/scaffold_synset.py \
    awn4-02493953-v awn4-00641523-a awn4-02730750-n awn4-01953825-v \
    awn4-00848000-s awn4-02248412-s awn4-08770504-n awn4-05223370-n \
    awn4-00679361-s awn4-01846632-v
```

> المخرجات الآلية المقابلة موجودة في `../linguist_workspace/output/evidence/`.
> The corresponding automated outputs are in `../linguist_workspace/output/evidence/`.

---

## استعراض المجموعات الترادفية — Browse Synsets

```bash
python3 tools/extract_synset_wn.py awn4-05162506-n
python3 tools/extract_synset_wn.py --english "refuge" --pos n
python3 tools/extract_synset_wn.py --random 10 --min-lemmas 2
python3 tools/extract_synset_wn.py --stats
```

---

## هيكل المجلد — Folder Structure

```
linguist_workspace_manual/
│
├── README.md                 ← أنت هنا — You are here
├── setup.sh                  ← سكربت الإعداد — Setup script
│
├── docs/                     ← المواصفات المرجعية — Reference docs
│   ├── MANUAL_GUIDE.md              دليل خطوة بخطوة — Step-by-step guide
│   ├── DATABASE_SCHEMA.md           هيكل قاعدة البيانات — DB schema reference
│   ├── EVIDENCE_SCHEMA.yaml         مواصفات القطعة الشاهدية — Output schema
│   ├── COLLECTION_ALGORITHM.md      خوارزمية الجمع (٩ خطوات) — 9-step algorithm
│   ├── SQL_QUERIES.sql              قوالب SQL لكل خطوة — SQL templates
│   └── EXAMPLE_ARTIFACT.yaml        مثال عملي كامل — Worked example
│
├── tools/                    ← أدوات — Tools
│   ├── scaffold_synset.py           مولّد الهيكل (بلا DB) — Scaffold generator
│   ├── extract_synset_wn.py         استعراض المجموعات الترادفية — Synset browser
│   └── common_queries.sql           استعلامات SQL جاهزة — Ready-to-use SQL
│
├── templates/                ← قوالب — Templates
│   └── evidence_template.yaml       قالب YAML فارغ — Blank YAML template
│
├── data/                     ← البيانات (تُنشأ بعد setup.sh)
│   └── arabic_dict.db               قاعدة المعاجم (٧٦٠,٦٦٠ مدخلاً)
│
├── batches/                  ← دفعات المراجعة — Review batches
│   └── (batch files go here)
│
└── output/
    └── evidence/             ← مخرجات الجمع — Evidence artifacts
        └── {synset_id}.evidence.yaml
```

---

## المتطلبات — Prerequisites

| المتطلب | الوصف |
|---------|------|
| `sqlite3` | أداة سطر أوامر SQL (مثبتة افتراضياً على macOS/Linux) |
| `python3` | Python 3.8+ |
| `wn` | مكتبة Python WordNet — `pip install wn` |

### إعداد مكتبة wn — Setting up the wn library

```bash
pip install wn

# تحميل AWN4 (مرة واحدة فقط)
python3 -c "import wn; wn.add('path/to/awn4.xml')"

# تحميل OEWN للتعريفات الإنجليزية (مرة واحدة فقط)
python3 -c "import wn; wn.download('oewn:2024')"

# التحقق
python3 -c "import wn; print([l.specifier() for l in wn.lexicons()])"
# Expected: ['oewn:2024', 'awn4:4.0']
```

---

## المراجع — Reference Documents

| المستند | الوصف |
|---------|------|
| `docs/MANUAL_GUIDE.md` | **ابدأ هنا** — دليل خطوة بخطوة مع SQL جاهز |
| `docs/DATABASE_SCHEMA.md` | هيكل كل الجداول والأعمدة والفهارس |
| `docs/EVIDENCE_SCHEMA.yaml` | عقد المخرج: كل حقل في ملف YAML |
| `docs/SQL_QUERIES.sql` | كل قوالب SQL (نفس محتوى `tools/common_queries.sql`) |
| `docs/EXAMPLE_ARTIFACT.yaml` | مثال كامل على `awn4-05162506-n` |
| `docs/COLLECTION_ALGORITHM.md` | الخوارزمية الرسمية (شبه كود) |

---

## ملاحظات — Notes

- قاعدة البيانات **للقراءة فقط** — Database is read-only (`?mode=ro`)
- المخرج YAML خام — بلا أحكام أو تقييمات — Output is raw data, no judgments
- `scaffold_synset.py` **لا** يستعلم من القاعدة — يستخدم مكتبة `wn` فقط
- انظر `docs/MANUAL_GUIDE.md` §٣ لتتبع المعرّفات المستبعدة (`excluded_ids`)
