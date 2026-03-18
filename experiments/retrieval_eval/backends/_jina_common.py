#!/usr/bin/env python3
"""Jina Embeddings + FAISS backend — local inference via sentence-transformers.

Uses Jina's task-specific LoRA adapters for asymmetric retrieval encoding.
Stores vectors in a local FAISS flat index (IndexFlatIP on normalized vectors
= cosine similarity).

IMPORTANT: faiss is imported lazily (inside functions) to avoid the macOS
fork-after-thread crash.  faiss-cpu links OpenMP which spawns threads on
import; Jina's trust_remote_code model loading later forks the process
(via huggingface_hub parallel downloads), causing a SIGSEGV on macOS.

Convention:
    setup(export_dir, *, model_id, dimensions, run_name, ...) -> config dict
    search(query, top_k, config) -> list[dict]

Dependencies: sentence-transformers, torch, faiss-cpu, numpy
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Prevent fork-related crashes on macOS: disable tokenizer parallelism
# and limit OpenMP threads before any heavy imports.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "8")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

# Module-level caches
_cached_model: SentenceTransformer | None = None
_cached_model_id: str | None = None
_cached_index = None
_cached_mapping: list[str] | None = None
_cached_config_path: str | None = None


def _get_device() -> str:
    """Return best available device for inference."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_model(model_id: str,
                model_kwargs: dict | None = None,
                max_seq_length: int | None = None) -> SentenceTransformer:
    """Load a Jina model via sentence-transformers (cached at module level)."""
    global _cached_model, _cached_model_id

    if _cached_model_id == model_id and _cached_model is not None:
        return _cached_model

    device = _get_device()
    print(f"Loading {model_id} on {device}...", file=sys.stderr)

    kwargs = {
        "trust_remote_code": True,
        "device": device,
    }
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs

    _cached_model = SentenceTransformer(model_id, **kwargs)
    if max_seq_length:
        _cached_model.max_seq_length = max_seq_length
        print(f"  max_seq_length set to {max_seq_length}", file=sys.stderr)
    _cached_model_id = model_id
    return _cached_model


# -- Backend convention -------------------------------------------------

def setup(export_dir: Path, *, model_id: str, dimensions: int,
          run_name: str, doc_task: str, doc_prompt: str,
          query_task: str, query_prompt: str,
          batch_size: int = 32, max_seq_length: int = 512,
          model_kwargs: dict | None = None, **kwargs) -> dict:
    """Embed all .md entry files and build a FAISS index.

    Returns a config dict with index_path, mapping_path, model, dimensions,
    and query task/prompt for use by search().
    """
    import faiss  # lazy import — see module docstring

    export_dir = Path(export_dir)
    entries_dir = export_dir / "entries"
    if not entries_dir.is_dir():
        print(f"Error: {entries_dir} not found. Run export_entries.py first.",
              file=sys.stderr)
        sys.exit(1)

    model = _load_model(model_id, model_kwargs=model_kwargs,
                        max_seq_length=max_seq_length)

    files = sorted(entries_dir.glob("*.md"))
    print(f"Embedding {len(files)} files with {model_id} (dim={dimensions})...",
          file=sys.stderr)

    texts = []
    filenames = []
    for f in files:
        texts.append(f.read_text(encoding="utf-8"))
        filenames.append(f.name)

    t0 = time.time()
    embeddings = model.encode(
        texts,
        task=doc_task,
        prompt_name=doc_prompt,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    elapsed = time.time() - t0
    print(f"  Encoded {len(texts)} docs in {elapsed:.1f}s "
          f"({len(texts)/elapsed:.0f} docs/s)", file=sys.stderr)

    # Build FAISS index (normalized vectors → IP = cosine similarity)
    vectors = np.array(embeddings, dtype=np.float32)
    index = faiss.IndexFlatIP(dimensions)
    index.add(vectors)

    # Save index and mapping
    run_dir = Path("runs") / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    index_path = run_dir / "faiss.index"
    mapping_path = run_dir / "filenames.json"

    faiss.write_index(index, str(index_path))
    mapping_path.write_text(
        json.dumps(filenames, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nIndex built: {len(filenames)} vectors, dim={dimensions}",
          file=sys.stderr)
    print(f"  Index: {index_path}", file=sys.stderr)
    print(f"  Mapping: {mapping_path}", file=sys.stderr)

    config = {
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
        "model_id": model_id,
        "dimensions": dimensions,
        "run_name": run_name,
        "query_task": query_task,
        "query_prompt": query_prompt,
        "max_seq_length": max_seq_length,
        "files_embedded": len(filenames),
        "embed_time_s": round(elapsed, 1),
        "device": _get_device(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return config


def search(query: str, top_k: int, config: dict) -> list[dict]:
    """Embed query and search the FAISS index.

    Returns list of {rank, filename, score, content_preview}.
    """
    import faiss  # lazy import — see module docstring

    global _cached_index, _cached_mapping, _cached_config_path

    index_path = config["index_path"]
    mapping_path = config["mapping_path"]
    model_id = config["model_id"]
    query_task = config["query_task"]
    query_prompt = config["query_prompt"]

    # Load index + mapping (cached)
    if _cached_config_path != index_path:
        _cached_index = faiss.read_index(index_path)
        _cached_mapping = json.loads(
            Path(mapping_path).read_text(encoding="utf-8")
        )
        _cached_config_path = index_path

    # Load model (cached)
    model = _load_model(model_id)

    # Embed query
    query_vec = model.encode(
        [query],
        task=query_task,
        prompt_name=query_prompt,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    # Search
    distances, indices = _cached_index.search(query_vec, top_k)

    retrieved = []
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0:
            continue
        filename = _cached_mapping[idx]
        retrieved.append({
            "rank": rank + 1,
            "filename": filename,
            "score": float(dist),
            "content_preview": "",
        })

    return retrieved
