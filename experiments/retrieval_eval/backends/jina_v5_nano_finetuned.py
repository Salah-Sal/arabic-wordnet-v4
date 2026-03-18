#!/usr/bin/env python3
"""Finetuned Jina v5-text-nano + FAISS backend.

Loads finetuned weights from HF Hub (SalahAbdoNLP/jina-v5-nano-arabic-dict)
and merges with custom EuroBERT code from the base Jina repo (which the
SentenceTransformerTrainer didn't include in the push).

The model was finetuned with "Query: " / "Document: " prefixes baked into
the training data, so we manually prepend those during encoding.

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "8")

# IMPORTANT: import torch + sentence_transformers at module level, BEFORE
# faiss is ever imported (lazily inside functions).  faiss-cpu links OpenMP
# which spawns threads on import; if torch/ST are imported after that, their
# dynamic module loading can fork → SIGSEGV on macOS.
import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

_FT_LOCAL = (Path(__file__).resolve().parent.parent.parent
             / "trajectory_dataset" / "output" / "jina_v5_nano_finetuned")
_FT_REPO = "SalahAbdoNLP/jina-v5-nano-arabic-dict"
_BASE_REPO = "jinaai/jina-embeddings-v5-text-nano-retrieval"
_DIMENSIONS = 768
_RUN_NAME = "jina_v5_nano_finetuned"

# Module-level caches
_cached_model = None
_cached_index = None
_cached_mapping: list[str] | None = None
_cached_config_path: str | None = None


def _prepare_model_dir() -> Path:
    """Download finetuned weights + base repo's custom code into a merged dir."""
    from huggingface_hub import hf_hub_download

    merged_dir = Path.home() / ".cache" / "jina_v5_nano_finetuned_merged"
    marker = merged_dir / ".ready"

    if marker.exists():
        return merged_dir

    merged_dir.mkdir(parents=True, exist_ok=True)

    # Finetuned model files (weights, config, tokenizer data)
    for fname in ["config.json", "model.safetensors", "tokenizer.json"]:
        path = hf_hub_download(_FT_REPO, fname)
        shutil.copy2(path, merged_dir / fname)

    # From base Jina repo: custom EuroBERT code + correct tokenizer config
    # (the finetuned repo has tokenizer_class="TokenizersBackend" which
    #  is invalid; base repo has the correct "PreTrainedTokenizer")
    for fname in ["configuration_eurobert.py", "modeling_eurobert.py",
                  "tokenizer_config.json"]:
        path = hf_hub_download(_BASE_REPO, fname)
        shutil.copy2(path, merged_dir / fname)

    # Sentence-transformers pipeline config from base retrieval repo.
    # CRITICAL: the model uses last-token pooling, NOT mean pooling.
    # Without these files, ST falls back to mean pooling → broken embeddings.
    for fname in ["modules.json", "config_sentence_transformers.json"]:
        path = hf_hub_download(_BASE_REPO, fname)
        shutil.copy2(path, merged_dir / fname)

    # Pooling config lives in a subdirectory
    pooling_dir = merged_dir / "1_Pooling"
    pooling_dir.mkdir(exist_ok=True)
    path = hf_hub_download(_BASE_REPO, "1_Pooling/config.json")
    shutil.copy2(path, pooling_dir / "config.json")

    marker.touch()
    print(f"Prepared merged model dir: {merged_dir}", file=sys.stderr)
    return merged_dir


def _load_model():
    """Load finetuned model (cached at module level).

    Prefers local zip-extracted model if available, falls back to
    HF Hub merged directory.
    """
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    if _FT_LOCAL.is_dir() and (_FT_LOCAL / "model.safetensors").exists():
        model_dir = _FT_LOCAL
    else:
        model_dir = _prepare_model_dir()

    print(f"Loading finetuned model from {model_dir}...", file=sys.stderr)

    _cached_model = SentenceTransformer(
        str(model_dir), trust_remote_code=True,
    )
    _cached_model.max_seq_length = 512
    print(f"  max_seq_length = {_cached_model.max_seq_length}",
          file=sys.stderr)
    return _cached_model


def setup(export_dir, **kwargs) -> dict:
    """Embed all .md entry files and build a FAISS index."""
    import faiss

    export_dir = Path(export_dir)
    entries_dir = export_dir / "entries"
    if not entries_dir.is_dir():
        print(f"Error: {entries_dir} not found.", file=sys.stderr)
        sys.exit(1)

    model = _load_model()

    files = sorted(entries_dir.glob("*.md"))
    print(f"Embedding {len(files)} files with finetuned v5-nano "
          f"(dim={_DIMENSIONS})...", file=sys.stderr)

    texts = []
    filenames = []
    for f in files:
        texts.append(f.read_text(encoding="utf-8"))
        filenames.append(f.name)

    t0 = time.time()
    embeddings = model.encode(
        texts,
        prompt_name="document",
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    elapsed = time.time() - t0
    print(f"  Encoded {len(texts)} docs in {elapsed:.1f}s "
          f"({len(texts)/elapsed:.0f} docs/s)", file=sys.stderr)

    vectors = np.array(embeddings, dtype=np.float32)
    index = faiss.IndexFlatIP(_DIMENSIONS)
    index.add(vectors)

    run_dir = Path("runs") / _RUN_NAME
    run_dir.mkdir(parents=True, exist_ok=True)

    index_path = run_dir / "faiss.index"
    mapping_path = run_dir / "filenames.json"

    faiss.write_index(index, str(index_path))
    mapping_path.write_text(
        json.dumps(filenames, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nIndex built: {len(filenames)} vectors, dim={_DIMENSIONS}",
          file=sys.stderr)

    config = {
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
        "model_id": _FT_REPO,
        "dimensions": _DIMENSIONS,
        "run_name": _RUN_NAME,
        "files_embedded": len(filenames),
        "embed_time_s": round(elapsed, 1),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return config


def search(query: str, top_k: int, config: dict) -> list[dict]:
    """Embed query and search the FAISS index."""
    import faiss

    global _cached_index, _cached_mapping, _cached_config_path

    index_path = config["index_path"]
    mapping_path = config["mapping_path"]

    if _cached_config_path != index_path:
        _cached_index = faiss.read_index(index_path)
        _cached_mapping = json.loads(
            Path(mapping_path).read_text(encoding="utf-8")
        )
        _cached_config_path = index_path

    model = _load_model()

    query_vec = model.encode(
        [query],
        prompt_name="query",
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    distances, indices = _cached_index.search(query_vec, top_k)

    retrieved = []
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0:
            continue
        retrieved.append({
            "rank": rank + 1,
            "filename": _cached_mapping[idx],
            "score": float(dist),
            "content_preview": "",
        })

    return retrieved
