#!/usr/bin/env python3
"""fetch_almaany_lemmas.py — Fetch Almaany dictionary data for audit lemmas.

Uses undetected-chromedriver to bypass Cloudflare Turnstile protection
automatically (no manual interaction needed).

Usage:
    # Fetch definitions for all lemmas in the sample (+ connected synsets)
    python fetch_almaany_lemmas.py

    # Custom delay between pages
    python fetch_almaany_lemmas.py --delay 6

    # Re-fetch entries that previously failed
    python fetch_almaany_lemmas.py --retry-errors
"""

import argparse
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import undetected_chromedriver as uc
except ImportError:
    print("Install: pip install undetected-chromedriver")
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
CACHE_FILE = SCRIPT_DIR / "output" / "almaany_cache.json"

SITE_BASE = "https://www.almaany.com/ar/dict/ar-ar"
DEFAULT_DELAY = 5.0
CF_WAIT_MAX = 30  # seconds to wait for Cloudflare auto-resolution

# ─── Arabic normalization ────────────────────────────────────────────────────

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")


def strip_diacritics(text):
    return DIACRITICS_RE.sub("", text)


# ─── HTML parsing ────────────────────────────────────────────────────────────


def parse_almaany_html(html):
    """Parse structured dictionary entries from Almaany HTML.

    Almaany pages have two main sections:
      1. معجم المعاني الجامع  — curated entries with headword, POS, definitions
      2. قاموس الكل           — aggregated entries from multiple dictionaries

    Each section contains an <ol class="meaning-results"> with <li> entries.

    Returns:
        sections: list of dicts with section_name, entries[]
        Each entry: {headword, pos, definition_text, source_dict}
    """
    soup = BeautifulSoup(html, "html.parser")
    sections = []

    # Find section headers (h1.section)
    h1s = soup.find_all("h1", class_="section")
    ols = soup.find_all("ol", class_="meaning-results")

    # Pair each h1 with its following <ol>
    for i, ol in enumerate(ols):
        section_name = h1s[i].get_text(strip=True) if i < len(h1s) else f"Section {i+1}"
        entries = []

        for li in ol.find_all("li", recursive=False):
            entry = _parse_li_entry(li)
            if entry:
                entries.append(entry)

        sections.append({
            "section_name": section_name,
            "num_entries": len(entries),
            "entries": entries,
        })

    return sections


def _parse_li_entry(li):
    """Parse a single <li> entry from a meaning-results list.

    List 1 (المعاني الجامع) structure:
        <li>
            <span>كِتاب: (اسم)</span>
            <ul><li>definition line 1</li><li>definition line 2</li></ul>
        </li>

    List 2 (قاموس الكل) structure:
        <li>
            كُتّاب كتاب - ج، كتب ... المعجم: الرائد
        </li>
    """
    full_text = li.get_text(separator=" ", strip=True)
    if not full_text or len(full_text) < 5:
        return None

    # Try to extract POS from parenthetical like (اسم) or (فعل)
    pos_match = re.search(r"\((\s*(?:اسم|فعل|صفة|حرف|ظرف|مصطلحات)[^)]*)\)", full_text)
    pos = pos_match.group(1).strip() if pos_match else ""

    # Try to extract dictionary source from "المعجم: ..."
    source_match = re.search(r"المعجم\s*:\s*(.+?)(?:\s*$)", full_text)
    source_dict = source_match.group(1).strip() if source_match else ""

    # Extract headword from the first <span> or beginning of text
    span = li.find("span", recursive=False)
    if span:
        headword_text = span.get_text(strip=True)
        # Strip POS annotation
        headword = re.sub(r"\s*:\s*\(.*?\)\s*$", "", headword_text).strip()
    else:
        # First word(s) before the definition
        headword = full_text.split()[0] if full_text else ""

    # Extract definition lines from <ul><li> children
    inner_ul = li.find("ul", recursive=False)
    if inner_ul:
        def_lines = []
        for inner_li in inner_ul.find_all("li"):
            line = inner_li.get_text(strip=True)
            if line:
                def_lines.append(line)
        definition_text = "\n".join(def_lines)
    else:
        # Flat text entry (list 2 style) — use full text minus headword
        definition_text = full_text

    return {
        "headword": headword,
        "pos": pos,
        "source_dict": source_dict,
        "definition_text": definition_text[:2000],
    }


# ─── Cloudflare handling ─────────────────────────────────────────────────────


