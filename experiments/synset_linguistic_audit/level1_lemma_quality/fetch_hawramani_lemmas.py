#!/usr/bin/env python3
"""fetch_hawramani_lemmas.py — Fetch Hawramani dictionary data for audit lemmas.

Targeted scraper that fetches dictionary definitions from arabiclexicon.hawramani.com
for the specific lemmas in our AWN4 synset audit sample. Only fetches single-word
lemmas (multi-word expressions are skipped since Hawramani is headword-based).

Usage:
    # Fetch definitions for all lemmas in the sample (+ connected synsets)
    python fetch_hawramani_lemmas.py

    # Custom sample and output paths
    python fetch_hawramani_lemmas.py --sample path/to/sample.json -o output/hawramani_cache.json

    # Adjust request delay (default: 5s between requests)
    python fetch_hawramani_lemmas.py --delay 8

    # Re-fetch entries that got 404 (skip already-fetched)
    python fetch_hawramani_lemmas.py --retry-404
"""

import argparse
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install: pip install requests")
    raise SystemExit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install beautifulsoup4")
    raise SystemExit(1)

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
AWN4_BASE = SCRIPT_DIR.parent.parent.parent  # arabic-wordnet-v4/
AWN4_XML = AWN4_BASE / "output" / "awn4.xml"
SAMPLE_JSON = SCRIPT_DIR / "output" / "random_synset_sample.json"
CACHE_FILE = SCRIPT_DIR / "output" / "hawramani_cache.json"

SITE_BASE = "https://arabiclexicon.hawramani.com"
DEFAULT_DELAY = 5.0
REQUEST_TIMEOUT = 30

# ─── Arabic normalization ────────────────────────────────────────────────────

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")


def strip_diacritics(text):
    """Remove Arabic diacritical marks (tashkeel)."""
    return DIACRITICS_RE.sub("", text)


# ─── HTML parsing ────────────────────────────────────────────────────────────


def parse_definitions(html):
    """Parse definition containers from a Hawramani headword page.

    Each page has <div class="definition-container dictionary_XX"> blocks,
    one per dictionary entry. Returns a list of dicts with dictionary name
    and definition text.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    containers = soup.find_all(
        "div", class_=lambda c: c and "definition-container" in c
    )

    for container in containers:
        # Extract dictionary ID from class="definition-container dictionary_XX"
        classes = container.get("class", [])
        dict_classes = [c for c in classes if c.startswith("dictionary_")]
        if not dict_classes:
            continue
        try:
            html_dict_id = int(dict_classes[0].replace("dictionary_", ""))
        except ValueError:
            continue

        # Extract dictionary name from credits div
        dict_name_en = ""
        dict_name_ar = ""
        credits_div = container.find("div", class_="credits")
        if credits_div:
            credit_a = credits_div.find("a")
            if credit_a:
                full_text = credit_a.get_text(strip=True)
                ar_span = credit_a.find("span", class_="ar")
                if ar_span:
                    dict_name_ar = ar_span.get_text(strip=True)
                    dict_name_en = full_text.replace(dict_name_ar, "").strip()
                else:
                    dict_name_en = full_text

        # Extract definition text
        defn_div = container.find("div", class_="definition")
        if not defn_div:
            continue

        defn_text = defn_div.get_text(separator="\n", strip=True)
        if not defn_text or len(defn_text) < 2:
            continue

        results.append({
            "html_dict_id": html_dict_id,
            "dict_name_en": dict_name_en,
            "dict_name_ar": dict_name_ar,
            "definition_text": defn_text,
        })

    return results


# ─── HTTP fetching ───────────────────────────────────────────────────────────


def make_session():
    """Create an HTTP session with proper headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "AWN4-Audit/1.0 (Academic Arabic WordNet research)",
        "Accept": "text/html,application/xhtml+xml",
    })
    return session


def fetch_page(bare_form, session, delay, retries=3):
    """Fetch the Hawramani page for a bare headword. Returns (html, url) or (None, url)."""
    slug = urllib.parse.quote(bare_form, safe="")
    url = f"{SITE_BASE}/{slug}/"

    for attempt in range(retries):
        time.sleep(delay if attempt == 0 else 60 * attempt)
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text, url
            elif resp.status_code == 404:
                return None, url
            elif resp.status_code == 429:
                print(f"    429 — backing off {60 * (attempt + 1)}s (attempt {attempt + 1}/{retries})...")
                continue
            else:
                print(f"    HTTP {resp.status_code} for {bare_form}")
                return None, url
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < retries - 1:
                print(f"    {type(e).__name__} — retrying in {60 * (attempt + 1)}s...")
                # Rebuild session on connection errors
                session.close()
                session.headers.update({
                    "User-Agent": "AWN4-Audit/1.0 (Academic Arabic WordNet research)",
                    "Accept": "text/html,application/xhtml+xml",
                })
                continue
            print(f"    {type(e).__name__} for {bare_form} (gave up after {retries} attempts)")
            return None, url

    print(f"    Failed after {retries} attempts")
    return None, url


