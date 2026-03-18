#!/usr/bin/env python3
"""Jina Embeddings v5-text-small + FAISS backend (local inference).

Model: jinaai/jina-embeddings-v5-text-small (677M params, 1024 dims, 32K context).

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]
"""
from backends._jina_common import search  # noqa: F401
from backends._jina_common import setup as _setup


def setup(export_dir, **kwargs):
    return _setup(export_dir,
                  model_id="jinaai/jina-embeddings-v5-text-small",
                  dimensions=1024, run_name="jina_v5_small",
                  doc_task="retrieval", doc_prompt="document",
                  query_task="retrieval", query_prompt="query",
                  **kwargs)
