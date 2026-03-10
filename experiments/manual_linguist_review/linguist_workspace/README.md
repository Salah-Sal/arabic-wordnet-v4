# جمع الشواهد المعجمية — Dictionary Evidence Collection Workspace

> هذا المجلد يحتوي على كل ما يحتاجه المراجع لجمع الشواهد المعجمية لمجموعات AWN4 الترادفية.
> This folder contains everything needed to collect dictionary evidence for AWN4 synsets.

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

### جمع الشواهد لمجموعة واحدة — Single synset

```bash
python3 tools/collect_evidence.py awn4-05162506-n
```

**المخرج:** `output/evidence/awn4-05162506-n.evidence.yaml`

### جمع دفعة كاملة — Batch collection

```bash
# أنشئ دفعة عشوائية — Create a random batch
python3 tools/extract_synset_wn.py --random 20 --pos n --min-lemmas 2 \
    --compact -o batches/nouns_batch1.txt

# نفّذ الجمع — Run collection
python3 tools/collect_evidence.py --batch batches/nouns_batch1.txt
```

### استعراض مجموعة ترادفية — Browse a synset

```bash
python3 tools/extract_synset_wn.py awn4-05162506-n
python3 tools/extract_synset_wn.py --english "refuge" --pos n
python3 tools/extract_synset_wn.py --stats
```

### استعلام تفاعلي — Interactive SQL

```bash
sqlite3 "file:data/arabic_dict.db?mode=ro"

# إعداد التنسيق — Setup formatting
.mode column
.headers on
PRAGMA cache_size = -64000;

# انظر tools/common_queries.sql للاستعلامات الجاهزة
# See tools/common_queries.sql for ready-to-use queries
```

---

## هيكل المجلد — Folder Structure

```
linguist_workspace/
│
├── README.md                 ← أنت هنا — You are here
├── setup.sh                  ← سكربت الإعداد — Setup script
│
├── docs/                     ← المواصفات المرجعية — Reference specs
│   ├── EVIDENCE_SCHEMA.yaml          مواصفات القطعة الشاهدية
│   ├── COLLECTION_ALGORITHM.md       خوارزمية الجمع (٩ خطوات)
│   ├── SQL_QUERIES.sql               قوالب SQL لكل خطوة
│   └── EXAMPLE_ARTIFACT.yaml         مثال عملي كامل
│
├── tools/                    ← أدوات — Tools
│   ├── collect_evidence.py           أداة الجمع الآلي (الأداة الرئيسية)
│   ├── extract_synset_wn.py          استعراض المجموعات الترادفية
│   └── common_queries.sql            استعلامات SQL جاهزة للنسخ
│
├── data/                     ← البيانات (تُنشأ بعد setup.sh)
│   └── arabic_dict.db                قاعدة المعاجم (٧٦٠,٦٦٠ مدخلاً)
│
├── batches/                  ← دفعات المراجعة — Review batches
│   └── (batch files go here)
│
└── output/
    └── evidence/             ← مخرجات الجمع — Evidence artifacts
        └── {synset_id}.evidence.yaml
```

---

## أداة الجمع — collect_evidence.py

الأداة الرئيسية. تنفّذ خوارزمية الجمع من ٩ خطوات وتنتج ملف YAML لكل مجموعة ترادفية.
Main tool. Runs the 9-step collection algorithm and produces a YAML artifact per synset.

```bash
# مجموعة واحدة — Single synset
python3 tools/collect_evidence.py awn4-05162506-n

# عدة مجموعات — Multiple synsets
python3 tools/collect_evidence.py awn4-05162506-n awn4-03466051-n

# من ملف دفعة — From batch file
python3 tools/collect_evidence.py --batch batches/my_batch.txt

# مجلد مخرجات مخصص — Custom output directory
python3 tools/collect_evidence.py --output-dir output/evidence awn4-05162506-n

# مسار قاعدة بيانات مخصص — Custom DB path
python3 tools/collect_evidence.py --db data/arabic_dict.db awn4-05162506-n
```

### ماذا تجمع؟ — What does it collect?

لكل لمّة (per lemma):
- **الخطوة ١:** مطابقة العنوان (ال-aware) — Headword lookup
- **الخطوة ٢:** التعريفات المهيكلة — Structured definitions
- **الخطوة ٣:** عائلة الجذر — Root family
- **الخطوة ٦:** الشواهد والأمثلة — Examples
- **الخطوة ٧:** الترتيب الزمني — Chronological ordering
- **الخطوة ٨:** البحث العكسي (FTS) — Reverse lookup

لكل مجموعة (per synset):
- **الخطوة ٤:** البحث النصي الكامل — FTS keyword search
- **الخطوة ٥:** الجسر الإنجليزي (ARABTERM) — English bridge
- **الخطوة ٩:** التصفية التخصصية — Specialized filtering

---

## المتطلبات — Prerequisites

| المتطلب | الوصف |
|---------|------|
| `sqlite3` | أداة سطر أوامر SQL (مثبتة افتراضياً على macOS/Linux) |
| `python3` | Python 3.8+ |
| `wn` | مكتبة Python WordNet — `pip install wn` |
| `pyyaml` | مكتبة Python YAML — `pip install pyyaml` |

### إعداد مكتبة wn — Setting up the wn library

```bash
pip install wn pyyaml

# تحميل AWN4 (مرة واحدة فقط)
python3 -c "import wn; wn.add('path/to/awn4.xml')"

# تحميل OEWN للتعريفات الإنجليزية (مرة واحدة فقط)
python3 -c "import wn; wn.download('oewn:2024')"

# التحقق
python3 -c "import wn; print([l.specifier() for l in wn.lexicons()])"
# Expected: ['oewn:2024', 'awn4:4.0']
```

---

## ملاحظات — Notes

- قاعدة البيانات **للقراءة فقط** — Database is read-only
- المخرج YAML خام — بلا أحكام أو تقييمات — Output is raw data, no judgments
- انظر `docs/EVIDENCE_SCHEMA.yaml` لمواصفات المخرج الكاملة
- انظر `docs/EXAMPLE_ARTIFACT.yaml` لمثال عملي على synset awn4-05162506-n