# ─── Lemma collection ────────────────────────────────────────────────────────


def collect_lemmas(sample_path, awn4_xml_path):
    """Collect all unique lemma bare forms from sample synsets + connected synsets.

    Returns (single_word_map, multi_word_map) where each maps
    bare_form → [original_written_forms].
    """
    with open(sample_path) as f:
        sample = json.load(f)

    # Parse AWN4 XML to get lemmas for connected synsets
    print(f"  Parsing AWN4 XML: {awn4_xml_path.name}")
    tree = ET.parse(awn4_xml_path)
    root = tree.getroot()
    lexicon = root.find("Lexicon")

    synset_lemmas = {}
    for entry in lexicon.findall("LexicalEntry"):
        lemma_el = entry.find("Lemma")
        wf = lemma_el.get("writtenForm")
        for sense in entry.findall("Sense"):
            sid = sense.get("synset")
            if sid not in synset_lemmas:
                synset_lemmas[sid] = []
            synset_lemmas[sid].append(wf)

    # All synset IDs: primary sample + 1-hop connected
    all_synset_ids = set()
    for synset in sample["synsets"]:
        all_synset_ids.add(synset["id"])
        for rel in synset.get("relations", []):
            all_synset_ids.add(rel["target"])

    # Collect bare forms → original forms
    all_bare = {}
    for sid in all_synset_ids:
        if sid in synset_lemmas:
            for wf in synset_lemmas[sid]:
                bare = strip_diacritics(wf)
                if bare not in all_bare:
                    all_bare[bare] = []
                if wf not in all_bare[bare]:
                    all_bare[bare].append(wf)

    single = {k: v for k, v in all_bare.items() if " " not in k.strip()}
    multi = {k: v for k, v in all_bare.items() if " " in k.strip()}

    return single, multi


# ─── Main pipeline ───────────────────────────────────────────────────────────


def run(args):
    t0 = time.time()

    print("Collecting lemmas from sample + connected synsets...")
    single, multi = collect_lemmas(
        Path(args.sample), Path(args.awn4_xml)
    )
    print(f"  {len(single)} single-word lemmas, {len(multi)} multi-word (skipped)")

    if multi:
        print(f"  Skipping multi-word: {', '.join(sorted(multi.keys())[:8])}...")

    # Load existing cache
    cache_path = Path(args.output)
    cache = {}
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"  Loaded existing cache: {len(cache)} entries")

    # Determine which lemmas need fetching
    to_fetch = []
    for bare, originals in sorted(single.items()):
        if bare in cache:
            entry = cache[bare]
            if entry.get("found"):
                continue  # already have good data
            if not args.retry_404 and not args.retry_errors:
                continue  # skip failed entries unless retrying
        to_fetch.append((bare, originals))

    if not to_fetch:
        print("\nAll lemmas already cached. Nothing to fetch.")
        print(f"Cache: {cache_path}")
        return

    print(f"\nFetching {len(to_fetch)} lemmas from Hawramani (delay={args.delay}s)...")
    session = make_session()
    found = 0
    not_found = 0

    for i, (bare, originals) in enumerate(to_fetch, 1):
        print(f"  [{i}/{len(to_fetch)}] {bare} ({', '.join(originals)})...", end=" ", flush=True)

        html, url = fetch_page(bare, session, args.delay)

        if html is None:
            print("NOT FOUND")
            cache[bare] = {
                "bare_form": bare,
                "written_forms": originals,
                "url": url,
                "found": False,
                "num_dictionaries": 0,
                "definitions": [],
            }
            not_found += 1
        else:
            defs = parse_definitions(html)
            print(f"OK — {len(defs)} dictionaries")
            cache[bare] = {
                "bare_form": bare,
                "written_forms": originals,
                "url": url,
                "found": True,
                "num_dictionaries": len(defs),
                "definitions": defs,
            }
            found += 1

        # Save after each fetch (resume-safe)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s — {found} found, {not_found} not found")
    print(f"Cache: {cache_path}")
    print(f"Total cached: {len(cache)} entries")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Hawramani dictionary definitions for AWN4 audit lemmas"
    )
    parser.add_argument(
        "--sample", default=str(SAMPLE_JSON),
        help="Path to random_synset_sample.json"
    )
    parser.add_argument(
        "--awn4-xml", default=str(AWN4_XML),
        help="Path to awn4.xml"
    )
    parser.add_argument(
        "-o", "--output", default=str(CACHE_FILE),
        help="Output cache JSON path (default: output/hawramani_cache.json)"
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY,
        help=f"Seconds between requests (default: {DEFAULT_DELAY})"
    )
    parser.add_argument(
        "--retry-404", action="store_true",
        help="Re-attempt entries that previously got 404"
    )
    parser.add_argument(
        "--retry-errors", action="store_true",
        help="Re-attempt entries that previously failed (404, connection errors, etc.)"
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
