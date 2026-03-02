# ColBERT Dictionary Index — Technical Reference

## 1. Overview

| Property | Value |
|----------|-------|
| Script | `colbert_index.py` |
| Model | [Jina-ColBERT-v2](https://huggingface.co/jinaai/jina-colbert-v2) (multilingual, 128-dim) |
| Backend | PLAID (IVF-PQ via `fast-plaid` Rust library) |
| Data Source | `arabic-dictionaries/db/arabic_dict.db` (v2 schema) |
| Indexed Entries | 341,880 (108,415 OCR + 233,465 Hawramani) |
| Index Size | ~3 GB on disk (15 PLAID shards) |
| Metadata | 144 MB JSON (341,880 entry records) |
| Search Latency | 400–1,400 ms per query (CPU, Apple Silicon) |
| Dependencies | `pylate`, `torch==2.9.0`, `fast-plaid`, `voyager` (optional) |

The ColBERT index provides **semantic retrieval** over the Arabic dictionary corpus. Unlike SQL-based lookups (exact headword, root, FTS5 BM25), ColBERT finds entries where the **meaning** matches the query — even when the query and entry share no common words.

---

## 2. Architecture

### What is ColBERT?

ColBERT (Contextualized Late Interaction over BERT) is a **late-interaction retrieval model**. Unlike single-vector models (e.g., Sentence-BERT) that compress an entire document into one embedding, ColBERT preserves **per-token embeddings**:

```
Document: "الماءُ: الذي يُشْرَبُ"
         ↓ encode (is_query=False)
Token embeddings: [e₁, e₂, e₃, ..., eₙ]  (each 128-dim)
```

At query time, the query is also encoded into per-token embeddings, and relevance is computed via **MaxSim** — the sum of maximum cosine similarities:

```
score(q, d) = Σᵢ maxⱼ (qᵢ · dⱼ)
```

This means each query token independently finds its best-matching document token, then scores are summed. This captures fine-grained semantic overlap that single-vector models miss.

### Query vs Document Encoding

ColBERT uses **asymmetric encoding** — queries and documents are processed differently:

| | Query | Document |
|--|-------|----------|
| Prefix token | `[QueryMarker]` | `[DocumentMarker]` |
| Padding | `[MASK]` expansion to 32 tokens | No padding |
| Punctuation | Preserved | Skipped (via skiplist) |
| Purpose | `[MASK]` tokens act as soft query expansion — the model learns to place them in embedding space to match related concepts | Compact representation of content |

This asymmetry is fundamental — you cannot swap query/document encoding and expect correct results.

### PLAID Index Architecture

PLAID (Performance-optimized Late Interaction using Approximate nearest-neighbors with Dimensionality-reduction) compresses token embeddings for efficient storage and retrieval:

```
Raw embedding (128-dim float32)     = 512 bytes/token
    ↓ K-means clustering
Centroid ID (int32)                 = 4 bytes
    ↓ Residual quantization (nbits=2)
Quantized residual (2 bits × 128)  = 32 bytes
                                    ─────────
Compressed                          = 36 bytes/token  (~14× compression)
```

**Retrieval pipeline:**
1. **Centroid lookup**: For each query token, find nearest centroids in the IVF (inverted file)
2. **Candidate generation**: Collect documents containing tokens mapped to those centroids
3. **Approximate MaxSim**: Score candidates using centroid-level approximation
4. **Exact reranking**: Decompress top candidates' residuals and compute exact MaxSim

This avoids brute-force comparison against all 341K documents. Typical retrieval touches <1% of the index.

### Why PLAID over Voyager?

| | PLAID | Voyager |
|--|-------|---------|
| Data structure | IVF-PQ (inverted file + product quantization) | HNSW (hierarchical navigable small world graph) |
| Storage | 3 GB (compressed residuals) | ~18 GB (full-precision embeddings) |
| Insertion cost | O(1) per token (after centroid training) | O(log N) per token (graph rewiring) |
| Build time (342K) | ~2.7 hrs encoding + 2.7 hrs index | ~2.7 hrs encoding + **fails** (OOM at 14%) |
| Memory at build | ~3.5 GB peak | >16 GB (crashed) |
| Search | 3-pass (centroid → approximate → exact) | 2-pass (token ANN → document MaxSim) |

Voyager's HNSW graph stores every token as a node with ~32 edges. At ~10M tokens, the graph alone needs 1.7 GB plus 6.5 GB for embeddings — exceeding 16 GB RAM during construction. PLAID's compressed representation fits comfortably.

---

## 3. Data Pipeline

### Document Format

Each dictionary entry is converted into a single document string:

```
{lemma1}; {lemma2}; ... | {definitions_text} | {example1}. {example2}.
```

- **Lemmas**: `headword_bare` + plurals from the `plurals` child table. Arabic diacritics are stripped to match undiacritized queries.
- **Definition**: The `definitions_text` column (flattened text of all senses).
- **Examples**: Joined from the `examples` child table.

Example document for entry "كتب" from Lisan al-Arab:

```
كتب | الكَتْبُ: خَرْز بسَيْرٍ أو سَيْرَيْن... والفِعْلُ: يَكْتُبُ
```

### Document ID Format

Each document gets a unique ID encoding its provenance:

```
dict-{dictionary_key}-{entry_id}
```

Examples:
- `dict-Al_Waseet-730` — Al-Waseet entry #730 (OCR)
- `dict-hawramani_36-907374` — Hawramani dictionary #36, entry ID 907374
- `dict-arabterm_123-500001` — ARABTERM dictionary #123, entry ID 500001

### Metadata

Metadata is stored in `metadata/synset_metadata.json` (144 MB). Each entry contains:

```json
{
  "dict-hawramani_6-984075": {
    "synset_id": "dict-hawramani_6-984075",
    "lang": "ar",
    "pos": "n",
    "ili": "",
    "lemmas": ["موه"],
    "definition": "الماءُ: الذي يُشْرَبُ، والهمزةُ فيه مُبْدَلَةٌ من الهاء...",
    "source_type": "hawramani"
  }
}
```

### Source Breakdown

| Source | Entries | Description |
|--------|--------:|-------------|
| OCR | 108,415 | 5 dictionaries extracted from scanned PDFs (Al-Waseet, Al-Kabir, Mujmal, Kitab al-Ayn, Maqayis) |
| Hawramani | 233,465 | 51 classical/modern dictionaries from the official Hawramani export |
| **Total** | **341,880** | |

ARABTERM terminology (417K entries) is excluded from the current index to fit within 16 GB RAM. ARABTERM entries are short glossary pairs (Arabic ↔ English/French) with minimal definition text, making them less valuable for semantic retrieval.

---

## 4. Directory Structure

```
colbertv2 exp/
├── colbert_index.py          # Main script (build, search, interactive, serve)
├── COLBERT_INDEX.md           # This documentation
├── indexes/
│   └── synset_colbert/
│       ├── fast_plaid_index/  # 15 shards: {N}.codes.npy + {N}.residuals.npy + {N}.metadata.json
│       ├── documents_ids_to_plaid_ids.sqlite  # Doc ID → internal PLAID ID mapping (29 MB)
│       └── plaid_ids_to_documents_ids.sqlite  # Reverse mapping (23 MB)
├── metadata/
│   ├── synset_metadata.json   # 341,880 entry records (144 MB)
│   └── ili_map.json           # ILI cross-references (empty for dict-only index)
├── embeddings/
│   └── embeddings_dict.pkl    # Cached raw embeddings (18 GB — can be deleted after index build)
└── sample_5k/                 # Small test index (5K entries, Voyager backend)
    ├── indexes/
    ├── metadata/
    └── embeddings/
```

### PLAID Shard Structure

Each shard contains:
- `{N}.codes.npy` — Centroid assignment codes for each token (int32 array)
- `{N}.residuals.npy` — Quantized residual vectors (packed bits)
- `{N}.metadata.json` — Shard metadata (token count, dimensions)

The 15 shards partition the 341,880 documents for parallel processing during retrieval.

---

## 5. Usage

### Prerequisites

```bash
pip install pylate torch==2.9.0 torchvision==0.24.0
# Voyager backend (optional, for small indexes only):
pip install "pylate[voyager]"
```

The model (`jinaai/jina-colbert-v2`) is downloaded automatically from HuggingFace on first use (~560 MB).

### Build the Index

```bash
# Full build: 342K entries, PLAID backend (~6.5 hrs on CPU)
python colbert_index.py build --backend plaid --batch-size 16

# Dict-only (skip ARABTERM):
python colbert_index.py build --backend plaid --no-arabterm --batch-size 16

# Small test build (100 entries, isolated output):
python colbert_index.py build --limit 100 --backend plaid --output-dir test_index

# Force re-encode (ignore cached embeddings):
python colbert_index.py build --backend plaid --force-encode
```

| Flag | Default | Description |
|------|---------|-------------|
| `--backend` | `voyager` | Index backend: `plaid` (recommended) or `voyager` (small indexes only) |
| `--limit N` | `0` (all) | Limit total entries loaded from DB |
| `--batch-size N` | `8` | Encoding batch size (16 recommended for Apple Silicon) |
| `--device` | `cpu` | PyTorch device (`cpu`, `cuda`, `mps`) |
| `--no-dict` | off | Skip OCR + Hawramani entries |
| `--no-arabterm` | off | Skip ARABTERM terminology |
| `--force-encode` | off | Re-encode even if cached embeddings exist |
| `--output-dir` | (default dirs) | Isolate output to a custom directory |

### Search

```bash
# Headword search:
python colbert_index.py search "كتب" --backend plaid --k 10

# Definition-based search (no headword needed):
python colbert_index.py search "سائل شفاف يشربه الناس" --backend plaid

# Filter by POS:
python colbert_index.py search "كتب" --backend plaid --pos v

# Filter by source type:
python colbert_index.py search "كتب" --backend plaid --source dict

# Search a custom index directory:
python colbert_index.py search "كتب" --backend plaid --output-dir sample_5k
```

| Flag | Default | Description |
|------|---------|-------------|
| `--k N` | `10` | Number of results to return |
| `--lang` | `all` | Filter: `ar`, `en`, or `all` |
| `--pos` | (none) | Filter: `n` (noun), `v` (verb), `a` (adjective), `r` (adverb) |
| `--source` | `all` | Filter: `dict` (OCR+Hawramani), `arabterm`, or `all` |
| `--backend` | `voyager` | Must match the backend used during build |
| `--output-dir` | (default dirs) | Directory containing the index to search |

### Interactive Mode

```bash
python colbert_index.py interactive --backend plaid
```

REPL commands:
- `:k N` — set number of results
- `:lang ar|en|all` — set language filter
- `:pos n|v|a|r|none` — set/clear POS filter
- `:source dict|arabterm|all` — set source filter
- `:quit` or `:q` — exit

### Web UI

```bash
python colbert_index.py serve --backend plaid --port 5002
```

Launches a Flask web interface on `http://localhost:5002`.

---

## 6. Search Examples

### Headword lookup

Query: **كتب** (write/books)

Returns entries for the root ك-ت-ب across all indexed dictionaries. Top results include entries from Lisan al-Arab, Maqayis al-Lugha, Mukhtar al-Sihah, Lane's Lexicon, and others — all defining the concept of writing, recording, and books.

```
 1. [ar|hawramani] dict-hawramani_36-907374  score=21.08
    Lemmas: كتب
    Def: الكَتْبُ: خَرْز بسَيْرٍ أو سَيْرَيْن...

 2. [ar|hawramani] dict-hawramani_31-840991  score=21.07
    Lemmas: كتب
    Def: الْكَتْبُ: ضمّ أديم إلى أديم بالخياطة...
```

### Semantic / definition-based retrieval

Query: **ماء** (water)

ColBERT finds entries about water even when the headword is not "ماء":

```
 1. [ar|hawramani] dict-hawramani_6-984075   score=20.38
    Lemmas: موه
    Def: الماءُ: الذي يُشْرَبُ، والهمزةُ فيه مُبْدَلَةٌ من الهاء...

 2. [ar|hawramani] dict-hawramani_25-826821  score=20.27
    Lemmas: سلسل
    Def: السَّلْسَلُ: الماء العذب، السَّلِسُ، السَّهْلُ فِي الْحَلْقِ...

 3. [ar|hawramani] dict-hawramani_14-788311  score=20.25
    Lemmas: ضحح
    Def: مَاءٌ ضَحْضَاحٌ أَيْ قَرِيبُ الْقَعْرِ...
```

The entry "موه" (the root of ماء) has headword "موه" — not "ماء" — yet ColBERT finds it because the definition text contains "الماء". Similarly, "سلسل" (sweet water) and "ضحح" (shallow water) are surfaced based on semantic content.

### Cross-concept retrieval

Query: **حكم القاضي في القضية** (the judge ruled on the case)

```
 1. [ar|hawramani] dict-hawramani_...-...  score=...
    Lemmas: قضى
    Def: ... القضاء: الحكم ...
```

ColBERT retrieves "قضى" (to judge/decide) for a phrase about "حكم" (ruling) — demonstrating cross-vocabulary retrieval where the query term and the result headword are different but semantically related.

---

## 7. Performance

### Build Performance (Apple Silicon M-series, CPU)

| Phase | Time | Notes |
|-------|------|-------|
| Load from DB | 13 s | 341,880 entries with plurals + examples |
| Build corpus | 1 s | Document text + metadata construction |
| Load model | 5 s | Jina-ColBERT-v2 (~560 MB, cached after first download) |
| Encode documents | 6.5 hrs | 341,880 docs × 0.068 s/doc (batch_size=16) |
| Build PLAID index | 2.7 hrs | K-means centroids + IVF-PQ compression |
| **Total** | **~9.2 hrs** | One-time cost; index persists on disk |

### Search Performance

| Query type | Latency | Notes |
|------------|---------|-------|
| Single headword (e.g., "كتب") | ~1,400 ms | First query includes model warmup |
| Headword (warm) | ~500–800 ms | Subsequent queries |
| Definition phrase | ~400–500 ms | Shorter queries encode faster |
| Model load (one-time) | ~2–5 s | Loaded once, reused across queries |

Latency breakdown: ~70% is query encoding (CPU), ~30% is PLAID retrieval + reranking.

### Storage

| Component | Size | Required at search time? |
|-----------|------|-------------------------|
| PLAID index | 3.0 GB | Yes |
| Metadata JSON | 144 MB | Yes |
| Cached embeddings | 18 GB | No (only needed for rebuilding) |
| Model weights | 560 MB | Yes (HuggingFace cache) |

The `embeddings_dict.pkl` (18 GB) can be deleted after the index is built — it's only needed if you want to rebuild the PLAID index without re-encoding.

---

## 8. Integration with RAG Pipeline

The ColBERT index is designed as a **retrieval tier** in the dictionary RAG pipeline (`arabic-dictionaries/extraction/rag/orchestrator.py`). It complements — not replaces — the existing SQL-based tiers:

### Current Pipeline Tiers

```
Tier 1: Exact headword match (SQL WHERE headword_bare = ?)
Tier 2: Root-family expansion (SQL WHERE root = ?)
Tier 3: FTS5 definition search (BM25 keyword matching)
Rootless fallback: 4-strategy cascade for entries without roots
```

### Where ColBERT Adds Value

ColBERT retrieves entries that the SQL tiers miss:

| Scenario | SQL Tiers | ColBERT |
|----------|-----------|---------|
| Exact headword "كتب" | Found (Tier 1) | Also found |
| Root family "ك-ت-ب" | Found (Tier 2) | Also found |
| Synonym "خط" for "كتب" | **Missed** | Found (semantic similarity) |
| Definition-level match | Partial (FTS5 keyword) | **Strong** (semantic understanding) |
| Cross-register (classical ↔ modern) | **Missed** | Found (embedding alignment) |
| Foreign loanwords (no root) | **Missed** (rootless fallback only) | Found |

### Proposed Integration

```python
# In orchestrator.py:
def tier_colbert(headword, definition_context, colbert_index, colbert_model):
    """Retrieve semantically related entries via ColBERT."""
    query = f"{headword} | {definition_context}"
    results = search(query, colbert_model, colbert_index, metadata, ili_map, k=20)
    return results

# Run conditionally when Tier 1+2 evidence is thin:
if len(tier1_results) + len(tier2_results) < MIN_EVIDENCE_THRESHOLD:
    colbert_results = tier_colbert(headword, definition, ...)
    # Score through existing score_candidate() function
    # ColBERT MaxSim score becomes an additional scoring component
```

ColBERT MaxSim scores can serve as component #10 in the existing 9-component scoring function, alongside (not replacing) the Jaccard-based `definition_similarity()`.

---

## 9. Programmatic API

### Loading the index in Python

```python
from colbert_index import load_model, load_index, load_metadata, search

# One-time setup (~7 seconds)
metadata, ili_map = load_metadata()
model = load_model(device="cpu")

# Load PLAID index
from pylate import indexes
index = indexes.PLAID(
    index_folder="indexes",
    index_name="synset_colbert",
    override=False,
)

# Search
results = search("كتب", model, index, metadata, ili_map, k=10)
for r in results:
    print(f"{r['score']:.2f}  {r['lemmas'][0]}  {r['definition'][:80]}")
```

### Result format

Each result is a dict:

```python
{
    "rank": 1,
    "score": 21.08,              # MaxSim score
    "synset_id": "dict-hawramani_36-907374",
    "lang": "ar",
    "pos": "n",
    "ili": "",
    "lemmas": ["كتب"],
    "definition": "الكَتْبُ: خَرْز بسَيْرٍ...",
    "source_type": "hawramani",  # "ocr" | "hawramani"
    "cross_ref": None,
}
```

### Encoding queries vs documents

```python
# Query encoding (with [MASK] expansion to 32 tokens):
query_emb = model.encode(["كتب"], is_query=True, batch_size=1)

# Document encoding (no padding, punctuation skipped):
doc_emb = model.encode(["كتب | الكَتْبُ: خَرْزٌ..."], is_query=False, batch_size=8)
```

**Important**: Always use `is_query=True` for queries and `is_query=False` for documents. Mixing them produces incorrect scores.

---

## 10. Rebuilding

### When to rebuild

- After loading new dictionaries into `arabic_dict.db`
- After updating `compute_roots.py` (roots appear in document text)
- After changing the document format in `build_document()`

### Rebuild steps

```bash
# 1. Full rebuild (re-encode + re-index, ~9 hours):
python colbert_index.py build --backend plaid --no-arabterm --force-encode --batch-size 16

# 2. Index-only rebuild (if embeddings are cached, ~2.7 hours):
python colbert_index.py build --backend plaid --no-arabterm --batch-size 16
# (will load from embeddings/embeddings_dict.pkl if it exists)
```

### Cleanup

```bash
# Delete cached embeddings (18 GB) after successful build:
rm embeddings/embeddings_dict.pkl

# Delete sample indexes:
rm -rf sample_5k/ sample_5k_plaid/
```

---

## 11. Limitations

1. **CPU-only encoding**: Encoding 342K entries takes ~6.5 hours on CPU. GPU (`--device cuda` or `--device mps`) would reduce this to ~30–60 minutes.

2. **No ARABTERM**: The 417K ARABTERM glossary entries are excluded from the current index due to RAM constraints (16 GB). Including them would require ~25 GB for raw embeddings. Options: streaming encode-and-index pipeline, or a machine with 32+ GB RAM.

3. **Search latency**: 400–1,400 ms per query on CPU. Acceptable for batch processing and RAG pipelines, but not for real-time autocomplete. GPU inference would reduce this to ~50–100 ms.

4. **No incremental updates**: Adding new entries requires a full re-encode and re-index. PLAID does not support incremental insertion (unlike Voyager's HNSW).

5. **Metadata in JSON**: The 144 MB metadata file is loaded entirely into memory at search time. For larger corpora, this should be migrated to SQLite with indexed lookups.