def wait_for_cloudflare(driver, timeout=CF_WAIT_MAX):
    """Wait for Cloudflare Turnstile to auto-resolve. Returns True if resolved."""
    for _ in range(timeout):
        title = driver.title
        if ("لحظة" not in title
                and "moment" not in title.lower()
                and "challenge" not in title.lower()
                and "security" not in title.lower()):
            return True
        time.sleep(1)
    return False


# ─── Lemma collection ────────────────────────────────────────────────────────


def collect_lemmas(sample_path, awn4_xml_path):
    """Collect all unique lemma bare forms from sample synsets + connected synsets."""
    with open(sample_path) as f:
        sample = json.load(f)

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

    all_synset_ids = set()
    for synset in sample["synsets"]:
        all_synset_ids.add(synset["id"])
        for rel in synset.get("relations", []):
            all_synset_ids.add(rel["target"])

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
    single, multi = collect_lemmas(Path(args.sample), Path(args.awn4_xml))
    print(f"  {len(single)} single-word lemmas, {len(multi)} multi-word (skipped)")

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
                continue
            if not args.retry_errors:
                continue
        to_fetch.append((bare, originals))

    if not to_fetch:
        print("\nAll lemmas already cached. Nothing to fetch.")
        return

    print(f"\nWill fetch {len(to_fetch)} lemmas from Almaany "
          f"(delay={args.delay}s, headless={args.headless}).")

    # Launch undetected Chrome
    options = uc.ChromeOptions()
    options.add_argument("--lang=ar")
    if args.headless:
        options.add_argument("--headless=new")

    driver = uc.Chrome(options=options, headless=args.headless)
    found = 0
    not_found = 0
    cf_ok = False

    try:
        for i, (bare, originals) in enumerate(to_fetch, 1):
            slug = urllib.parse.quote(bare, safe="")
            url = f"{SITE_BASE}/{slug}/"

            print(f"  [{i}/{len(to_fetch)}] {bare} ({', '.join(originals)})...",
                  end=" ", flush=True)

            driver.get(url)

            # First page: wait for Cloudflare auto-resolution
            if not cf_ok:
                print("(waiting for Cloudflare)...", end=" ", flush=True)
                cf_ok = wait_for_cloudflare(driver)
                if not cf_ok:
                    print("CLOUDFLARE BLOCKED — aborting.")
                    break
                # Extra wait for first page content
                time.sleep(3)
            else:
                time.sleep(args.delay)

            # Verify we're on a real content page
            title = driver.title
            current_url = driver.current_url

            if "moment" in title.lower() or "لحظة" in title:
                # Cloudflare re-challenged mid-session
                print("(re-challenged)...", end=" ", flush=True)
                cf_ok = wait_for_cloudflare(driver, timeout=60)
                if not cf_ok:
                    print("BLOCKED")
                    cache[bare] = _make_cache_entry(bare, originals, current_url, title, False)
                    not_found += 1
                    _save_cache(cache, cache_path)
                    continue
                time.sleep(2)
                title = driver.title
                current_url = driver.current_url

            # Get page source and parse
            html = driver.page_source
            sections = parse_almaany_html(html)

            total_entries = sum(s["num_entries"] for s in sections)

            if total_entries > 0:
                print(f"OK — {total_entries} entries across {len(sections)} sections")
                cache[bare] = {
                    "bare_form": bare,
                    "written_forms": originals,
                    "url": current_url,
                    "title": title,
                    "found": True,
                    "num_entries": total_entries,
                    "sections": sections,
                }
                found += 1
            else:
                print("NO ENTRIES")
                cache[bare] = _make_cache_entry(bare, originals, current_url, title, False)
                not_found += 1

            _save_cache(cache, cache_path)

    except KeyboardInterrupt:
        print("\n\nInterrupted — saving cache...")
    finally:
        driver.quit()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s — {found} found, {not_found} not found")
    print(f"Cache: {cache_path}")
    print(f"Total cached: {len(cache)} entries")


def _make_cache_entry(bare, originals, url, title, found):
    return {
        "bare_form": bare,
        "written_forms": originals,
        "url": url,
        "title": title,
        "found": found,
        "num_entries": 0,
        "sections": [],
    }


def _save_cache(cache, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Almaany dictionary definitions for AWN4 audit lemmas"
    )
    parser.add_argument("--sample", default=str(SAMPLE_JSON))
    parser.add_argument("--awn4-xml", default=str(AWN4_XML))
    parser.add_argument("-o", "--output", default=str(CACHE_FILE))
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Seconds between page loads (default: {DEFAULT_DELAY})")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Re-attempt entries that previously failed")
    parser.add_argument("--headless", action="store_true",
                        help="Run Chrome in headless mode (may trigger Cloudflare)")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
