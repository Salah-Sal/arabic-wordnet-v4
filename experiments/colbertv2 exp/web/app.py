#!/usr/bin/env python3
"""Flask + HTMX web UI for ColBERT semantic search.

Wraps the search() function from colbert_index.py with a browser interface.
Model and index are loaded once at startup as global singletons.

Usage:
    python app.py                        # direct launch
    python ../colbert_index.py serve     # via CLI subcommand
"""

import sys
import time
from collections import Counter
from pathlib import Path

from flask import Flask, render_template, request, jsonify

# ── Import colbert_index from parent directory ───────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PARENT_DIR))

import colbert_index as ci  # noqa: E402

# ── Flask app ────────────────────────────────────────────────────────────────

app = Flask(__name__,
            template_folder=str(SCRIPT_DIR / "templates"),
            static_folder=str(SCRIPT_DIR / "static"))

# Global singletons — loaded once at startup
MODEL = None
INDEX = None
METADATA = None
ILI_MAP = None
STATS_CACHE = {}


# ── Startup ──────────────────────────────────────────────────────────────────

def startup_load(device="cpu", backend="voyager"):
    """Load model, index, and metadata. Called once at app startup."""
    global MODEL, INDEX, METADATA, ILI_MAP

    print("=" * 60)
    print("ColBERT Search Web UI — Loading resources...")
    print("=" * 60)

    t0 = time.time()

    print("[1/3] Loading metadata...")
    METADATA, ILI_MAP = ci.load_metadata()
    print(f"       {len(METADATA):,} documents, {len(ILI_MAP):,} ILI entries")

    print("[2/3] Loading model...")
    MODEL = ci.load_model(device=device)

    print("[3/3] Loading index...")
    INDEX = ci.load_index(backend=backend)

    elapsed = time.time() - t0
    print(f"\nAll resources loaded in {elapsed:.1f}s")
    print("=" * 60)

    _compute_stats(backend)


def _compute_stats(backend="voyager"):
    """Compute index statistics from loaded metadata."""
    source_counts = Counter()
    lang_counts = Counter()
    pos_counts = Counter()

    for meta in METADATA.values():
        source_counts[meta.get("source_type", "synset")] += 1
        lang_counts[meta.get("lang", "?")] += 1
        pos_counts[meta.get("pos", "?")] += 1

    STATS_CACHE["total_documents"] = len(METADATA)
    STATS_CACHE["total_ili"] = len(ILI_MAP)
    STATS_CACHE["source_count"] = len(source_counts)
    STATS_CACHE["source_counts"] = source_counts.most_common()
    STATS_CACHE["lang_counts"] = lang_counts.most_common()
    STATS_CACHE["pos_counts"] = pos_counts.most_common()
    STATS_CACHE["max_source_count"] = max(source_counts.values()) if source_counts else 1
    STATS_CACHE["max_lang_count"] = max(lang_counts.values()) if lang_counts else 1
    STATS_CACHE["max_pos_count"] = max(pos_counts.values()) if pos_counts else 1
    STATS_CACHE["model_name"] = ci.MODEL_NAME
    STATS_CACHE["index_backend"] = backend

    # File sizes
    index_dir = ci.INDEX_DIR / "synset_colbert"
    if index_dir.exists():
        STATS_CACHE["index_size_mb"] = sum(
            f.stat().st_size for f in index_dir.iterdir() if f.is_file()
        ) / (1024 * 1024)
    else:
        STATS_CACHE["index_size_mb"] = 0

    meta_dir = ci.META_DIR
    if meta_dir.exists():
        STATS_CACHE["metadata_size_mb"] = sum(
            f.stat().st_size for f in meta_dir.iterdir() if f.is_file()
        ) / (1024 * 1024)
    else:
        STATS_CACHE["metadata_size_mb"] = 0


# ── Template filters ─────────────────────────────────────────────────────────

SOURCE_NAMES = {
    "synset": "Synset",
    "dict": "Dictionary",
    "arabterm": "ARABTERM",
}

POS_LABELS = {
    "n": "noun",
    "v": "verb",
    "a": "adj",
    "r": "adv",
}


@app.template_filter("source_name")
def source_name_filter(key):
    return SOURCE_NAMES.get(key, key)


@app.template_filter("pos_label")
def pos_label_filter(key):
    return POS_LABELS.get(key, key)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Search page (empty state with hero stats)."""
    return render_template("index.html", stats=STATS_CACHE)


@app.route("/search")
def search_route():
    """Search endpoint — returns full page or HTMX partial."""
    q = request.args.get("q", "").strip()
    k = request.args.get("k", 10, type=int)
    lang = request.args.get("lang", "all")
    pos = request.args.get("pos", "") or None
    source = request.args.get("source", "all")

    if not q:
        if request.headers.get("HX-Request"):
            return render_template("_results.html", results=[], result_count=0, q="",
                                   search_time="0.00", k=k, lang=lang, pos=pos or "",
                                   source=source)
        return render_template("index.html", stats=STATS_CACHE)

    k = max(1, min(k, 100))

    t0 = time.time()
    results = ci.search(q, MODEL, INDEX, METADATA, ILI_MAP,
                        k=k, lang=lang, pos=pos, source=source)
    search_time = time.time() - t0

    ctx = dict(
        results=results,
        q=q,
        k=k,
        lang=lang,
        pos=pos or "",
        source=source,
        search_time=f"{search_time:.2f}",
        result_count=len(results),
        stats=STATS_CACHE,
    )

    if request.headers.get("HX-Request"):
        return render_template("_results.html", **ctx)
    return render_template("index.html", **ctx)


@app.route("/detail/<path:doc_id>")
def detail(doc_id):
    """HTMX partial for expanded result detail."""
    meta = METADATA.get(doc_id)
    if not meta:
        return "<p>Not found</p>", 404

    # Build cross-references via ILI
    cross_ref = None
    ili = meta.get("ili", "")
    if ili and ili in ILI_MAP:
        other_ids = [sid for sid in ILI_MAP[ili] if sid != doc_id]
        if other_ids:
            cross_ref = []
            for oid in other_ids[:5]:
                ometa = METADATA.get(oid, {})
                cross_ref.append({
                    "synset_id": oid,
                    "lang": ometa.get("lang", "?"),
                    "lemmas": ometa.get("lemmas", []),
                    "definition": ometa.get("definition", ""),
                    "source_type": ometa.get("source_type", "synset"),
                })

    return render_template("_detail.html", meta=meta, cross_ref=cross_ref)


@app.route("/stats")
def stats_page():
    """Statistics dashboard."""
    return render_template("stats.html", stats=STATS_CACHE)


@app.route("/api/health")
def health():
    """JSON health check."""
    return jsonify({
        "status": "ok",
        "documents": len(METADATA) if METADATA else 0,
        "model": ci.MODEL_NAME,
    })


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ColBERT Search Web UI")
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--backend", choices=["voyager", "plaid"], default="voyager")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    startup_load(device=args.device, backend=args.backend)

    print(f"\n  Starting web UI on http://localhost:{args.port}")
    print(f"  Press Ctrl+C to stop.\n")
    app.run(debug=args.debug, port=args.port, threaded=False, use_reloader=False)
