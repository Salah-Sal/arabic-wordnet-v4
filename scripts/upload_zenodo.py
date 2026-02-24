"""Upload a new version of AWN4 to Zenodo.

Usage:
    python scripts/upload_zenodo.py [--dry-run]

Reads ZENODO_TOKEN from .env file. Recompresses awn4.xml → awn4.xml.gz,
creates a new version draft on Zenodo, uploads the file, and publishes.
"""

import gzip
import json
import shutil
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
XML_FILE = OUTPUT / "awn4.xml"
GZ_FILE = OUTPUT / "awn4.xml.gz"

ZENODO_API = "https://zenodo.org/api"
RECORD_ID = "18335226"  # from DOI 10.5281/zenodo.18335226


def load_token():
    load_dotenv(ROOT / ".env")
    token = os.getenv("ZENODO_TOKEN")
    if not token:
        print("Error: ZENODO_TOKEN not found in .env")
        sys.exit(1)
    return token


def recompress():
    """Recompress awn4.xml → awn4.xml.gz if XML is newer."""
    if XML_FILE.stat().st_mtime > GZ_FILE.stat().st_mtime:
        print(f"Recompressing {XML_FILE.name} → {GZ_FILE.name} ...")
        with open(XML_FILE, "rb") as f_in, gzip.open(GZ_FILE, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        size_mb = GZ_FILE.stat().st_size / (1024 * 1024)
        print(f"Done — {size_mb:.1f} MB")
    else:
        print("awn4.xml.gz is up to date, skipping recompression.")


def zenodo_request(method, url, token, **kwargs):
    """Make a Zenodo API request with error handling."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.request(method, url, headers=headers, **kwargs)
    if not resp.ok:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)
    return resp


def main():
    dry_run = "--dry-run" in sys.argv
    token = load_token()

    # Step 1: Recompress
    recompress()

    if dry_run:
        print("\n[DRY RUN] Would create new version, upload, and publish.")
        print(f"  File: {GZ_FILE} ({GZ_FILE.stat().st_size / (1024*1024):.1f} MB)")
        return

    # Step 2: Create new version draft
    print("\nCreating new version draft...")
    resp = zenodo_request(
        "POST",
        f"{ZENODO_API}/deposit/depositions/{RECORD_ID}/actions/newversion",
        token,
    )
    draft_url = resp.json()["links"]["latest_draft"]
    print(f"Draft URL: {draft_url}")

    # Step 3: Get draft details
    draft = zenodo_request("GET", draft_url, token).json()
    draft_id = draft["id"]
    bucket_url = draft["links"]["bucket"]
    print(f"Draft ID: {draft_id}")

    # Step 4: Delete old files from draft (Zenodo copies them from previous version)
    for f in draft.get("files", []):
        print(f"Removing old file: {f['filename']}")
        zenodo_request(
            "DELETE",
            f"{ZENODO_API}/deposit/depositions/{draft_id}/files/{f['id']}",
            token,
        )

    # Step 5: Upload new file
    print(f"\nUploading {GZ_FILE.name}...")
    with open(GZ_FILE, "rb") as fp:
        zenodo_request(
            "PUT",
            f"{bucket_url}/{GZ_FILE.name}",
            token,
            data=fp,
        )
    print("Upload complete.")

    # Step 6: Publish
    print("\nPublishing...")
    resp = zenodo_request(
        "POST",
        f"{ZENODO_API}/deposit/depositions/{draft_id}/actions/publish",
        token,
    )
    published = resp.json()
    doi = published.get("doi", "N/A")
    record_url = published.get("links", {}).get("record_html", "N/A")
    print(f"\nPublished!")
    print(f"  DOI: {doi}")
    print(f"  URL: {record_url}")


if __name__ == "__main__":
    main()
