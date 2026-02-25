# Research Documents & References

This folder contains research documents, references, and background material informing the synset linguistic audit experiment.

## Contents

| Document | Description |
|----------|-------------|
| `Open-source toolkit for auditing Arabic WordNet 4.0.md` | Survey of 80+ open-source tools mapped to 35 audit questions |
| `CAMeL Tools — Capability Inventory for AWN4 Audit.md` | Deep-dive into CAMeL Tools: all modules, 40+ morphological features, code patterns, and mapping to audit levels |
| `Farasa — Capability Inventory for AWN4 Audit.md` | Farasa toolkit: 7 NLP tasks, head-to-head comparison with CAMeL Tools, concrete cross-validation plan for the audit |

---

## Investigation Log: ColBERT Semantic Search for Synset Reviews

**Date:** 2026-02-25
**Context:** While building `generate_synset_review.py` (Level 1 audit), we attempted to use the ColBERT semantic search index (`colbertv2 exp/`) to surface dictionary and ARABTERM entries related to each synset's definition and lemmas. The goal was to add the top 3 non-synset ColBERT results per definition and per lemma to the linguist review documents.

### Problem

ColBERT semantic search returned **zero** dictionary or ARABTERM results, regardless of retrieval depth. All results were synsets.

### Investigation Method

1. **Metadata audit** — Counted `source_type` distribution in `synset_metadata.json`:
   - `arabterm`: 417,278 (55.1%)
   - `synset`: 230,531 (30.4%)
   - `dict`: 109,769 (14.5%)
   - **Total metadata entries: 757,578**

2. **Voyager index inspection** — Loaded the HNSW index and queried `embeddings_to_documents_ids.sqlite`:
   - **Token embeddings in index: 3,084** (expected ~7M+ for full corpus)
   - **Unique documents in index: 100** (all AWN4 synsets, first 100 by ID)
   - `index.voyager` file size: 3.1 MB (should be several GB for full corpus)

3. **Embeddings file audit** — Checked `embeddings/embeddings.pkl` (3,069 MB):
   - Contains **230,531 document embeddings** — matches only the AWN4 + OEWN synset count
   - Dict (109K) and ARABTERM (417K) entries were **never encoded**

4. **Retrieval depth testing** — Tested with `ef_search=5000` and `k_token` values of 500, 2000, 5000:
   - All returned exactly 100 results, all synsets
   - Confirmed the 100-document ceiling comes from the index itself, not search parameters

5. **pylate internals review** — Read the source of `indexes.Voyager.__call__` and `retrieve.ColBERT.retrieve`:
   - `ef_search` is a mutable Python attribute (not baked into the index file)
   - Retrieval is two-stage: token-level ANN (`k_token` neighbors per query token) → document-level MaxSim reranking (`k` final results)
   - The constraint `ef_search >= k_token` is enforced by Voyager's C++ layer

### Root Cause

A **two-layer metadata/index mismatch**:

| Layer | Expected (full corpus) | Actual |
|-------|------------------------|--------|
| Metadata (`synset_metadata.json`) | 757,578 docs | 757,578 docs |
| Embeddings (`embeddings.pkl`) | 757,578 docs | **230,531** (synsets only) |
| Voyager index (`index.voyager`) | 757,578 docs | **100** (first 100 synsets) |

The metadata was generated from all four sources (AWN4, OEWN, dict, ARABTERM), but:
- The embeddings were only encoded for synsets (AWN4 + OEWN = 230K), skipping dict and ARABTERM
- The Voyager HNSW index was built from a `--limit 100` test run, never rebuilt with full embeddings

The embeddings directory confirms the build history:
```
embeddings_limit100.pkl           2.8 MB   (100 synsets only)
embeddings_awn_oewn_limit50.pkl   1.5 MB   (50 per source)
embeddings_awn_oewn_dict_at_limit100.pkl  5.8 MB  (all sources, limit 100)
embeddings.pkl                    3,069 MB  (230K synsets, no dict/arabterm)
```

### Resolution

To get dict/ARABTERM results via ColBERT, 527K additional documents would need to be encoded (~hours on CPU) and the Voyager index rebuilt. This is deferred as a future task. For now, the synset review generator relies on **direct DB queries** (exact match, hamza-normalized match, and FTS definition mentions) for dictionary evidence and ARABTERM lookups, which provide good coverage for lexicographic data.
