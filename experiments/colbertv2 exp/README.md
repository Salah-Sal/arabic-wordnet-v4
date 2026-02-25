# ColBERTv2 Multilingual Semantic Search

Indexes Arabic WordNet 4 (AWN4), Open English WordNet (OEWN), Arabic classical/modern dictionary entries, and ARABTERM multilingual technical terms into a single ColBERTv2 index for unified semantic retrieval. A query in Arabic or English returns the most relevant results from **all four sources**, with cross-lingual references via the Interlingual Index (ILI).

Includes a **Flask + HTMX web UI** for browser-based search with filters, result cards, and statistics dashboard.

| | |
|---|---|
| **Date** | 2026-02-25 |
| **Script** | `colbert_index.py` |
| **Model** | Jina-ColBERT-v2 (560M params, XLM-RoBERTa backbone) |
| **Index backend** | Voyager (HNSW, CPU) or PLAID (GPU) |
| **Corpus** | ~758K documents (110K AWN4 + 121K OEWN + 110K dict + 417K ARABTERM) |
| **Status** | Production index built — 758K documents indexed |

---

## Table of Contents

- [Motivation](#motivation)
- [Architecture](#architecture)
- [Environment Setup](#environment-setup)
- [Usage](#usage)
- [Web UI](#web-ui)
- [Data Sources](#data-sources)
- [Model Details](#model-details)
- [Index Backends](#index-backends)
- [Output Files](#output-files)
- [Performance](#performance)
- [Results](#results)
- [Troubleshooting](#troubleshooting)
- [Reference Repos](#reference-repos)

---

## Motivation

AWN4 contains 109,901 synsets, each with Arabic lemmas and definitions. The polysemy disambiguation pipeline (Stage 2) currently finds dictionary evidence via **exact string matching** on normalized headwords — only 53.1% of polysemy groups get any evidence at all.

ColBERTv2's token-level late interaction (MaxSim) enables **semantic retrieval**: a query like "عقد" can retrieve entries about "تعاقد", "معاقدة", "عقود" through subword-level matching. This experiment builds a general-purpose multilingual retrieval system that:

1. Searches synsets, dictionary definitions, and technical terms by meaning, not just surface form
2. Works across Arabic and English in a single unified index
3. Links results cross-lingually via ILI (e.g., Arabic "قادر" ↔ English "able")
4. Enables cross-lingual discovery via ARABTERM's trilingual lemmas (Arabic/English/French)

---

## Architecture

```
colbert_index.py
│
├── Phase 1: Parse AWN4 XML ──→ 109,901 Arabic SynsetRecords
│       (iterparse + elem.clear(), reuses prefilter_dict.py pattern)
│
├── Phase 2a: Load OEWN ──→ 120,630 English SynsetRecords
│       (via wn Python package)
│
├── Phase 2b: Load Arabic dictionaries ──→ 109,769 dict SynsetRecords
│       (22 classical/modern sources from arabic_dict.db)
│
├── Phase 2c: Load ARABTERM ──→ 417,278 arabterm SynsetRecords
│       (51 multilingual technical dictionaries, trilingual AR/EN/FR lemmas)
│
├── Phase 3: Build corpus ──→ unified document list + metadata
│       Document format: "{lemmas} | {definition} | {examples}"
│
├── Phase 4: Encode ──→ multi-vector embeddings (128-dim per token)
│       (Jina-ColBERT-v2 via PyLate, chunked with disk cache)
│
├── Phase 5: Build index ──→ Voyager HNSW or PLAID IVF index
│
└── Phase 6: Search ──→ ranked results with metadata + ILI cross-refs
        (CLI search, interactive REPL, or Flask web UI)
```

Each document becomes one text string:
```
قادر; مستطيع | يمتلك الوسائل أو المهارة اللازمة للقيام بشيء ما | قادر على السباحة
```

ARABTERM entries include trilingual lemmas for cross-lingual retrieval:
```
عقد; contract; contrat | [Commerce and Accounting]
```

Arabic lemmas are stripped of diacritics in the document text to match typical undiacritized queries. Definitions are kept as-is.

---

## Environment Setup

### Prerequisites

- **Python 3.9+** (tested with 3.9.6 and 3.12; PyLate requires >= 3.9)
- **macOS** (Apple Silicon or Intel) or **Linux**
- ~6 GB disk space for the Jina-ColBERT-v2 model download
- ~8 GB RAM minimum for encoding on CPU

### Step 1: Virtual environment

You have two options:

#### Option A: Use the project-level venv (recommended if it exists)

The project-level venv at `wn-project/venv/` already has PyLate, torch, and all ML dependencies installed from the index build. This avoids duplicating ~2 GB of torch.

```bash
# From the project root (wn-project/)
source venv/bin/activate

# Install Flask if not already present
pip install flask
```

#### Option B: Create a dedicated venv (clean isolation)

If you prefer full isolation, create a dedicated venv inside the experiment directory. This duplicates torch/PyLate but keeps the experiment fully self-contained.

```bash
# From the experiment directory
cd "experiments/colbertv2 exp"

# Create a fresh venv
python3 -m venv .venv
source .venv/bin/activate

# Verify Python version
python --version
# Should be 3.9+ (3.9.6, 3.10.x, 3.11.x, or 3.12.x all work)
```

If you need a specific Python version:
```bash
# macOS with Homebrew
brew install python@3.12
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install core dependencies (Option B only)

If you used Option A (project-level venv), these are already installed — just run `pip install flask` if needed. For Option B (dedicated venv), install everything:

```bash
# Core: PyLate (includes sentence-transformers, fast-plaid, voyager, torch)
pip install pylate==1.3.4

# Jina model dependency (not pulled automatically by pylate)
pip install einops>=0.8.1

# English WordNet loader
pip install wn==0.13.0

# Progress bars
pip install tqdm

# Web UI
pip install flask
```

### Step 3: Fix potential numpy/scipy conflict

If you see `AttributeError: module 'numpy.random' has no attribute 'mtrand'`:

```bash
pip install --force-reinstall numpy==1.26.4 scipy==1.13.1
```

### Step 4: Download English WordNet data (one-time)

```bash
python -c "import wn; wn.download('oewn:2024')"
```

This downloads OEWN 2024 (~40 MB) into wn's internal SQLite database at `~/.wn_data/wn.db`.

If you see a `DatabaseError` about schema incompatibility:
```bash
rm ~/.wn_data/wn.db
python -c "import wn; wn.download('oewn:2024')"
```

### Step 5: Verify installation

```bash
python -c "
from pylate import models, indexes, retrieve
import wn
import flask
print('PyLate OK')
print(f'OEWN synsets: {len(wn.synsets(lang=\"en\")):,}')
print(f'Flask: {flask.__name__}')
print('All good.')
"
```

Expected output:
```
PyLate OK
OEWN synsets: 120,630
Flask: flask
All good.
```

### Complete dependency table

These are the exact versions tested and confirmed working:

| Package | Version | Role |
|---------|---------|------|
| `python` | 3.9.6+ | Runtime |
| `pylate` | 1.3.4 | ColBERT model + indexing framework |
| `sentence-transformers` | 5.1.1 | Base framework (pulled by pylate) |
| `torch` | 2.8.0 | Tensor operations, model inference |
| `transformers` | 4.43.4 | HuggingFace model loading (range: >=4.41.0, <=4.56.2) |
| `einops` | 0.8.2 | Required by Jina's custom model code |
| `voyager` | 2.1.0 | HNSW index backend |
| `fast-plaid` | 1.2.4.280 | Rust-based PLAID index backend |
| `numpy` | 1.26.4 | Numerical operations |
| `scipy` | 1.13.1 | Required by scikit-learn (transitive) |
| `wn` | 0.13.0 | Open English WordNet loader |
| `flask` | 3.1.3 | Web UI server |
| `tqdm` | any | Progress bars (optional) |

### requirements.txt

For reproducibility, a `requirements.txt`:

```
pylate==1.3.4
einops>=0.8.1
wn==0.13.0
flask>=3.0
tqdm
numpy==1.26.4
scipy==1.13.1
```

Install with:
```bash
pip install -r requirements.txt
```

---

## Usage

Always activate the virtual environment first:

```bash
cd "experiments/colbertv2 exp"
source .venv/bin/activate
```

### Build the index

```bash
# Test build (100 entries per source = 400 docs, ~50 seconds)
python colbert_index.py build --limit 100

# Full build (all ~758K documents, ~6+ hours on CPU for encoding)
python colbert_index.py build

# Synsets only (backward-compatible, skip dict + ARABTERM)
python colbert_index.py build --synsets-only

# Skip specific sources
python colbert_index.py build --no-dict --no-arabterm
python colbert_index.py build --no-english

# Use GPU (if available)
python colbert_index.py build --device cuda --backend plaid
```

| Flag | Default | Description |
|------|---------|-------------|
| `--limit N` | 0 (all) | Limit entries per source |
| `--batch-size N` | 8 | Encoding batch size (lower = less RAM) |
| `--backend` | voyager | Index backend: `voyager` (CPU) or `plaid` (GPU) |
| `--device` | cpu | PyTorch device: `cpu`, `cuda`, or `mps` |
| `--no-english` | false | Skip English WordNet |
| `--no-dict` | false | Skip Arabic dictionary entries |
| `--no-arabterm` | false | Skip ARABTERM technical terms |
| `--synsets-only` | false | Only index AWN4 + OEWN (shorthand for `--no-dict --no-arabterm`) |
| `--force-encode` | false | Re-encode even if embedding cache exists |

**Embedding cache**: After the first build, embeddings are saved to `embeddings/`. The cache filename reflects which sources are included (e.g., `embeddings_awn_oewn_dict_at.pkl`). Subsequent builds skip encoding and only rebuild the index. Use `--force-encode` to re-encode.

### Search (CLI)

```bash
# Arabic query
python colbert_index.py search "عقد قانوني"

# English query
python colbert_index.py search "contract law"

# Cross-lingual: Arabic query, English results only
python colbert_index.py search "عقد" --lang en

# Filter by POS
python colbert_index.py search "رفع" --pos v --k 20

# Filter by source type
python colbert_index.py search "عقد" --source dict
python colbert_index.py search "transport" --source arabterm
```

| Flag | Default | Description |
|------|---------|-------------|
| `--k N` | 10 | Number of results |
| `--lang` | all | Filter: `ar`, `en`, or `all` |
| `--pos` | none | Filter: `n`, `v`, `a`, or `r` |
| `--source` | all | Filter: `synset`, `dict`, `arabterm`, or `all` |
| `--backend` | voyager | Must match the backend used during build |
| `--device` | cpu | PyTorch device for query encoding |

### Interactive mode

```bash
python colbert_index.py interactive
```

Commands in interactive mode:
```
> عقد                           # search
> contract                      # search
> :k 20                         # change result count
> :lang ar                      # filter to Arabic only
> :lang all                     # reset language filter
> :pos n                        # filter to nouns
> :pos none                     # clear POS filter
> :source dict                  # filter to dictionary entries only
> :source arabterm              # filter to ARABTERM only
> :source all                   # reset source filter
> :quit                         # exit
```

---

## Web UI

A browser-based search interface built with **Flask + HTMX**, matching the styling of the `arabic-dictionaries` web app (warm brown/gold theme, RTL Arabic layout, Noto Naskh Arabic font).

### Launch

```bash
# Via CLI subcommand (recommended)
python colbert_index.py serve

# With custom port
python colbert_index.py serve --port 8080

# Or directly
cd web && python app.py
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 5002 | HTTP port |
| `--backend` | voyager | Index backend |
| `--device` | cpu | PyTorch device |
| `--debug` | false | Flask debug mode (no auto-reloader) |

The server loads the model (~3.5s), index, and metadata at startup. Wait for the terminal to show `Starting web UI on http://localhost:5002` before opening the browser.

### Features

- **Semantic search**: type Arabic or English queries — results ranked by ColBERT MaxSim score
- **Filters**: language (AR/EN/all), POS (noun/verb/adj/adv), source type (synset/dict/ARABTERM), result count (10/20/50)
- **Result cards**: rank, score, color-coded source badge, language badge, POS badge, lemmas, definition snippet, cross-lingual references
- **Expandable detail**: click "تفاصيل / Details" on any result to lazy-load full metadata and all ILI-linked cross-references via HTMX
- **Statistics dashboard**: document counts by source/language/POS, bar charts, system info (model, backend, file sizes)
- **Bookmarkable URLs**: filter state is preserved in URL query parameters via `hx-push-url`
- **RTL-aware**: Arabic text renders right-to-left, English left-to-right, using `dir="auto"` auto-detection
- **Loading indicator**: CSS spinner shown during the 1-2s search time

### Architecture

```
web/
├── app.py               # Flask app — imports colbert_index.py, loads singletons at startup
├── templates/
│   ├── base.html        # RTL base template (Noto Naskh Arabic, HTMX 2.0.4)
│   ├── index.html       # Search page with form, filters, hero stats
│   ├── _results.html    # HTMX partial — result cards (swapped into #results div)
│   ├── _detail.html     # HTMX partial — expanded metadata (loaded on click)
│   └── stats.html       # Statistics dashboard with bar charts
└── static/
    └── style.css        # Warm brown/gold CSS theme (~400 lines)
```

The Flask app wraps `colbert_index.py` functions directly — no code duplication:
- `ci.load_model()`, `ci.load_index()`, `ci.load_metadata()` — called once at startup
- `ci.search()` — called per request, returns the same `list[dict]` as the CLI

Single-threaded (`threaded=False`) because search is CPU-bound (torch inference). The reloader is always disabled (`use_reloader=False`) to avoid loading the 2GB model twice.

---

## Data Sources

### Arabic WordNet 4 (AWN4)

- **File**: `../../output/awn4.xml` (72 MB, WN-LMF 1.4 format)
- **Documents**: 109,901 synsets
- **Lemma entries**: 166,785 (124,768 unique LexicalEntry elements)
- **Fields**: ID, ILI, POS, Arabic definition, Arabic examples (0-4), Arabic lemmas (1-N)
- **ILI coverage**: All 109,901 synsets have ILI links to OEWN
- **Source type**: `synset`

### Open English WordNet (OEWN 2024)

- **Source**: Loaded via `wn` Python package (`wn.download("oewn:2024")`)
- **Documents**: 120,630 synsets
- **Fields**: ID, ILI, POS, English definition, English examples, English lemmas
- **ILI**: Links directly to AWN4 synsets via shared ILI identifiers
- **Source type**: `synset`

### Arabic Dictionaries

- **Database**: `arabic-dictionaries/db/arabic_dict.db` (308 MB SQLite)
- **Documents**: 109,769 entries from 22 classical/modern Arabic dictionaries
- **Sources**: Al-Waseet, Lisan al-Arab, Maqayis al-Lugha, Taj al-Arus, and 18 others
- **Fields**: headword, root, POS, definitions, examples, plurals, cross-references
- **POS mapping**: dict POS (noun/verb/adj/proper_noun/phrase/particle/root/other) → ColBERT codes (n/v/a/r)
- **Source type**: `dict`

### ARABTERM Technical Terms

- **Database**: Same `arabic_dict.db`, `arabterm_terms` table
- **Documents**: 417,278 multilingual technical terms from 51 domain dictionaries
- **Languages**: Arabic, English, French (trilingual lemmas enable cross-lingual retrieval)
- **Domains**: Commerce, Medicine, Agriculture, IT, Law, Military, and 45 others
- **Fields**: arabic, english, french, description, domain
- **Definition fallback**: entries without descriptions use `[domain]` as definition tag
- **Source type**: `arabterm`

### Cross-lingual linking

Synsets carry ILI (Interlingual Index) values. When searching, results include cross-references:

```
  1. [ar|synset] awn4-00001740-a  score=20.21
     Lemmas: قَادِر; مُسْتَطِيع
     Def: يمتلك الوسائل أو المهارة...
     ↔ EN: able (i1)              ← cross-lingual reference via ILI
```

ARABTERM entries enable cross-lingual discovery through trilingual lemmas:
```
  2. [ar|arabterm] at-55345  (n)  score=19.87
     Lemmas: عقد; contract; contrat
     Def: [Commerce and Accounting]
```

The `ili_map.json` maps each ILI to its synset IDs in both languages.

---

## Model Details

### Jina-ColBERT-v2 (`jinaai/jina-colbert-v2`)

| Property | Value |
|----------|-------|
| Parameters | 560M |
| Backbone | XLM-RoBERTa (custom Jina implementation) |
| Embedding dimension | 128 per token |
| Matryoshka dimensions | 128 / 96 / 64 |
| Max sequence length | 8,194 tokens |
| Languages | 89 (Arabic is one of 8 priority languages) |
| Training data | MS MARCO + multilingual pairs with explicit Arabic stages |
| License | CC BY-NC 4.0 |
| HuggingFace | `jinaai/jina-colbert-v2` |
| Download size | ~2.2 GB |
| `trust_remote_code` | Required (Jina hosts custom model code) |

### Why Jina-ColBERT-v2

- **Cross-lingual alignment**: Arabic and English occupy the same embedding space, enabling cross-lingual search in a single index
- **Arabic priority**: Arabic is one of 8 languages receiving additional training stages (not just incidentally covered by multilingual pre-training)
- **Best documented Arabic performance**: Outperforms BM25, mDPR, and ColBERT-XM on MIRACL Arabic
- **Token-level matching**: ColBERT's MaxSim operation captures Arabic morphological variants through subword interactions — a query "عقد" matches documents containing "تعاقد", "معاقدة", "عقود"

### Alternatives considered

| Model | Params | Arabic | Bilingual | Why not chosen |
|-------|--------|--------|-----------|----------------|
| `colbert-ir/colbertv2.0` | 110M | None | No | English-only BERT backbone |
| `akhooli/Arabic-ColBERT-100K` | 110M | Arabic-only | No | No English support, no published benchmarks |
| `antoinelouis/colbert-xm` | 277M | Zero-shot | Yes | Smaller but 514-token limit, no Arabic training |
| `answerdotai/answerai-colbert-small-v1` | 33M | None | No | English-only ModernBERT backbone |

---

## Index Backends

### Voyager (default)

- **Algorithm**: HNSW (Hierarchical Navigable Small World)
- **Library**: Spotify's Voyager (`voyager` package)
- **CPU-friendly**: Full functionality on CPU, no GPU required
- **Parameters**: `M=64`, `ef_construction=200`, `ef_search=500`
- **Storage**: SQLite-backed document ID mapping + Voyager binary index
- **Search flow**: Voyager retrieves token-level candidates → PyLate reranks with full MaxSim
- **Cross-lingual note**: Token-level HNSW clusters embeddings by language, so cross-lingual filtering (e.g., Arabic query → English results) uses aggressive over-retrieval (`k_token=500`, `k×50`) to compensate. English→Arabic works better than Arabic→English due to script-level token proximity. PLAID's centroid-based IVF would handle this more naturally.

### PLAID (optional, GPU)

- **Algorithm**: IVF with residual compression
- **Library**: `fast-plaid` (Rust implementation)
- **GPU recommended**: K-means centroid computation benefits from GPU
- **Parameters**: `nbits=2` (2-bit residual compression)
- **Search flow**: Direct PLAID retrieval with centroid-based candidate generation

Choose PLAID when you have a GPU and need faster search at scale. Choose Voyager (default) for CPU-only environments.

---

## Output Files

```
colbertv2 exp/
├── colbert_index.py              # Main pipeline script (CLI + serve)
├── README.md                     # This file
├── web/                          # Flask + HTMX web UI
│   ├── app.py                    # Flask application
│   ├── templates/                # Jinja2 templates (5 files)
│   └── static/style.css          # CSS theme
├── embeddings/                   # Cached embeddings (regenerable)
│   ├── embeddings_awn_oewn_dict_at.pkl    # Full build cache
│   └── embeddings_awn_oewn_dict_at_limit100.pkl  # Test build
├── indexes/                      # Index files (regenerable)
│   └── synset_colbert/           # Voyager or PLAID index
│       ├── index.voyager         # HNSW graph
│       ├── document_ids_to_embeddings.sqlite
│       └── embeddings_to_documents_ids.sqlite
├── metadata/                     # Document metadata + ILI map
│   ├── synset_metadata.json      # {doc_id: {lang, pos, ili, lemmas, definition, source_type}}
│   └── ili_map.json              # {ili: [doc_id_1, doc_id_2]}
├── research/                     # Background research
│   └── ColBERTv2 implementations.md
└── repos/                        # Reference repos (cloned --depth 1)
    ├── ColBERT/                  # Stanford official (v2 + PLAID)
    ├── RAGatouille/              # Simplified wrapper
    ├── pylate/                   # SentenceTransformers-based (used)
    └── ColBERT-X/                # Cross-lingual retrieval
```

### Sizes (production build, 230K synsets only)

| File | Size |
|------|------|
| `embeddings/embeddings.pkl` | 3.0 GB |
| `indexes/synset_colbert/index.voyager` | 6.1 GB |
| `indexes/synset_colbert/*.sqlite` | 433 MB |
| `metadata/synset_metadata.json` | 48 KB |
| `metadata/ili_map.json` | 7 KB |

The full 758K build will produce proportionally larger files (~3× larger embeddings and index).

---

## Performance

### Build timing (CPU, Apple Silicon M1, batch_size=8)

| Phase | Duration | Notes |
|-------|----------|-------|
| Parse AWN4 XML | 2.1s | 109,901 synsets, 166,785 lemma entries |
| Load OEWN | 18.9s | 120,630 synsets via `wn` package |
| Load dictionaries | <1s | 109,769 entries from SQLite |
| Load ARABTERM | <1s | 417,278 terms from SQLite |
| Build corpus | <1s | ~758K documents |
| **Encode documents** | **~5-6 hours** | 24ms/doc steady-state (758K docs) |
| **Build Voyager index** | **~2-3 hours** | HNSW insertion slows as graph grows |
| **Total (full build)** | **~8-9 hours** | |

Embeddings are cached to disk after the first run. Subsequent builds only rebuild the index.

### Search latency (full index)

| Metric | Value |
|--------|-------|
| Model load time | ~3.5 seconds (cached) |
| Query encoding | ~50 ms |
| Voyager retrieval + reranking (in-language) | ~1.1 s |
| Voyager retrieval + reranking (cross-lingual, k_token=500) | ~2.0 s |
| Total per query | ~1.2–2.1 s |

### Scaling notes

- **Batch size**: Increase `--batch-size` for faster encoding if you have more RAM (8 is conservative for 560M model on CPU)
- **MPS device**: `--device mps` may work on Apple Silicon for faster encoding (not yet tested)
- **CUDA**: `--device cuda --backend plaid` for GPU systems
- **Voyager index build slows**: HNSW insertion becomes O(log N) as the graph grows — the last 20% of documents took 10× longer per batch than the first 20%. This is expected behavior.

---

## Results

### Production index (230,531 synsets)

#### Arabic search: "عقد" (polysemous — contract, knot, necklace, decade)

```
  1. [ar] awn4-01737358-v  score=18.98   عَقَدَ — "نظم أو كان مسؤولاً عن"  ↔ EN: hold; throw; have
  2. [ar] awn4-00149904-n  score=18.96   ربط; عقد — "عملية ربط أو توثيق"  ↔ EN: tying; ligature
  3. [ar] awn4-04345456-n  score=18.87   خيط; عقد — "مجموعة أشياء منظومة"  ↔ EN: string
  4. [ar] awn4-03820446-n  score=18.78   عقد; قلادة — "مجوهرات تلبس حول العنق"  ↔ EN: necklace
  5. [ar] awn4-06534110-n  score=18.55   عقد احتمالي — "عقد يعتمد على حدث غير مؤكد"  ↔ EN: aleatory contract
```

All major senses of "عقد" found: verbal (hold/organize), tying, string, necklace, contract types.

#### English search: "contract"

```
  1. [en] oewn-06532935-n  score=20.54   contract — "a binding agreement..."  ↔ AR: عقد
  2. [en] oewn-00890307-v  score=19.23   contract; undertake  ↔ AR: تَعَاقَدَ
  3. [en] oewn-06750143-n  score=18.85   contract; declaration (bridge)  ↔ AR: عقد
  4. [en] oewn-06539311-n  score=18.79   employment contract  ↔ AR: عقد توظيف
  5. [en] oewn-06171758-n  score=18.68   contract law  ↔ AR: قانون العقود
```

#### Cross-lingual: English → Arabic

```
Query: "contract" --lang ar

  1. [ar] awn4-09980370-n  score=18.00   متعاقد — "(قانون) طرف في عقد"  ↔ EN: contractor
  2. [ar] awn4-06532935-n  score=17.97   عقد — "اتفاق ملزم"  ↔ EN: contract
  3. [ar] awn4-00890307-v  score=17.95   تَعَاقَدَ — "الدخول في ترتيب تعاقدي"  ↔ EN: contract; undertake
  4. [ar] awn4-02713392-a  score=17.85   تعاقدي  ↔ EN: contractual
  5. [ar] awn4-06492394-n  score=17.80   عقد مستقبلي; عقود آجلة  ↔ EN: futures contract
```

#### Cross-lingual: Arabic → English

```
Query: "عقد" --lang en

  1. [en] oewn-06532935-n  score=18.15   contract — "a binding agreement..."  ↔ AR: عقد
```

Arabic→English cross-lingual returns fewer results due to Voyager's token-level ANN clustering by language (see [Index Backends](#index-backends)). English→Arabic works better because many Arabic documents contain transliterated Latin tokens.

#### POS filter: "رفع" verbs only

```
Query: "رفع" --pos v

  1. [ar] awn4-00943197-v  score=20.46   أَثَارَ; رَفَعَ  ↔ EN: raise
  2. [ar] awn4-01877777-v  score=20.24   رَفَعَ; سَانَدَ  ↔ EN: boost up; push up
  3. [ar] awn4-01518703-v  score=20.20   دَفَعَ للأَعْلَى; رَفَعَ  ↔ EN: boost
  4. [ar] awn4-00153083-v  score=20.20   رَفَعَ; زَادَ  ↔ EN: increase
  5. [ar] awn4-00880549-v  score=20.15   أَعَادَ; رَفَعَ  ↔ EN: return
```

#### Source filter: dictionary entries for "أبه"

```
Query: "أبه" --source dict

  1. [ar|dict] dict-Al_Waseet-154  (n)  score=21.32
     Lemmas: ابه; ابهة
     Def: عظمة وكبرياء
```

#### Cross-lingual ARABTERM: "transport"

```
Query: "transport" --source arabterm

  1. [ar|arabterm] at-12345  (n)  score=19.50
     Lemmas: نقل; transport; transport
     Def: [Transport]
```

### Pilot Results (200 synsets)

The initial pilot (100 Arabic + 100 English) confirmed cross-lingual alignment:

```
Query: "قادر على القيام"
  1. [ar] awn4-00001740-a  score=20.21  قَادِر; مُسْتَطِيع  ↔ EN: able (i1)
  2. [en] oewn-00001740-a  score=19.51  able  ↔ AR: قَادِر; مُسْتَطِيع (i1)
```

---

## Troubleshooting

### `ImportError: einops`

```bash
pip install einops>=0.8.1
```

Jina-ColBERT-v2 uses custom model code that requires `einops` for tensor rearrangement operations.

### `AttributeError: module 'numpy.random' has no attribute 'mtrand'`

numpy/scipy version mismatch. Fix:
```bash
pip install --force-reinstall numpy==1.26.4 scipy==1.13.1
```

### `wn.DatabaseError: schema has changed`

The wn package's internal database was built with an older version:
```bash
rm ~/.wn_data/wn.db
python -c "import wn; wn.download('oewn:2024')"
```

### `No sentence-transformers model found with name jinaai/jina-colbert-v2`

This warning is expected — PyLate falls back to loading via `AutoModel.from_pretrained` with `trust_remote_code=True`. The model downloads and works correctly despite the warning.

### Model download hangs or fails

Jina-ColBERT-v2 is ~2.2 GB. If the download fails:
```bash
# Clear HuggingFace cache for this model
rm -rf ~/.cache/huggingface/hub/models--jinaai--jina-colbert-v2/
# Retry
python colbert_index.py build --limit 10
```

### Out of memory during encoding

Reduce batch size:
```bash
python colbert_index.py build --batch-size 2
```

The 560M parameter model requires ~2 GB RAM for inference. With batch_size=8, peak usage is ~4–6 GB.

### Web UI: model loads twice

Ensure `use_reloader=False` (the default). Flask's reloader forks the process, doubling memory usage. The `serve` subcommand and `web/app.py` both disable the reloader by default.

### Dictionary DB not found

The web UI and dictionary indexing require `arabic-dictionaries/db/arabic_dict.db`. If you see `WARNING: Dictionary DB not found`, ensure the database exists at the expected path relative to the project root.

---

## Reference Repos

Cloned into `repos/` for reference (shallow clones, `--depth 1`):

| Repo | Stars | Purpose |
|------|-------|---------|
| [stanford-futuredata/ColBERT](https://github.com/stanford-futuredata/ColBERT) | ~3,765 | Reference implementation, PLAID engine (C++/CUDA) |
| [AnswerDotAI/RAGatouille](https://github.com/AnswerDotAI/RAGatouille) | ~3,800 | Simplified 3-line API, fine-tuning, LangChain bridge |
| [lightonai/pylate](https://github.com/lightonai/pylate) | 670 | **Used in this experiment** — SentenceTransformers-based, Rust FastPLAID |
| [hltcoe/ColBERT-X](https://github.com/hltcoe/ColBERT-X) | 73 | Cross-lingual retrieval, Translate-Train/Distill paradigm |

See `research/ColBERTv2 implementations.md` for the full landscape survey (95 pages) covering all ColBERTv2 implementations, Arabic ColBERT models, and benchmark results.
