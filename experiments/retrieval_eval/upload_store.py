#!/usr/bin/env python3
"""Upload exported dictionary entries to a Mixedbread Store.

Creates a Store, uploads all .md files from the export directory, and saves
the store configuration for later evaluation.

Usage:
    python upload_store.py --export-dir export/
    python upload_store.py --export-dir export/ --store-name "my-store"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from mixedbread import Mixedbread

# Load .env from the AWN4 project root
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export-dir", required=True, help="Path to export/ directory")
    parser.add_argument("--store-name", default="awn4-classical-arabic-dict",
                        help="Name for the Mixedbread Store")
    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    entries_dir = export_dir / "entries"
    manifest_path = export_dir / "manifest.json"

    if not entries_dir.is_dir():
        print(f"Error: {entries_dir} not found. Run export_entries.py first.", file=sys.stderr)
        sys.exit(1)

    # Load API key
    load_dotenv(ENV_PATH)
    import os
    api_key = os.getenv("MIXEDBREAD_API_KEY")
    if not api_key:
        print("Error: MIXEDBREAD_API_KEY not found in .env", file=sys.stderr)
        sys.exit(1)

    mxbai = Mixedbread(api_key=api_key)

    # Verify connection
    info = mxbai.info()
    print(f"Connected to Mixedbread: {info.name} v{info.version}", file=sys.stderr)

    # Create Store
    print(f"Creating Store: {args.store_name}", file=sys.stderr)
    store = mxbai.stores.create(name=args.store_name)
    print(f"Store created: id={store.id}", file=sys.stderr)

    # Upload files
    files = sorted(entries_dir.glob("*.md"))
    print(f"Uploading {len(files)} files...", file=sys.stderr)

    uploaded = 0
    failed = 0
    for i, filepath in enumerate(files):
        try:
            mxbai.stores.files.upload(
                store_identifier=store.id,
                file=filepath,
            )
            uploaded += 1
        except Exception as e:
            print(f"  FAIL {filepath.name}: {e}", file=sys.stderr)
            failed += 1

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(files)} uploaded ({failed} failed)", file=sys.stderr)

    print(f"\nUpload complete: {uploaded} ok, {failed} failed", file=sys.stderr)

    # Save store config
    config = {
        "store_id": store.id,
        "store_name": args.store_name,
        "files_uploaded": uploaded,
        "files_failed": failed,
        "manifest": str(manifest_path),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    config_path = Path(__file__).parent / "store_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Config saved: {config_path}", file=sys.stderr)
    print(f"Store ID: {store.id}", file=sys.stderr)


if __name__ == "__main__":
    main()
