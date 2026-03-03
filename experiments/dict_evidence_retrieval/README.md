# Dictionary Evidence Retrieval for AWN4 Synset Review

This experiment retrieves Arabic dictionary evidence for AWN4 (Arabic WordNet v4) synsets and produces structured linguist review documents. AWN4's 109,901 synsets were machine-translated from the English Open English WordNet (OEWN) by Google Gemini, with no confidence scores or quality metadata. This pipeline provides the evidence a human linguist needs to validate each translation.

## Directory Structure

```
dict_evidence_retrieval/
├── README.md                       ← this file
├── DEVLOG.md                       ← chronological development log
├── retrieve_dict_evidence.py       ← retrieval engine: 5 strategies + diagnostic report
├── generate_review_doc.py          ← linguist review document generator
└── output/
    ├── report.md                   ← engineering diagnostic report (strategy comparison)
    ├── results.json                ← raw retrieval results (JSON)
    └── reviews/                    ← per-synset linguist review documents
        ├── awn4-XXXXX-n.md         ← read-only reference for linguist
        └── awn4-XXXXX-n.yaml       ← structured decision sidecar
```

## Architecture

### Data Sources

| Source | Description | Size |
|--------|-------------|------|
| **AWN4 XML** (`output/awn4.xml`) | 109,901 synsets in WN-LMF 1.4 format; 97.2% have ILI cross-links to OEWN | ~60 MB |
| **Arabic Dictionary DB** (`arabic-dictionaries/db/arabic_dict.db`) | 760K entries across 107 dictionaries (3 source types: OCR, Hawramani, ARABTERM) | ~2.1 GB |
| **ColBERT PLAID Index** (`experiments/colbertv2 exp/`) | Semantic search index over dictionary entries using `jinaai/jina-colbert-v2` | ~1.5 GB |
| **OEWN** (via `wn` library) | English source definitions, lemmas, and examples looked up by ILI | installed package |

### Dictionary Source Types

| Type | Period | Content |
|------|--------|---------|
| **Hawramani** | Classical + Modern | 65+ dictionaries scraped from hawramani.com; includes Lisan al-Arab, Taj al-Arus, Al-Wasit, etc. |
| **OCR** | Classical + Modern | Academy dictionaries (Al-Wasit, Al-Kabir) and classical texts (Kitab Al-Ayn, Maqayis) digitized via OCR |
| **ARABTERM** | Modern | 417K multilingual terminology entries from the Arab League's ArabTerm platform (Arabic/English/French) |

### Retrieval Pipeline

Both scripts share the same 5-strategy retrieval pipeline. The strategies are designed to be complementary — each catches evidence the others miss:

```
AWN4 Synset (lemmas + definition + ILI)
    │
    ├─ Strategy A: Headword Match (SQL Tier 1)
    │   Exact headword_norm lookup for each Arabic lemma.
    │   Uses normalize_arabic() which strips diacritics + normalizes hamza/alef.
    │   Fast, high-precision, but misses morphological variants.
    │
    ├─ Strategy B: Root Family (SQL Tier 2)
    │   Extracts Arabic roots from Strategy A entries, then finds all entries
    │   sharing those roots (excluding A's entry_ids). Captures morphological
    │   relatives: e.g., مول → تمويل, أموال, مالي.
    │   Depends on A's output (chained, not parallel).
    │
    ├─ Strategy C: Definition Search (FTS5 BM25)
    │   Extracts Arabic keywords from the synset definition, searches via
    │   SQLite FTS5 full-text index. Finds entries with similar definitions
    │   but different headwords. Excludes A+B entry_ids.
    │
    ├─ Strategy D: ColBERT Semantic Search (optional)
    │   3 sub-queries (lemma, definition, combined) against a PLAID index
    │   built with jinaai/jina-colbert-v2. Finds semantically related entries
    │   that keyword methods miss. Requires ~4s per synset on CPU.
    │
    └─ Strategy E: Translation Bridge (ARABTERM)
        Uses ILI to look up English OEWN lemmas, then searches ARABTERM's
        English translation field via FTS5. Bridges English→Arabic via
        bilingual terminology. Excludes A+B+C entry_ids.
```

### Evidence Classification

Each retrieved entry is classified into evidence types:

