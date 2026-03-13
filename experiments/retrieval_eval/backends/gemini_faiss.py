#!/usr/bin/env python3
"""Gemini Embeddings + FAISS backend — local vector search with asymmetric encoding.

Uses Gemini's task-type-aware embeddings: RETRIEVAL_DOCUMENT for indexing,
RETRIEVAL_QUERY for search. Stores vectors in a local FAISS flat index.

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]

Dependencies: google-genai, faiss-cpu, numpy, python-dotenv
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"

# Module-level cache for loaded index (avoids reloading per query)
_cached_index = None
_cached_mapping = None
_cached_config_path = None


def _get_client() -> genai.Client:
    """Load .env and return an authenticated Gemini client."""
    load_dotenv(ENV_PATH)
    api_key = os.getenv("GEM_API_KEY")
    if not api_key:
        print("Error: GEM_API_KEY not found in .env", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize vectors (required for cosine similarity via inner product)."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def _embed_batch(client: genai.Client, texts: list[str],
                 model: str, dimensions: int,
                 task_type: str,
                 max_retries: int = 5) -> list[list[float]]:
    """Embed a batch of texts with the specified task type and retry on 429."""
    for attempt in range(max_retries):
        try:
            result = client.models.embed_content(
                model=model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=dimensions,
                ),
            )
            return [e.values for e in result.embeddings]
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s, 40s, 80s
                print(f"    Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})...",
                      file=sys.stderr)
                time.sleep(wait)
            else:
                raise


# -- Backend convention -------------------------------------------------

def setup(export_dir: Path, *, model: str = "gemini-embedding-001",
          dimensions: int = 768, batch_size: int = 20,
          **kwargs) -> dict:
    """Embed all .md entry files and build a FAISS index.

    Returns a config dict with index_path, mapping_path, model, dimensions.
    """
    export_dir = Path(export_dir)
    entries_dir = export_dir / "entries"
    if not entries_dir.is_dir():
        print(f"Error: {entries_dir} not found. Run export_entries.py first.",
              file=sys.stderr)
        sys.exit(1)

    client = _get_client()

    files = sorted(entries_dir.glob("*.md"))
    print(f"Embedding {len(files)} files with {model} (dim={dimensions})...",
          file=sys.stderr)

    all_embeddings = []
    filenames = []
    failed = 0

    for i in range(0, len(files), batch_size):
        batch_files = files[i:i + batch_size]
        batch_texts = []
        batch_names = []

        for f in batch_files:
            text = f.read_text(encoding="utf-8")
            batch_texts.append(text)
            batch_names.append(f.name)

        try:
            embeddings = _embed_batch(
                client, batch_texts, model, dimensions,
                task_type="RETRIEVAL_DOCUMENT",
            )
            all_embeddings.extend(embeddings)
            filenames.extend(batch_names)
        except Exception as e:
            print(f"  FAIL batch {i}-{i+len(batch_files)}: {e}", file=sys.stderr)
            failed += len(batch_files)

        if (i + batch_size) % 200 == 0 or i + batch_size >= len(files):
            print(f"  {min(i + batch_size, len(files))}/{len(files)} embedded "
                  f"({failed} failed)", file=sys.stderr)

        # Pause to respect rate limits (free tier: ~1500 RPM but low TPM)
        time.sleep(1.5)

    if not all_embeddings:
        print("Error: No embeddings produced.", file=sys.stderr)
        sys.exit(1)

    # Build FAISS index
    vectors = np.array(all_embeddings, dtype=np.float32)
    vectors = _normalize(vectors)

    index = faiss.IndexFlatIP(dimensions)
    index.add(vectors)

    # Save index and mapping
    run_dir = Path("runs") / "gemini_faiss"
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
        "model": model,
        "dimensions": dimensions,
        "files_embedded": len(filenames),
        "files_failed": failed,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return config


def search(query: str, top_k: int, config: dict) -> list[dict]:
    """Embed query and search the FAISS index.

    Returns list of {rank, filename, score, content_preview}.
    """
    global _cached_index, _cached_mapping, _cached_config_path

    index_path = config["index_path"]
    mapping_path = config["mapping_path"]
    model = config["model"]
    dimensions = config["dimensions"]

    # Load index + mapping (cached)
    if _cached_config_path != index_path:
        _cached_index = faiss.read_index(index_path)
        _cached_mapping = json.loads(
            Path(mapping_path).read_text(encoding="utf-8")
        )
        _cached_config_path = index_path

    # Embed query
    client = _get_client()
    result = client.models.embed_content(
        model=model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=dimensions,
        ),
    )
    query_vec = np.array([result.embeddings[0].values], dtype=np.float32)
    query_vec = _normalize(query_vec)

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
