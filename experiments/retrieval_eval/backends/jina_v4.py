#!/usr/bin/env python3
"""Jina Embeddings v4 + FAISS backend (local inference).

Model: jinaai/jina-embeddings-v4 (3.8B params, 2048 dims, 32K context, multimodal).
Note: requires MPS config patch (eager attention) on Apple Silicon.

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]
"""
import torch

from backends._jina_common import search  # noqa: F401
from backends._jina_common import setup as _setup


def setup(export_dir, **kwargs):
    return _setup(export_dir,
                  model_id="jinaai/jina-embeddings-v4",
                  dimensions=2048, run_name="jina_v4",
                  doc_task="retrieval", doc_prompt="passage",
                  query_task="retrieval", query_prompt="query",
                  batch_size=16,
                  model_kwargs={"torch_dtype": torch.float16},
                  **kwargs)