| Type | Condition | Meaning |
|------|-----------|---------|
| `lemma_match` | Headword normalizes to a synset lemma | Direct attestation of the word |
| `definition_support` | Definition similarity > 0.15 and headword matches | Dictionary confirms this meaning |
| `synonym_candidate` | Definition similarity > 0.30, headword differs, POS compatible | Potential missing synonym |
| `morphological_kin` | Shares root but different headword | Related word from same root |
| `translation_bridge` | Has English translation field | Cross-lingual evidence via ARABTERM |
| `contextual` | None of the above | Tangentially related |

Similarity is computed by `rag.similarity.definition_similarity()` using character n-gram Jaccard overlap, optimized for Arabic text.

---

## Scripts

### `retrieve_dict_evidence.py` — Retrieval Engine

Runs all 5 strategies on selected synsets and produces an **engineering diagnostic report** comparing strategy effectiveness.

```bash
# 10 diverse synsets, all strategies
python retrieve_dict_evidence.py

# SQL-only (skip ColBERT, much faster)
python retrieve_dict_evidence.py --no-colbert

# Specific synsets
python retrieve_dict_evidence.py --synset-ids awn4-13271441-n awn4-00534261-n

# Custom count and seed
python retrieve_dict_evidence.py --count 20 --seed 99
```

**Output:** `output/report.md` (per-synset strategy comparison tables) + `output/results.json` (raw data).

### `generate_review_doc.py` — Linguist Review Documents

Produces **linguist-facing** review documents: a bilingual `.md` reference and a `.yaml` decision sidecar per synset.

```bash
# Generate for specific synsets (SQL-only, fast)
python generate_review_doc.py --synset-ids awn4-13271441-n --no-colbert

# Generate for specific synsets (with ColBERT semantic search)
python generate_review_doc.py --synset-ids awn4-13271441-n

# Batch: 10 diverse synsets
python generate_review_doc.py --count 10 --seed 42 --no-colbert

# Custom output directory
python generate_review_doc.py --synset-ids awn4-13271441-n --output-dir output/batch1/
```

**CLI flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--synset-ids` | — | Specific synset IDs to process |
| `--count` | 10 | Number of diverse synsets to randomly select |
| `--seed` | 42 | Random seed for reproducible selection |
| `--output-dir` | `output/reviews/` | Where to write .md + .yaml files |
| `--no-colbert` | false | Skip ColBERT (SQL-only, ~0.5s/synset vs ~7s with ColBERT) |
| `--device` | `cpu` | PyTorch device for ColBERT (`cpu`, `mps`, `cuda`) |
| `--awn4-xml` | auto | Path to awn4.xml |
| `--dict-db` | auto | Path to arabic_dict.db |

---

## Review Document Format

### `.md` — Reference Document (5 sections)

**Section 1: Synset Overview** — Side-by-side 3-column comparison table (Field | English OEWN | Arabic AWN4) showing definition, lemmas, and examples. Named Entity synsets (detected via `instance_hypernym` relation) display a warning badge noting that semantic search results may reflect phonetic rather than semantic similarity.

**Section 2: Per-Lemma Dictionary Evidence** — For each Arabic lemma in the synset:
- **Attestation summary**: number of dictionary entries and dictionaries found
- **Root information**: Arabic root(s) with source attribution (CAMeL morphological analyzer or OCR-extracted)
- **Core dictionary definitions** (all entries): sorted by match quality (exact headword first) then dictionary authority (classical → modern OCR → modern Hawramani → ARABTERM). Full definitions shown without truncation.
- **Root family** (non-ARABTERM with definitions): morphologically related words sharing the same root
- **Synonym candidates**: entries with different headwords but similar definitions (similarity > 0.30)
- **ARABTERM translations**: English/French glosses from the bilingual terminology database

**Section 3: Semantic Evidence (ColBERT-only)** — Entries found *only* by neural semantic search, not by any keyword strategy. These can reveal better Arabic alternatives that keyword methods miss. Named Entity synsets display a phonetic-similarity warning.

**Section 4: Connected Synsets** — Hypernyms, hyponyms, and other semantic relations, each with bilingual tables showing Arabic (AWN4) and English (OEWN) equivalents.

**Section 5: Review Instructions** — Bilingual checklist of what to review and pointer to the YAML sidecar.

### `.yaml` — Decision Sidecar

Pre-populated structure the linguist fills in:

```yaml
synset_id: awn4-XXXXX-n
reviewer: ""
review_date: ""
status: pending          # pending | in_progress | completed

