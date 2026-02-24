#!/usr/bin/env python3
"""Bilingual ColBERTv2 synset retrieval pipeline for AWN4 + OEWN.

Indexes ~110K Arabic synsets and ~121K English synsets into a single
ColBERT index using Jina-ColBERT-v2 (multilingual, cross-lingual aligned).
Supports Arabic, English, and cross-lingual queries.

Usage:
    python colbert_index.py build [--limit N] [--backend voyager|plaid]
    python colbert_index.py search "عقد" [--k 10] [--lang ar|en|all]
    python colbert_index.py interactive
"""

import argparse
import json
import pickle
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:

    def tqdm(iterable, **kwargs):
        return iterable


# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
AWN4_BASE = SCRIPT_DIR.parent.parent
AWN4_XML = AWN4_BASE / "output" / "awn4.xml"
INDEX_DIR = SCRIPT_DIR / "indexes"
META_DIR = SCRIPT_DIR / "metadata"
EMB_DIR = SCRIPT_DIR / "embeddings"

MODEL_NAME = "jinaai/jina-colbert-v2"


# ─── Arabic normalization (from prefilter_dict.py) ────────────────────────────

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
TRAILING_DIGITS_RE = re.compile(r"\d+$")
ARTICLE_RE = re.compile(r"^ال\u0640?")


def strip_diacritics(text):
    """Remove Arabic tashkeel diacritics."""
    return DIACRITICS_RE.sub("", text)


# ─── Data structures ─────────────────────────────────────────────────────────


@dataclass
class SynsetRecord:
    synset_id: str
    ili: str
    pos: str
    lang: str
    lemmas: list
    definition: str
    examples: list = field(default_factory=list)


# ─── Phase 1: Parse AWN4 XML ─────────────────────────────────────────────────


def parse_awn4(xml_path, limit=0):
    """Stream-parse AWN4 XML into SynsetRecord list.

    Uses iterparse + elem.clear() for memory efficiency on the 72 MB file.
    Single pass: collects LexicalEntry → Sense mappings and Synset data,
    then joins them.
    """
    print(f"Parsing AWN4 XML: {xml_path}")
    t0 = time.time()

    # Pass 1: collect lemma→synset and synset→data
    lemma_to_synsets = defaultdict(list)  # synset_id → [(writtenForm, pos)]
    synset_data = {}  # synset_id → {ili, pos, definition, examples}

    current_entry = None
    current_synset_id = None
    current_synset = None

    for event, elem in ET.iterparse(str(xml_path), events=("start", "end")):
        tag = elem.tag

        if event == "start":
            if tag == "LexicalEntry":
                current_entry = {"lemma": "", "pos": "", "synset_ids": []}
            elif tag == "Synset":
                current_synset_id = elem.get("id")
                current_synset = {
                    "ili": elem.get("ili", ""),
                    "pos": elem.get("partOfSpeech", ""),
                    "definition": "",
                    "examples": [],
                }

        elif event == "end":
            if tag == "Lemma" and current_entry is not None:
                current_entry["lemma"] = elem.get("writtenForm", "")
                current_entry["pos"] = elem.get("partOfSpeech", "")

            elif tag == "Sense" and current_entry is not None:
                sid = elem.get("synset", "")
                if sid:
                    current_entry["synset_ids"].append(sid)

            elif tag == "LexicalEntry" and current_entry is not None:
                lemma = current_entry["lemma"]
                for sid in current_entry["synset_ids"]:
                    lemma_to_synsets[sid].append(
                        (lemma, current_entry["pos"])
                    )
                current_entry = None

            elif tag == "Definition" and current_synset is not None:
                current_synset["definition"] = elem.text or ""

            elif tag == "Example" and current_synset is not None:
                if elem.text:
                    current_synset["examples"].append(elem.text)

            elif tag == "Synset" and current_synset is not None:
                synset_data[current_synset_id] = current_synset
                current_synset = None
                current_synset_id = None

            # Free memory
            elem.clear()

    # Join: build SynsetRecord list
    records = []
    for sid, data in synset_data.items():
        lemma_pairs = lemma_to_synsets.get(sid, [])
        lemmas = list(dict.fromkeys(lp[0] for lp in lemma_pairs))  # dedup, preserve order

        records.append(
            SynsetRecord(
                synset_id=sid,
                ili=data["ili"],
                pos=data["pos"],
                lang="ar",
                lemmas=lemmas,
                definition=data["definition"],
                examples=data["examples"],
            )
        )

    if limit > 0:
        records = records[:limit]

    elapsed = time.time() - t0
    print(f"  Parsed {len(synset_data):,} synsets, {sum(len(v) for v in lemma_to_synsets.values()):,} lemma entries in {elapsed:.1f}s")
    if limit > 0:
        print(f"  Limited to {len(records):,} synsets")

    return records


