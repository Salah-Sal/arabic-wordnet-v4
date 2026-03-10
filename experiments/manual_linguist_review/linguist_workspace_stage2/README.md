# المرحلة الثانية — التحليل اللغوي اليدوي
# Stage 2 — Manual Linguistic Analysis

فضاء عمل لتحليل مجموعات المعنى (synsets) في شبكة الكلمات العربية AWN4 يدوياً.
يبني على الشواهد المعجمية المجمّعة في المرحلة الأولى (120,630 ملف مضغوط).

A workspace for manually analyzing AWN4 synsets. Builds on the lexicographic
evidence collected in Stage 1 (120,630 compressed evidence files from 107 Arabic
dictionaries).

---

## المتطلبات — Prerequisites

- Python 3.9+
- `pyyaml` (`pip install pyyaml`)
- Stage 1 evidence files in `../linguist_workspace/output/evidence/`

## الإعداد — Setup

```bash
cd linguist_workspace_stage2
./setup.sh
```

This verifies prerequisites, locates evidence files, and creates symlinks.

---

## سير العمل — Workflow

### 1. تجهيز المعطيات — Prepare a synset

```bash
python3 tools/prepare_synset.py awn4-01572394-v
```

Creates `output/awn4-01572394-v/` with:

| File | Description | الوصف |
|------|-------------|-------|
| `summary.md` | Evidence digest (2-5 pages) | ملخص الشواهد |
| `review.yaml` | Pre-filled review template | قالب مراجعة مسبق التعبئة |
| `evidence.yaml` | Raw evidence (for drill-down) | الشواهد الخام |

### 2. قراءة وتحليل — Read and analyze

Open `summary.md`. It contains:
- Hypernym chain and relations
- Per-lemma attestation, definitions, root family, synonym candidates, examples
- FTS and English bridge results
- Decision prompts (checklist)

### 3. تعبئة المراجعة — Fill review

Open `review.yaml` and fill in the decision fields following
[docs/STAGE2_GUIDE.md](docs/STAGE2_GUIDE.md).

### 4. التحقق — Validate

```bash
python3 tools/validate_review.py output/awn4-01572394-v/review.yaml
```

---

## الأدوات — Tools

| Tool | Usage | Description |
|------|-------|-------------|
| `prepare_synset.py` | `python3 tools/prepare_synset.py <id> [<id>...]` | Generate summary + review + evidence |
| `validate_review.py` | `python3 tools/validate_review.py <file>` | Validate completed review YAML |

### prepare_synset.py options

```
--batch FILE       Process synset IDs from a file (one per line)
--no-raw           Skip decompressing raw evidence.yaml
--evidence-dir DIR Override evidence directory path
--output-dir DIR   Override output directory (default: output/)
```

### validate_review.py options

```
--strict           Treat warnings as errors
```

---

## بنية المجلد — Folder Structure

```
linguist_workspace_stage2/
├── README.md                      ← أنت هنا / You are here
├── setup.sh                       الإعداد / Setup script
│
├── docs/
│   ├── STAGE2_GUIDE.md            دليل التحليل / Analysis guide
│   ├── REVIEW_SCHEMA.md           مخطط الحقول / Field reference
│   ├── SCORING_RUBRIC.md          معايير التقييم / Scoring criteria
│   └── EXAMPLE_REVIEW.yaml        مثال مكتمل / Completed example
│
├── templates/
│   └── review_template.yaml       قالب فارغ / Blank template
│
├── tools/
│   ├── prepare_synset.py          الأداة الرئيسية / Main tool
│   └── validate_review.py         أداة التحقق / Validation tool
│
├── batches/                       قوائم الدُّفعات / Batch lists
│
└── output/                        مجلدات العمل / Working directories
    └── {synset_id}/
        ├── summary.md
        ├── review.yaml
        └── evidence.yaml
```

---

## الوثائق — Documentation

| Document | Content |
|----------|---------|
| [STAGE2_GUIDE.md](docs/STAGE2_GUIDE.md) | Step-by-step decision algorithm |
| [REVIEW_SCHEMA.md](docs/REVIEW_SCHEMA.md) | Per-field documentation and valid values |
| [SCORING_RUBRIC.md](docs/SCORING_RUBRIC.md) | 5 scoring dimensions with rubric |
| [EXAMPLE_REVIEW.yaml](docs/EXAMPLE_REVIEW.yaml) | Completed review for awn4-01572394-v |

---

## معالجة الدُّفعات — Batch Processing

Create a text file with synset IDs (one per line):

```bash
# batches/sample.txt
awn4-01572394-v
awn4-03466051-n
awn4-02863805-a
```

Then:

```bash
python3 tools/prepare_synset.py --batch batches/sample.txt
```

Validate all completed reviews:

```bash
python3 tools/validate_review.py output/*/review.yaml
```
