---
language:
  - ar
  - en
library_name: sentence-transformers
tags:
  - sentence-transformers
  - feature-extraction
  - sentence-similarity
  - arabic
  - retrieval
  - finetuned
  - jina-embeddings
  - eurobert
base_model: jinaai/jina-embeddings-v5-text-nano-retrieval
datasets:
  - custom
pipeline_tag: sentence-similarity
license: apache-2.0
---

# Jina v5 Nano — Arabic Dictionary Retrieval v2

A finetuned version of [`jinaai/jina-embeddings-v5-text-nano-retrieval`](https://huggingface.co/jinaai/jina-embeddings-v5-text-nano-retrieval) (211M parameters, 768 dimensions) optimized for **Arabic dictionary entry retrieval** in the context of Arabic WordNet v4 (AWN4).

This is **v2**, trained with 8 corrections over v1 including CachedMultipleNegativesRankingLoss (GradCache), anchor decomposition (3× training data), and proper warmup/precision settings. See the [v1 model](https://huggingface.co/SalahAbdoNLP/jina-v5-nano-arabic-dict) for comparison.

## Key Result

The finetuned v2 model **beats Google's Gemini embedding-001** on definition-based retrieval (63.0% vs 58.2% R@10) while being a local 211M model. It outperforms the 3× larger Jina v5-small (677M) by +13.5pp on the same task.

| Metric | Base v5-nano | **Finetuned v2** | v1 | v5-small (677M) | Gemini (cloud) |
|--------|-------------|-----------------|-----|-----------------|----------------|
| arabic_lemma R@10 | 95.5% | 91.8% | 95.9% | 97.6% | 99.5% |
| **def_keyword R@10** | 48.3% | **63.0%** | 54.0% | 49.5% | 58.2% |
| Overall R@10 | 71.9% | **77.4%** | 74.9% | 73.5% | 78.8% |
| Overall MRR | 0.670 | **0.765** | 0.695 | 0.659 | 0.703 |

Evaluated on 126 queries across 63 AWN4 synsets, against a FAISS corpus of 1,937 headword documents (7,141 entries from 15 Arabic dictionaries).

### Independent Validation

On a clean evaluation dataset (79 synsets, 166 triplets, zero training overlap):

| Metric | Base v5-nano | Finetuned v2 |
|--------|-------------|--------------|
| Triplet accuracy | 46.4% | **67.5%** (+21.1pp) |
| Mean cosine margin | −0.011 | **+0.057** |

## Usage

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "SalahAbdoNLP/jina-v5-nano-arabic-dict-v2",
    trust_remote_code=True,
)
model.max_seq_length = 512

# Encode queries
queries = ["ما يُدرَك أو يُعرَف أو يُستدَلّ على وجوده المستقل"]
query_embeddings = model.encode(
    queries,
    prompt_name="query",
    normalize_embeddings=True,
)

# Encode documents
documents = ["# كيان (جذر: كن)\n\n## Data and AI Glossary\nEN: Entity\n..."]
doc_embeddings = model.encode(
    documents,
    prompt_name="document",
    normalize_embeddings=True,
)

# Compute similarity
similarities = query_embeddings @ doc_embeddings.T
```

### Important Notes

- Use `prompt_name="query"` for queries and `prompt_name="document"` for corpus documents. These add the `"Query: "` and `"Document: "` prefixes that the model was trained with.
- The model uses **last-token pooling** (not mean pooling). The `modules.json` and `1_Pooling/config.json` files in this repo ensure correct pooling behavior.
- Requires `trust_remote_code=True` for the custom EuroBERT architecture.

## Training Details

### v2 Corrections from v1

| # | Bug in v1 | Fix in v2 |
|---|-----------|-----------|
| P0-1 | Grad accum doesn't increase contrastive batch (only 15 negatives/query) | CachedMNRL — 63 negatives/query |
| P0-2 | MNRL negatives math wrong | Correctly: 2×32−1 = 63 negatives |
| P0-3 | Train/test distribution shift (combined anchors only) | Anchor decomposition → 3 variants per anchor |
| P1-4 | warmup_steps=582 = 80% of training | warmup_ratio=0.1 |
| P1-5 | bf16 on T4 = software emulation | fp16 (native T4 tensor cores) |
| P1-6 | metric_for_best_model not set | Set to NDCG@10 |
| P1-7 | Param count 239M (includes LoRA) | Corrected to 211M |
| P2-8 | "32 eval synsets" was 28 | Corrected |

### Configuration

| Parameter | v1 | v2 |
|-----------|-----|-----|
| Base model | `jinaai/jina-embeddings-v5-text-nano-retrieval` | same |
| Parameters | 211M (full finetune) | same |
| Loss | MatryoshkaLoss(MNRL) | MatryoshkaLoss(**CachedMNRL**) |
| Matryoshka dims | [768, 512, 256, 128, 64, 32] | same |
| Training triplets | 4,660 | **13,980** (3× via anchor decomposition) |
| Eval triplets | 1,512 | **4,536** |
| Negatives per query | 15 | **63** |
| Epochs | 5 (best: epoch 2) | 5 (best: **epoch 1**, step 219) |
| Batch size | 8 × 4 grad accum | **32** per device |
| Mini-batch size | — | **16** |
| Learning rate | 2e-5 (cosine) | same |
| Warmup | 582 steps (80%) | **10%** |
| Precision | bf16 (emulated) | **fp16** (native) |
| GPU | 1× T4 (Colab) | **2× T4 (Kaggle)** |

## Training Data

The dataset was constructed from a three-stage pipeline:

1. **280 Claude Code autonomous sessions** queried an Arabic dictionary SQLite database (760K entries, 107 dictionaries) to find matches for AWN4 synsets. Cost: $182 total (~$1.08/synset).
2. **Structured linguistic reviews** produced per-lemma decisions (confirmed/removed) with evidence assessment, substitution tests, and nuance differentiation.
3. **Triplet assembly** cross-joined confirmed positives with rejected negatives per synset. 96.1% soft negatives (FTS-adjacent, unreviewed) + 3.9% hard negatives (expert-rejected near-synonyms). Split at synset level to prevent leakage.

**v2 anchor decomposition:** Each anchor `"Query: lemmas — definition"` is split into 3 variants (combined, lemma-only, definition-only), tripling the dataset from 4,660 → 13,980 training triplets while matching the production query distribution.

## Intended Use

- Retrieving relevant Arabic dictionary entries given an Arabic definition or concept description
- Arabic WordNet construction and enrichment
- Cross-register Arabic semantic search (modern definitions → classical/modern dictionary entries)

## Limitations

- Trained specifically on Arabic dictionary/lexicographic content. Performance on general Arabic text retrieval is not evaluated.
- The training set covers 137 AWN4 synsets — a small fraction of the full AWN4. Performance may vary on domains not represented in training.
- definition_keyword R@10 improved from 48.3% to 63.0% — a large gain but below the 80%+ target. The task remains challenging.
- arabic_lemma R@10 regressed slightly (95.5% → 91.8%) due to the training emphasis on definition-style queries via anchor decomposition.
- The model inherits the base Jina v5-nano's 8K context window but was trained with `max_seq_length=512`.

## Citation

```bibtex
@misc{jina-v5-nano-arabic-dict-v2,
  author = {Salah Abdo},
  title = {Jina v5 Nano Finetuned for Arabic Dictionary Retrieval v2},
  year = {2026},
  publisher = {HuggingFace},
  url = {https://huggingface.co/SalahAbdoNLP/jina-v5-nano-arabic-dict-v2}
}
```