# ─── Phase 2: Load OEWN English synsets ──────────────────────────────────────


def load_oewn(limit=0):
    """Load English synsets from Open English WordNet via the wn package.

    Requires: pip install wn && python -c "import wn; wn.download('oewn:2024')"
    """
    try:
        import wn
    except ImportError:
        print("WARNING: wn package not installed. Skipping English synsets.")
        print("  Install with: pip install wn")
        return []

    print("Loading OEWN English synsets...")
    t0 = time.time()

    try:
        all_synsets = wn.synsets(lang="en")
    except Exception as e:
        print(f"WARNING: Could not load OEWN: {e}")
        print("  Download with: python -c \"import wn; wn.download('oewn:2024')\"")
        return []

    records = []
    for ss in tqdm(all_synsets, desc="  Loading EN synsets"):
        ili_obj = ss.ili
        ili_str = ili_obj.id if ili_obj else ""

        words = ss.words()
        lemmas = [w.lemma() for w in words]

        records.append(
            SynsetRecord(
                synset_id=ss.id,
                ili=ili_str,
                pos=ss.pos,
                lang="en",
                lemmas=lemmas,
                definition=ss.definition() or "",
                examples=ss.examples() or [],
            )
        )

        if limit > 0 and len(records) >= limit:
            break

    elapsed = time.time() - t0
    print(f"  Loaded {len(records):,} English synsets in {elapsed:.1f}s")

    return records


# ─── Phase 3: Build unified document corpus ──────────────────────────────────


def build_document(record):
    """Build a single document string from a SynsetRecord.

    Format: {lemma1}; {lemma2} | {definition} | {example1}. {example2}.
    Arabic lemmas are stripped of diacritics in the document text to match
    typical undiacritized queries.
    """
    if record.lang == "ar":
        lemma_str = "; ".join(strip_diacritics(l) for l in record.lemmas)
    else:
        lemma_str = "; ".join(record.lemmas)

    parts = [lemma_str, record.definition]

    if record.examples:
        parts.append(". ".join(record.examples))

    return " | ".join(p for p in parts if p)


def build_corpus(ar_records, en_records):
    """Build parallel document/ID/metadata structures for indexing.

    Returns:
        documents: list[str] — text to encode
        doc_ids: list[str] — synset IDs
        metadata: dict[str, dict] — synset_id → metadata
        ili_map: dict[str, list[str]] — ILI → [synset_ids]
    """
    all_records = ar_records + en_records
    documents = []
    doc_ids = []
    metadata = {}
    ili_map = defaultdict(list)

    for rec in tqdm(all_records, desc="Building corpus"):
        doc_text = build_document(rec)
        documents.append(doc_text)
        doc_ids.append(rec.synset_id)

        metadata[rec.synset_id] = {
            "synset_id": rec.synset_id,
            "lang": rec.lang,
            "pos": rec.pos,
            "ili": rec.ili,
            "lemmas": rec.lemmas,
            "definition": rec.definition[:200],  # truncate for metadata
        }

        if rec.ili:
            ili_map[rec.ili].append(rec.synset_id)

    print(f"  Corpus: {len(documents):,} documents ({len(ar_records):,} AR + {len(en_records):,} EN)")

    return documents, doc_ids, metadata, dict(ili_map)


# ─── Phase 4: Encode documents ───────────────────────────────────────────────


