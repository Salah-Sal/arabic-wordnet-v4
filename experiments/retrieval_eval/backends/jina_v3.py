#!/usr/bin/env python3
"""Jina Embeddings v3 + FAISS backend (local inference).

Model: jinaai/jina-embeddings-v3 (570M params, 1024 dims, 8K context, task LoRA).

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]
"""
from backends._jina_common import search  # noqa: F401
from backends._jina_common import setup as _setup


def setup(export_dir, **kwargs):
    return _setup(export_dir,
                  model_id="jinaai/jina-embeddings-v3",
                  dimensions=1024, run_name="jina_v3",
                  doc_task="retrieval.passage",
                  doc_prompt="retrieval.passage",
                  query_task="retrieval.query",
                  query_prompt="retrieval.query",
                  **kwargs)
