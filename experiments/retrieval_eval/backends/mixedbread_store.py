#!/usr/bin/env python3
"""Mixedbread Store backend — managed chunking, embedding, and retrieval.

Convention:
    setup(export_dir, **kwargs) -> config dict
    search(query, top_k, config) -> list[dict]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from mixedbread import Mixedbread

ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"


def _get_client() -> Mixedbread:
    """Load .env and return an authenticated Mixedbread client."""
    load_dotenv(ENV_PATH)
    api_key = os.getenv("MIXEDBREAD_API_KEY")
    if not api_key:
        print("Error: MIXEDBREAD_API_KEY not found in .env", file=sys.stderr)
        sys.exit(1)
    return Mixedbread(api_key=api_key)


# -- Backend convention -------------------------------------------------

def setup(export_dir: Path, *, store_name: str = "awn4-classical-arabic-dict",
          **kwargs) -> dict:
    """Create a Mixedbread Store and upload all .md entry files.

    Returns a config dict with at least ``store_id``.
    """
    export_dir = Path(export_dir)
    entries_dir = export_dir / "entries"
    if not entries_dir.is_dir():
        print(f"Error: {entries_dir} not found. Run export_entries.py first.",
              file=sys.stderr)
        sys.exit(1)

    mxbai = _get_client()
    info = mxbai.info()
    print(f"Connected to Mixedbread: {info.name} v{info.version}", file=sys.stderr)

    print(f"Creating Store: {store_name}", file=sys.stderr)
    store = mxbai.stores.create(name=store_name)
    print(f"Store created: id={store.id}", file=sys.stderr)

    files = sorted(entries_dir.glob("*.md"))
    print(f"Uploading {len(files)} files...", file=sys.stderr)

    uploaded = 0
    failed = 0
    for i, filepath in enumerate(files):
        try:
            mxbai.stores.files.upload(store_identifier=store.id, file=filepath)
            uploaded += 1
        except Exception as e:
            print(f"  FAIL {filepath.name}: {e}", file=sys.stderr)
            failed += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(files)} uploaded ({failed} failed)",
                  file=sys.stderr)

    print(f"\nUpload complete: {uploaded} ok, {failed} failed", file=sys.stderr)

    config = {
        "store_id": store.id,
        "store_name": store_name,
        "files_uploaded": uploaded,
        "files_failed": failed,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return config


def search(query: str, top_k: int, config: dict) -> list[dict]:
    """Search the Mixedbread Store and return ranked results.

    Returns list of ``{rank, filename, score, content_preview}``.
    """
    mxbai = _get_client()

    response = mxbai.stores.search(
        query=query,
        store_identifiers=[config["store_id"]],
        top_k=top_k,
    )

    retrieved = []
    for i, chunk in enumerate(response.data):
        filename = (getattr(chunk, "filename", None)
                    or getattr(chunk, "file_name", None))
        score = getattr(chunk, "score", None)
        content_preview = ""
        if hasattr(chunk, "content"):
            content_preview = str(chunk.content)[:200]
        elif hasattr(chunk, "text"):
            content_preview = str(chunk.text)[:200]
        retrieved.append({
            "rank": i + 1,
            "filename": str(filename) if filename else None,
            "score": float(score) if score is not None else None,
            "content_preview": content_preview,
        })

    return retrieved