def load_model(device="cpu"):
    """Load Jina-ColBERT-v2 via PyLate."""
    from pylate import models

    print(f"Loading model: {MODEL_NAME} (device={device})")
    t0 = time.time()

    model = models.ColBERT(
        model_name_or_path=MODEL_NAME,
        query_prefix="[QueryMarker]",
        document_prefix="[DocumentMarker]",
        attend_to_expansion_tokens=True,
        trust_remote_code=True,
        device=device,
    )

    elapsed = time.time() - t0
    print(f"  Model loaded in {elapsed:.1f}s")
    return model


def encode_documents(model, documents, batch_size=8, cache_path=None, force=False):
    """Encode documents into ColBERT multi-vector embeddings.

    Uses chunked encoding with optional caching to disk.
    """
    # Check cache
    if cache_path and Path(cache_path).exists() and not force:
        print(f"  Loading cached embeddings from {cache_path}")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    print(f"  Encoding {len(documents):,} documents (batch_size={batch_size})...")
    t0 = time.time()

    CHUNK_SIZE = 5000
    all_embeddings = []

    for i in range(0, len(documents), CHUNK_SIZE):
        chunk = documents[i : i + CHUNK_SIZE]
        chunk_end = min(i + CHUNK_SIZE, len(documents))
        print(f"    Chunk {i:,}–{chunk_end:,} of {len(documents):,}...")

        chunk_embs = model.encode(
            chunk,
            is_query=False,
            batch_size=batch_size,
            show_progress_bar=True,
        )
        all_embeddings.extend(chunk_embs)

    elapsed = time.time() - t0
    print(f"  Encoded {len(all_embeddings):,} documents in {elapsed:.1f}s ({elapsed / len(documents):.3f}s/doc)")

    # Cache to disk
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        print(f"  Saving embeddings to {cache_path}")
        with open(cache_path, "wb") as f:
            pickle.dump(all_embeddings, f, protocol=pickle.HIGHEST_PROTOCOL)

    return all_embeddings


# ─── Phase 5: Build index ────────────────────────────────────────────────────


def build_index(doc_ids, doc_embeddings, backend="voyager"):
    """Build a ColBERT index from pre-encoded embeddings."""
    from pylate import indexes

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Building {backend} index ({len(doc_ids):,} documents)...")
    t0 = time.time()

    if backend == "voyager":
        index = indexes.Voyager(
            index_folder=str(INDEX_DIR),
            index_name="synset_colbert",
            override=True,
            embedding_size=128,
            M=64,
            ef_construction=200,
        )
    elif backend == "plaid":
        index = indexes.PLAID(
            index_folder=str(INDEX_DIR),
            index_name="synset_colbert",
            override=True,
            nbits=2,
        )
    else:
        raise ValueError(f"Unknown backend: {backend}")

    index = index.add_documents(
        documents_ids=doc_ids,
        documents_embeddings=doc_embeddings,
    )

    elapsed = time.time() - t0
    print(f"  Index built in {elapsed:.1f}s")
    return index


# ─── Phase 6: Search ─────────────────────────────────────────────────────────


def load_metadata():
    """Load saved metadata and ILI map from disk."""
    meta_path = META_DIR / "synset_metadata.json"
    ili_path = META_DIR / "ili_map.json"

    with open(meta_path) as f:
        metadata = json.load(f)
    with open(ili_path) as f:
        ili_map = json.load(f)

    return metadata, ili_map


def load_index(backend="voyager"):
    """Load an existing index from disk."""
    from pylate import indexes

    if backend == "voyager":
        index = indexes.Voyager(
            index_folder=str(INDEX_DIR),
            index_name="synset_colbert",
            override=False,
            embedding_size=128,
        )
    elif backend == "plaid":
        index = indexes.PLAID(
            index_folder=str(INDEX_DIR),
            index_name="synset_colbert",
            override=False,
        )
    return index


