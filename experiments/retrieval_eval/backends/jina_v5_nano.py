#!/usr/bin/env python3
"""Jina Embeddings v5-text-nano + FAISS backend (local inference).

Model: jinaai/jina-embeddings-v5-text-nano (239M params, 768 dims, 8K context).

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]
"""
from backends._jina_common import search  # noqa: F401
from backends._jina_common import setup as _setup


def setup(export_dir, **kwargs):
    return _setup(export_dir,
                  model_id="jinaai/jina-embeddings-v5-text-nano",
                  dimensions=768, run_name="jina_v5_nano",
                  doc_task="retrieval", doc_prompt="document",
                  query_task="retrieval", query_prompt="query",
                  **kwargs)
