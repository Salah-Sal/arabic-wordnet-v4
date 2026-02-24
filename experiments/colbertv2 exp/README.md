# ColBERTv2 Bilingual Synset Retrieval

Indexes Arabic WordNet 4 (AWN4) and Open English WordNet (OEWN) synsets into a single ColBERTv2 index for bilingual synset retrieval. A query in Arabic or English returns the most relevant synsets from **both** wordnets, with cross-lingual references via the Interlingual Index (ILI).

| | |
|---|---|
| **Date** | 2026-02-24 |
| **Script** | `colbert_index.py` |
| **Model** | Jina-ColBERT-v2 (560M params, XLM-RoBERTa backbone) |
| **Index backend** | Voyager (HNSW, CPU) or PLAID (GPU) |
| **Corpus** | ~109,901 Arabic + ~120,630 English = ~230,531 synsets |
| **Status** | Pipeline complete, tested on 200-synset pilot |

---

## Table of Contents

- [Motivation](#motivation)
- [Architecture](#architecture)
- [Environment Setup](#environment-setup)
- [Usage](#usage)
- [Data Sources](#data-sources)
- [Model Details](#model-details)
- [Index Backends](#index-backends)
- [Output Files](#output-files)
- [Performance](#performance)
- [Pilot Results](#pilot-results)
- [Troubleshooting](#troubleshooting)
- [Reference Repos](#reference-repos)

---

## Motivation

AWN4 contains 109,901 synsets, each with Arabic lemmas and definitions. The polysemy disambiguation pipeline (Stage 2) currently finds dictionary evidence via **exact string matching** on normalized headwords — only 53.1% of polysemy groups get any evidence at all.

ColBERTv2's token-level late interaction (MaxSim) enables **semantic retrieval**: a query like "عقد" can retrieve entries about "تعاقد", "معاقدة", "عقود" through subword-level matching. This experiment builds a general-purpose synset retrieval system that:

1. Searches synsets by meaning, not just surface form
2. Works across Arabic and English in a single unified index
3. Links results cross-lingually via ILI (e.g., Arabic "قادر" ↔ English "able")

---

## Architecture

```
colbert_index.py
│
├── Phase 1: Parse AWN4 XML ──→ 109,901 Arabic SynsetRecords
│       (iterparse + elem.clear(), reuses prefilter_dict.py pattern)
│
├── Phase 2: Load OEWN ──→ 120,630 English SynsetRecords
│       (via wn Python package)
│
├── Phase 3: Build corpus ──→ unified document list + metadata
│       Document format: "{lemmas} | {definition} | {examples}"
│
├── Phase 4: Encode ──→ multi-vector embeddings (128-dim per token)
│       (Jina-ColBERT-v2 via PyLate, chunked with disk cache)
│
├── Phase 5: Build index ──→ Voyager HNSW or PLAID IVF index
│
└── Phase 6: Search ──→ ranked synsets with metadata + ILI cross-refs
```

Each synset becomes one document:
```
قادر; مستطيع | يمتلك الوسائل أو المهارة اللازمة للقيام بشيء ما | قادر على السباحة
```

Arabic lemmas are stripped of diacritics in the document text to match typical undiacritized queries. Definitions are kept as-is.

---

## Environment Setup

### Prerequisites

- **Python 3.9** (tested with 3.9.6; PyLate requires >= 3.9)
- **macOS** (Apple Silicon or Intel) or **Linux**
- ~6 GB disk space for the Jina-ColBERT-v2 model download
- ~8 GB RAM minimum for encoding on CPU

### Step 1: Create a fresh virtual environment

```bash
# From the project root (wn-project/)
python3.9 -m venv colbert-venv
source colbert-venv/bin/activate
```

If you don't have Python 3.9, install it:
```bash
# macOS with Homebrew
brew install python@3.9

# Then create venv with explicit path
/opt/homebrew/opt/python@3.9/bin/python3.9 -m venv colbert-venv
source colbert-venv/bin/activate
```

### Step 2: Install dependencies

```bash
# Core: PyLate (includes sentence-transformers, fast-plaid, voyager)
pip install pylate==1.3.4

# Jina model dependency (not pulled automatically)
pip install einops>=0.8.1

# English WordNet loader
pip install wn==0.13.0

# Progress bars
pip install tqdm
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
print('PyLate OK')
print(f'OEWN synsets: {len(wn.synsets(lang=\"en\")):,}')
print('All good.')
"
```

Expected output:
```
PyLate OK
OEWN synsets: 120,630
All good.
```

### Complete dependency table

These are the exact versions tested and confirmed working:

| Package | Version | Role |
|---------|---------|------|
| `python` | 3.9.6 | Runtime |
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
| `tqdm` | any | Progress bars (optional) |

### requirements.txt

For reproducibility, create a `requirements.txt`:

```
pylate==1.3.4
einops>=0.8.1
wn==0.13.0
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

### Build the index

```bash
# Test build (100 synsets per language, ~50 seconds)
python colbert_index.py build --limit 100

# Full build (all ~230K synsets, ~3 hours on CPU for encoding)
python colbert_index.py build

# Arabic only (skip English)
python colbert_index.py build --no-english

# Use GPU (if available)
python colbert_index.py build --device cuda --backend plaid
```

| Flag | Default | Description |
|------|---------|-------------|
| `--limit N` | 0 (all) | Limit synsets per language |
| `--batch-size N` | 8 | Encoding batch size (lower = less RAM) |
| `--backend` | voyager | Index backend: `voyager` (CPU) or `plaid` (GPU) |
| `--device` | cpu | PyTorch device: `cpu`, `cuda`, or `mps` |
| `--no-english` | false | Skip English WordNet |
| `--force-encode` | false | Re-encode even if embedding cache exists |

**Embedding cache**: After the first build, embeddings are saved to `embeddings/`. Subsequent builds skip encoding and only rebuild the index. Use `--force-encode` to re-encode.

### Search

```bash
# Arabic query
python colbert_index.py search "عقد قانوني"

# English query
python colbert_index.py search "contract law"

# Cross-lingual: Arabic query, English results only
python colbert_index.py search "عقد" --lang en

# Filter by POS
python colbert_index.py search "رفع" --pos v --k 20
```

| Flag | Default | Description |
|------|---------|-------------|
| `--k N` | 10 | Number of results |
| `--lang` | all | Filter: `ar`, `en`, or `all` |
| `--pos` | none | Filter: `n`, `v`, `a`, or `r` |
| `--backend` | voyager | Must match the backend used during build |
| `--device` | cpu | PyTorch device for query encoding |

### Interactive mode

```bash
python colbert_index.py interactive
```

Commands in interactive mode:
```
> عقد                    # search
> contract               # search
> :k 20                  # change result count
> :lang ar               # filter to Arabic only
> :lang all              # reset language filter
> :pos n                 # filter to nouns
> :pos none              # clear POS filter
> :quit                  # exit
```

---

## Data Sources

### Arabic WordNet 4 (AWN4)

- **File**: `../../output/awn4.xml` (72 MB, WN-LMF 1.4 format)
- **Synsets**: 109,901
- **Lemma entries**: 166,785 (124,768 unique LexicalEntry elements)
- **Fields per synset**: ID, ILI, POS, Arabic definition, Arabic examples (0-4), Arabic lemmas (1-N)
- **ILI coverage**: All 109,901 synsets have ILI links to OEWN

### Open English WordNet (OEWN 2024)

- **Source**: Loaded via `wn` Python package (`wn.download("oewn:2024")`)
- **Synsets**: 120,630
- **Fields per synset**: ID, ILI, POS, English definition, English examples, English lemmas
- **ILI**: Links directly to AWN4 synsets via shared ILI identifiers

### Cross-lingual linking

Every synset carries an ILI (Interlingual Index) value. When searching, results include cross-references:

```
  1. [ar] awn4-00001740-a  score=20.21
     Lemmas: قَادِر; مُسْتَطِيع
     Def: يمتلك الوسائل أو المهارة...
     ↔ EN: able (i1)              ← cross-lingual reference via ILI
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
- **Parameters**: `M=64`, `ef_construction=200`, `ef_search=200`
- **Storage**: SQLite-backed document ID mapping + Voyager binary index
- **Search flow**: Voyager retrieves token-level candidates → PyLate reranks with full MaxSim

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
├── colbert_index.py              # Main script
├── README.md                     # This file
├── embeddings/                   # Cached embeddings (regenerable)
│   └── embeddings_limit100.pkl   # Test build cache (2.8 MB for 200 docs)
├── indexes/                      # Index files (regenerable)
│   └── synset_colbert/           # Voyager or PLAID index
│       ├── index.voyager         # HNSW graph
│       ├── document_ids_to_embeddings.sqlite
│       └── embeddings_to_documents_ids.sqlite
├── metadata/                     # Synset metadata + ILI map
│   ├── synset_metadata.json      # {synset_id: {lang, pos, ili, lemmas, definition}}
│   └── ili_map.json              # {ili: [synset_id_1, synset_id_2]}
├── research/                     # Background research
│   └── ColBERTv2 implementations.md
└── repos/                        # Reference repos (cloned --depth 1)
    ├── ColBERT/                  # Stanford official (v2 + PLAID)
    ├── RAGatouille/              # Simplified wrapper
    ├── pylate/                   # SentenceTransformers-based (used)
    └── ColBERT-X/                # Cross-lingual retrieval
```

### Estimated sizes (full build)

| File | Size (estimated) |
|------|------------------|
| `embeddings/embeddings.pkl` | ~3–4 GB |
| `indexes/synset_colbert/` | ~5–8 GB |
| `metadata/synset_metadata.json` | ~80 MB |
| `metadata/ili_map.json` | ~5 MB |

---

## Performance

### Encoding speed (CPU, Apple Silicon)

| Metric | Value |
|--------|-------|
| Model load time | ~3 seconds (cached) |
| Per-document encoding | ~42 ms |
| 200 documents (test) | 8.4 seconds |
| 230K documents (full, estimated) | ~2.7 hours |

Embeddings are cached to disk after the first run. Subsequent builds only rebuild the index (~minutes).

### Search latency

| Metric | Value |
|--------|-------|
| Query encoding | ~50 ms |
| Voyager retrieval + reranking | ~90 ms |
| Total per query | ~140 ms |

### Scaling notes

- **Batch size**: Increase `--batch-size` for faster encoding if you have more RAM (8 is conservative for 560M model on CPU)
- **MPS device**: `--device mps` may work on Apple Silicon for faster encoding (not yet tested)
- **CUDA**: `--device cuda --backend plaid` for GPU systems

---

## Pilot Results

Tested with 200 synsets (100 Arabic + 100 English):

### English query → bilingual results

```
Query: "able to do something"

  1. [en] oewn-00001740-a  score=20.49
     Lemmas: able
     Def: (usually followed by 'to') having the necessary means or skill...
     ↔ AR: قَادِر; مُسْتَطِيع (i1)

  2. [ar] awn4-00001740-a  score=18.92
     Lemmas: قَادِر; مُسْتَطِيع
     Def: يمتلك الوسائل أو المهارة أو المعرفة...
     ↔ EN: able (i1)
```

### Arabic query → bilingual results

```
Query: "قادر على القيام"

  1. [ar] awn4-00001740-a  score=20.21
     Lemmas: قَادِر; مُسْتَطِيع
     ↔ EN: able (i1)

  2. [en] oewn-00001740-a  score=19.51
     Lemmas: able
     ↔ AR: قَادِر; مُسْتَطِيع (i1)
```

Cross-lingual alignment is confirmed: Arabic queries find English synsets and vice versa, with the correct ILI-linked counterparts ranked in the top results.

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