def search(query, model, index, metadata, ili_map, k=10, lang="all", pos=None):
    """Search the index for synsets matching the query.

    Returns a list of result dicts with metadata and cross-lingual references.
    """
    from pylate import retrieve

    retriever = retrieve.ColBERT(index=index)

    # Encode query
    query_emb = model.encode(
        [query],
        is_query=True,
        batch_size=1,
    )

    # Over-retrieve for post-filtering
    over_k = k * 5 if (lang != "all" or pos) else k
    results_raw = retriever.retrieve(
        queries_embeddings=query_emb,
        k=over_k,
    )

    # Post-filter and enrich
    filtered = []
    for r in results_raw[0]:
        doc_id = r.id if hasattr(r, "id") else r["id"]
        score = r.score if hasattr(r, "score") else r["score"]

        meta = metadata.get(doc_id)
        if not meta:
            continue

        if lang != "all" and meta["lang"] != lang:
            continue
        if pos and meta["pos"] != pos:
            continue

        # Cross-lingual reference
        cross_ref = None
        ili = meta.get("ili", "")
        if ili and ili in ili_map:
            other_ids = [sid for sid in ili_map[ili] if sid != doc_id]
            if other_ids:
                others = []
                for oid in other_ids[:3]:  # limit cross-refs
                    ometa = metadata.get(oid, {})
                    others.append({
                        "synset_id": oid,
                        "lang": ometa.get("lang", "?"),
                        "lemmas": ometa.get("lemmas", []),
                    })
                cross_ref = others

        filtered.append({
            "rank": len(filtered) + 1,
            "score": float(score),
            "synset_id": doc_id,
            "lang": meta["lang"],
            "pos": meta["pos"],
            "ili": ili,
            "lemmas": meta["lemmas"],
            "definition": meta["definition"],
            "cross_ref": cross_ref,
        })

        if len(filtered) >= k:
            break

    return filtered


def display_results(results, query):
    """Pretty-print search results."""
    print(f'\nResults for "{query}" (top {len(results)}):')
    print("─" * 60)

    for r in results:
        lang_tag = f"[{r['lang']}]"
        lemmas = "; ".join(r["lemmas"][:5])
        print(f"  {r['rank']:2d}. {lang_tag} {r['synset_id']}  ({r['pos']})  score={r['score']:.2f}")
        print(f"      Lemmas: {lemmas}")
        defn = r["definition"][:100]
        print(f"      Def: {defn}{'...' if len(r['definition']) > 100 else ''}")

        if r.get("cross_ref"):
            for xr in r["cross_ref"]:
                xr_lemmas = "; ".join(xr["lemmas"][:3])
                print(f"      ↔ {xr['lang'].upper()}: {xr_lemmas} ({r['ili']})")

        print()

    if not results:
        print("  No results found.")
    print("─" * 60)


def interactive_mode(model, index, metadata, ili_map):
    """Interactive REPL for querying the index."""
    k = 10
    lang = "all"
    pos = None

    print("\nInteractive ColBERT Synset Search")
    print("Commands: :k N, :lang ar|en|all, :pos n|v|a|r|none, :quit")
    print("─" * 60)

    while True:
        try:
            query = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not query:
            continue

        if query == ":quit" or query == ":q":
            print("Goodbye.")
            break
        elif query.startswith(":k "):
            try:
                k = int(query.split()[1])
                print(f"  k set to {k}")
            except ValueError:
                print("  Invalid k value")
            continue
        elif query.startswith(":lang "):
            lang = query.split()[1]
            if lang not in ("ar", "en", "all"):
                print("  Invalid lang. Use: ar, en, all")
                lang = "all"
            else:
                print(f"  lang set to {lang}")
            continue
        elif query.startswith(":pos "):
            val = query.split()[1]
            if val == "none":
                pos = None
                print("  pos filter cleared")
            elif val in ("n", "v", "a", "r"):
                pos = val
                print(f"  pos filter set to {pos}")
            else:
                print("  Invalid pos. Use: n, v, a, r, none")
            continue

        results = search(query, model, index, metadata, ili_map, k=k, lang=lang, pos=pos)
        display_results(results, query)


# ─── CLI ──────────────────────────────────────────────────────────────────────