definition:
  verdict: ""            # accept | revise | reject
  revised_text: ""
  notes: ""

lemmas:
  - lemma: "كتاب"
    verdict: ""          # accept | remove | modify
    modified_form: ""
    notes: ""

missing_lemmas: []       # linguist adds after reviewing synonym candidates in .md
# - lemma: "سِفْر"
#   source: "dictionary name"
#   notes: ""

examples:
  verdict: ""            # accept | revise | remove | add
  revised_examples: []
  notes: ""

cultural_fit:
  needs_adaptation: false
  notes: ""

overall:
  confidence: ""         # high | medium | low
  general_notes: ""
```

The `missing_lemmas` section starts empty. The linguist adds entries after reviewing the "Synonym Candidates" table in the `.md` reference document.

---

## Implementation Details

### Key Design Decisions

**Monkey-patching `_row_to_dict`**: `generate_review_doc.py` imports `retrieve_dict_evidence.py` and monkey-patches its `_row_to_dict` function to pass full definition text (no truncation) and add `dict_name_ar` and `root_source` fields. This avoids modifying the original retrieval script.

**Two-pass AWN4 parsing**: `parse_awn4()` (from `retrieve_dict_evidence.py`) collects synsets and lemmas. `parse_awn4_relations()` (in `generate_review_doc.py`) does a second iterparse pass for `<SynsetRelation>` elements. This avoids modifying the shared parser.

**Headword match quality sorting**: Arabic hamza normalization (أ→ا) can conflate unrelated words (e.g., مأل "fatness" → مال "money"). The sort uses a 2-level key: `(match_quality, authority_level)` where exact `headword_bare` matches rank above normalized-only matches.

**Per-lemma evidence merging**: Strategy results are flat lists. `merge_evidence_by_lemma()` reorganizes them:
- Strategy A entries → matched by normalized headword; prefix-stripped entries routed via `_original_lemma`
- Strategy B entries → matched by shared root (via `root_to_lemma` mapping from A)
- Strategy C/D entries → classified for synonym candidates (with POS compatibility check)
- Strategy E entries → matched by headword to appropriate lemma

**Empty definition filtering**: Core Dictionary tables only show entries with non-empty `definitions_text`. Entries attested by headword but with no definition text are summarized in a compact "Also attested in" line, preserving the attestation count while eliminating blank table rows.

**MWE stop-word filter**: Multi-word lemmas are split into content words for individual lookup. Words are filtered by both length (`> 2` chars) and membership in `ARABIC_STOPWORDS` (37-entry frozenset from `rag.similarity` covering function words like غير, كل, بعض, بين).

**Definition truncation**: Long definitions are truncated at word boundaries (500-char limit) with " …" appended. Applied at render time in Core Dictionary, Root Family, Synonym Candidates, and ColBERT-only tables. Full text is preserved in the data layer (monkey-patch passes complete definitions).

**POS compatibility filter**: Synonym candidates are checked against the synset's POS. Conservative: only entries with explicit, mismatching POS are excluded (e.g., noun entries for verb synsets). Entries with NULL/empty POS are kept. The DB has clean POS values for ~108K entries (noun, verb, adj, proper_noun).

**Proclitic prefix stripping**: Adverb lemmas with zero Strategy A results that start with a single-character Arabic proclitic (ب, ك, ل, ف, و) trigger a fallback lookup on the stripped base form. Results are rendered in a separate "Prefix-stripped matches" sub-section with an explanatory note.

### Dependencies

| Package | Used for |
|---------|----------|
| `wn` | OEWN English data lookup via ILI |
| `pyyaml` | YAML sidecar generation |
| `colbert-ai` | ColBERT semantic search (optional, for Strategy D) |
| `torch` | ColBERT model inference (optional) |

The RAG pipeline modules (`rag.db`, `rag.retrieval`, `rag.similarity`, `common`) are imported from `arabic-dictionaries/extraction/`.

### Performance

| Mode | Time per synset | Notes |
|------|----------------|-------|
| SQL-only (`--no-colbert`) | ~0.5s | Strategies A, B, C, E |
| With ColBERT | ~7s (CPU) | All 5 strategies; ~3s on MPS/CUDA |
| AWN4 parsing | ~1.8s | One-time cost (109K synsets) |
| Relations parsing | ~1.4s | One-time cost (271K relations) |