def cmd_build(args):
    """Build the index: parse → encode → index."""
    # Phase 1: Parse AWN4
    ar_records = parse_awn4(AWN4_XML, limit=args.limit)

    # Phase 2: Load OEWN
    if args.no_english:
        en_records = []
    else:
        en_records = load_oewn(limit=args.limit)

    # Phase 3: Build corpus
    documents, doc_ids, metadata, ili_map = build_corpus(ar_records, en_records)

    # Save metadata
    META_DIR.mkdir(parents=True, exist_ok=True)
    with open(META_DIR / "synset_metadata.json", "w") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=1)
    with open(META_DIR / "ili_map.json", "w") as f:
        json.dump(ili_map, f, ensure_ascii=False, indent=1)
    print(f"  Metadata saved to {META_DIR}/")

    # Phase 4: Encode
    model = load_model(device=args.device)

    EMB_DIR.mkdir(parents=True, exist_ok=True)
    cache_suffix = f"_limit{args.limit}" if args.limit > 0 else ""
    cache_path = EMB_DIR / f"embeddings{cache_suffix}.pkl"

    embeddings = encode_documents(
        model,
        documents,
        batch_size=args.batch_size,
        cache_path=str(cache_path),
        force=args.force_encode,
    )

    # Phase 5: Build index
    index = build_index(doc_ids, embeddings, backend=args.backend)

    # Summary
    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print(f"  Arabic synsets:  {len(ar_records):>8,}")
    print(f"  English synsets: {len(en_records):>8,}")
    print(f"  Total indexed:   {len(doc_ids):>8,}")
    print(f"  Backend:         {args.backend}")
    print(f"  Index dir:       {INDEX_DIR}/synset_colbert/")
    print(f"  Embeddings:      {cache_path}")
    print("=" * 60)


def cmd_search(args):
    """Search the index for a single query."""
    metadata, ili_map = load_metadata()
    model = load_model(device=args.device)
    index = load_index(backend=args.backend)

    results = search(
        args.query, model, index, metadata, ili_map,
        k=args.k, lang=args.lang, pos=args.pos,
    )
    display_results(results, args.query)


def cmd_interactive(args):
    """Launch interactive search REPL."""
    metadata, ili_map = load_metadata()
    model = load_model(device=args.device)
    index = load_index(backend=args.backend)

    interactive_mode(model, index, metadata, ili_map)


def main():
    parser = argparse.ArgumentParser(
        description="Bilingual ColBERTv2 synset retrieval pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- build ---
    build_p = subparsers.add_parser("build", help="Build the index from AWN4 + OEWN")
    build_p.add_argument("--backend", choices=["voyager", "plaid"], default="voyager",
                         help="Index backend (default: voyager)")
    build_p.add_argument("--limit", type=int, default=0,
                         help="Limit synsets per language, 0=all (default: 0)")
    build_p.add_argument("--batch-size", type=int, default=8,
                         help="Encoding batch size (default: 8)")
    build_p.add_argument("--device", default="cpu",
                         help="PyTorch device (default: cpu)")
    build_p.add_argument("--no-english", action="store_true",
                         help="Skip English synsets")
    build_p.add_argument("--force-encode", action="store_true",
                         help="Re-encode even if cache exists")
    build_p.set_defaults(func=cmd_build)

    # --- search ---
    search_p = subparsers.add_parser("search", help="Search for synsets")
    search_p.add_argument("query", help="Search query (Arabic or English)")
    search_p.add_argument("--k", type=int, default=10, help="Number of results (default: 10)")
    search_p.add_argument("--lang", choices=["ar", "en", "all"], default="all",
                          help="Filter by language (default: all)")
    search_p.add_argument("--pos", choices=["n", "v", "a", "r"], default=None,
                          help="Filter by POS")
    search_p.add_argument("--backend", choices=["voyager", "plaid"], default="voyager")
    search_p.add_argument("--device", default="cpu")
    search_p.set_defaults(func=cmd_search)

    # --- interactive ---
    inter_p = subparsers.add_parser("interactive", help="Interactive search REPL")
    inter_p.add_argument("--backend", choices=["voyager", "plaid"], default="voyager")
    inter_p.add_argument("--device", default="cpu")
    inter_p.set_defaults(func=cmd_interactive)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
