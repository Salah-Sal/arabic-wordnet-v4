#!/usr/bin/env python3
"""A/B test: Jaccard vs ColBERT MaxSim for Arabic definition similarity.

Compares the current Jaccard-based definition_similarity() used in the RAG
pipeline's scoring function (weight 0.45) against ColBERT MaxSim scoring
using Jina-ColBERT-v2 embeddings.

For each polysemous headword group (5+ entries across different dictionaries),
computes both Jaccard and MaxSim pairwise similarity, then compares rankings
to determine whether ColBERT provides better semantic discrimination.

Usage:
    python ab_test_jaccard_vs_maxsim.py [--n-groups 50] [--min-entries 5]
                                        [--device cpu] [--batch-size 8]
                                        [--output results.json]
                                        [--jaccard-only]

Dependencies:
    - arabic_dict.db (the 760K-entry dictionary database)
    - pylate + jinaai/jina-colbert-v2 (for ColBERT scoring)
    - RAG pipeline's similarity.py (for Jaccard scoring)
"""

import argparse
import json
import sqlite3
import sys
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
# arabic-dictionaries is a sibling of arabic-wordnet-v4
DICT_ROOT = SCRIPT_DIR.parents[2] / "arabic-dictionaries"
DB_PATH = DICT_ROOT / "db" / "arabic_dict.db"
RAG_DIR = DICT_ROOT / "extraction" / "rag"
EXTRACTION_DIR = DICT_ROOT / "extraction"

# Add extraction/ to path so the RAG package can import common.py
sys.path.insert(0, str(EXTRACTION_DIR))
sys.path.insert(0, str(RAG_DIR.parent))

from rag.similarity import definition_similarity  # noqa: E402

# ── ColBERT model setup ──────────────────────────────────────────────────────

MODEL_NAME = "jinaai/jina-colbert-v2"


def load_colbert_model(device="cpu"):
    """Load Jina-ColBERT-v2 via PyLate. Returns None if PyLate unavailable."""
    try:
        from pylate import models
    except ImportError:
        print("WARNING: pylate not installed. Running Jaccard-only mode.")
        print("  Install with: pip install pylate einops>=0.8.1")
        return None

    print(f"Loading ColBERT model: {MODEL_NAME} (device={device})")
    t0 = time.time()
    model = models.ColBERT(
        model_name_or_path=MODEL_NAME,
        query_prefix="[QueryMarker]",
        document_prefix="[DocumentMarker]",
        attend_to_expansion_tokens=True,
        trust_remote_code=True,
        device=device,
    )
    print(f"  Model loaded in {time.time() - t0:.1f}s")
    return model


def maxsim_numpy(query_emb: np.ndarray, doc_emb: np.ndarray) -> float:
    """Compute ColBERT MaxSim between two token embedding arrays.

    Both arrays should already be L2-normalized (PyLate does this by default).

    Args:
        query_emb: shape (Q, D) — Q query tokens, D dimensions
        doc_emb:   shape (T, D) — T document tokens, D dimensions

    Returns:
        MaxSim score (sum of per-query-token max cosine similarities).
    """
    # Dot product = cosine similarity since embeddings are L2-normalized
    sim_matrix = query_emb @ doc_emb.T  # (Q, T)
    return float(sim_matrix.max(axis=1).sum())


# ── Database queries ─────────────────────────────────────────────────────────

def select_polysemous_groups(db_path: Path, min_entries: int = 5,
                              n_groups: int = 50) -> list[dict]:
    """Find headwords with the most entries across different dictionaries.

    Returns list of {headword_norm, count, entries: [{id, source, dictionary_id,
    headword, definitions_text}]}.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Find headword_norm values with the most entries from distinct dictionaries
    rows = conn.execute("""
        SELECT headword_norm, COUNT(*) as cnt, COUNT(DISTINCT dictionary_id) as n_dicts
        FROM entries
        WHERE definitions_text IS NOT NULL
          AND LENGTH(definitions_text) > 20
          AND headword_norm IS NOT NULL
        GROUP BY headword_norm
        HAVING cnt >= ? AND n_dicts >= 3
        ORDER BY n_dicts DESC, cnt DESC
        LIMIT ?
    """, (min_entries, n_groups * 2)).fetchall()  # over-fetch, then filter

    groups = []
    for row in rows:
        if len(groups) >= n_groups:
            break

        hw_norm = row["headword_norm"]
        entries = conn.execute("""
            SELECT e.id, d.key AS source, e.dictionary_id, e.headword,
                   e.definitions_text
            FROM entries e
            JOIN dictionaries d ON e.dictionary_id = d.id
            WHERE e.headword_norm = ?
              AND e.definitions_text IS NOT NULL
              AND LENGTH(e.definitions_text) > 20
            ORDER BY d.key, e.id
            LIMIT 30
        """, (hw_norm,)).fetchall()

        if len(entries) < min_entries:
            continue

        groups.append({
            "headword_norm": hw_norm,
            "count": len(entries),
            "n_dicts": row["n_dicts"],
            "entries": [dict(e) for e in entries],
        })

    conn.close()
    print(f"Selected {len(groups)} polysemous headword groups "
          f"(min {min_entries} entries, >=3 dictionaries)")
    return groups


# ── Pairwise scoring ─────────────────────────────────────────────────────────

def compute_jaccard_pairs(entries: list[dict]) -> dict[tuple[int, int], float]:
    """Compute Jaccard definition_similarity for all pairs."""
    scores = {}
    for i, j in combinations(range(len(entries)), 2):
        def_a = entries[i]["definitions_text"]
        def_b = entries[j]["definitions_text"]
        sim = definition_similarity(def_a, def_b)
        id_a, id_b = entries[i]["id"], entries[j]["id"]
        scores[(id_a, id_b)] = sim
    return scores


def compute_maxsim_pairs(entries: list[dict], model,
                          batch_size: int = 8) -> dict[tuple[int, int], float]:
    """Encode definitions and compute MaxSim for all pairs.

    Encodes all definitions as documents (is_query=False) since both sides
    are dictionary definitions. This matches the pipeline's use case where
    candidate definitions are precomputed.
    """
    definitions = [e["definitions_text"] for e in entries]

    # Encode all definitions as documents
    embeddings = model.encode(
        definitions,
        is_query=False,
        batch_size=batch_size,
        show_progress_bar=False,
    )

    # Compute MaxSim for all pairs
    scores = {}
    for i, j in combinations(range(len(entries)), 2):
        ms = maxsim_numpy(embeddings[i], embeddings[j])
        id_a, id_b = entries[i]["id"], entries[j]["id"]
        scores[(id_a, id_b)] = ms
    return scores


# ── Ranking comparison ───────────────────────────────────────────────────────

def kendall_tau(ranking_a: list, ranking_b: list) -> float:
    """Compute Kendall's tau rank correlation between two rankings.

    Both inputs are lists of (pair_key, score) sorted by score descending.
    Returns tau in [-1.0, 1.0] where 1.0 = perfect agreement.
    """
    n = len(ranking_a)
    if n < 2:
        return 1.0

    # Build rank maps
    rank_a = {item[0]: i for i, item in enumerate(ranking_a)}
    rank_b = {item[0]: i for i, item in enumerate(ranking_b)}

    # Count concordant and discordant pairs
    keys = list(rank_a.keys())
    concordant = 0
    discordant = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ki, kj = keys[i], keys[j]
            a_diff = rank_a[ki] - rank_a[kj]
            b_diff = rank_b[ki] - rank_b[kj]
            if a_diff * b_diff > 0:
                concordant += 1
            elif a_diff * b_diff < 0:
                discordant += 1
            # ties are neither concordant nor discordant

    total = concordant + discordant
    if total == 0:
        return 1.0
    return (concordant - discordant) / total


def analyze_group(group: dict, jaccard_scores: dict,
                  maxsim_scores: dict | None) -> dict:
    """Analyze one headword group's scoring agreement/disagreement."""
    pairs = list(jaccard_scores.keys())

    # Rank by Jaccard (descending)
    jac_ranked = sorted(pairs, key=lambda p: jaccard_scores[p], reverse=True)
    jac_ranking = [(p, jaccard_scores[p]) for p in jac_ranked]

    result = {
        "headword": group["headword_norm"],
        "n_entries": group["count"],
        "n_dicts": group["n_dicts"],
        "n_pairs": len(pairs),
        "jaccard_stats": {
            "mean": float(np.mean([jaccard_scores[p] for p in pairs])),
            "median": float(np.median([jaccard_scores[p] for p in pairs])),
            "std": float(np.std([jaccard_scores[p] for p in pairs])),
            "min": float(min(jaccard_scores[p] for p in pairs)),
            "max": float(max(jaccard_scores[p] for p in pairs)),
        },
    }

    if maxsim_scores is not None:
        ms_ranked = sorted(pairs, key=lambda p: maxsim_scores[p], reverse=True)
        ms_ranking = [(p, maxsim_scores[p]) for p in ms_ranked]

        # Kendall's tau
        tau = kendall_tau(jac_ranking, ms_ranking)

        ms_values = [maxsim_scores[p] for p in pairs]
        result["maxsim_stats"] = {
            "mean": float(np.mean(ms_values)),
            "median": float(np.median(ms_values)),
            "std": float(np.std(ms_values)),
            "min": float(min(ms_values)),
            "max": float(max(ms_values)),
        }
        result["kendall_tau"] = tau

        # Find top disagreements (where rankings differ most)
        jac_rank_map = {p: i for i, (p, _) in enumerate(jac_ranking)}
        ms_rank_map = {p: i for i, (p, _) in enumerate(ms_ranking)}

        disagreements = []
        for p in pairs:
            rank_diff = abs(jac_rank_map[p] - ms_rank_map[p])
            if rank_diff >= 3:  # at least 3 positions apart
                disagreements.append({
                    "pair": [p[0], p[1]],
                    "jaccard_rank": jac_rank_map[p],
                    "maxsim_rank": ms_rank_map[p],
                    "rank_diff": rank_diff,
                    "jaccard_score": jaccard_scores[p],
                    "maxsim_score": maxsim_scores[p],
                })
        disagreements.sort(key=lambda d: d["rank_diff"], reverse=True)
        result["top_disagreements"] = disagreements[:5]

    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="A/B test: Jaccard vs ColBERT MaxSim for Arabic definitions"
    )
    parser.add_argument("--n-groups", type=int, default=50,
                        help="Number of polysemous headword groups (default: 50)")
    parser.add_argument("--min-entries", type=int, default=5,
                        help="Minimum entries per headword (default: 5)")
    parser.add_argument("--device", default="cpu",
                        help="PyTorch device (default: cpu)")
    parser.add_argument("--batch-size", type=int, default=8,
                        help="ColBERT encoding batch size (default: 8)")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: stdout summary only)")
    parser.add_argument("--jaccard-only", action="store_true",
                        help="Skip ColBERT, only compute Jaccard baselines")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    # ── Step 1: Select polysemous headwords ────────────────────────────
    print("=" * 60)
    print("A/B TEST: Jaccard vs ColBERT MaxSim")
    print("=" * 60)

    groups = select_polysemous_groups(DB_PATH, args.min_entries, args.n_groups)
    if not groups:
        print("No polysemous groups found. Try lowering --min-entries.")
        sys.exit(1)

    total_entries = sum(g["count"] for g in groups)
    total_pairs = sum(g["count"] * (g["count"] - 1) // 2 for g in groups)
    print(f"  Total entries: {total_entries:,}")
    print(f"  Total pairwise comparisons: {total_pairs:,}")

    # ── Step 2: Load ColBERT model (if not jaccard-only) ──────────────
    model = None
    if not args.jaccard_only:
        model = load_colbert_model(device=args.device)
        if model is None:
            print("Falling back to Jaccard-only mode.")

    # ── Step 3: Compute scores for each group ─────────────────────────
    results = []
    all_maxsim_raw = []  # for normalization calibration

    for i, group in enumerate(groups):
        hw = group["headword_norm"]
        n = group["count"]
        print(f"\n[{i+1}/{len(groups)}] {hw} ({n} entries, {group['n_dicts']} dicts)")

        # Jaccard scores
        t0 = time.time()
        jac_scores = compute_jaccard_pairs(group["entries"])
        jac_ms = (time.time() - t0) * 1000
        print(f"  Jaccard: {len(jac_scores)} pairs in {jac_ms:.0f}ms")

        # MaxSim scores
        ms_scores = None
        if model is not None:
            t0 = time.time()
            ms_scores = compute_maxsim_pairs(
                group["entries"], model, batch_size=args.batch_size
            )
            ms_ms = (time.time() - t0) * 1000
            print(f"  MaxSim:  {len(ms_scores)} pairs in {ms_ms:.0f}ms")
            all_maxsim_raw.extend(ms_scores.values())

        # Analyze
        analysis = analyze_group(group, jac_scores, ms_scores)
        results.append(analysis)

        # Print summary
        jac_s = analysis["jaccard_stats"]
        print(f"  Jaccard  mean={jac_s['mean']:.3f}  std={jac_s['std']:.3f}  "
              f"range=[{jac_s['min']:.3f}, {jac_s['max']:.3f}]")
        if "maxsim_stats" in analysis:
            ms_s = analysis["maxsim_stats"]
            print(f"  MaxSim   mean={ms_s['mean']:.1f}  std={ms_s['std']:.1f}  "
                  f"range=[{ms_s['min']:.1f}, {ms_s['max']:.1f}]")
            print(f"  Kendall tau = {analysis['kendall_tau']:.3f}")
            if analysis["top_disagreements"]:
                print(f"  Top disagreement: rank diff = "
                      f"{analysis['top_disagreements'][0]['rank_diff']}")

    # ── Step 4: Aggregate analysis ────────────────────────────────────
    print("\n" + "=" * 60)
    print("AGGREGATE RESULTS")
    print("=" * 60)

    jac_means = [r["jaccard_stats"]["mean"] for r in results]
    print(f"Jaccard mean similarity across groups: {np.mean(jac_means):.3f} "
          f"(std={np.std(jac_means):.3f})")

    if all_maxsim_raw:
        ms_arr = np.array(all_maxsim_raw)
        taus = [r["kendall_tau"] for r in results if "kendall_tau" in r]

        print(f"\nMaxSim raw score distribution (N={len(ms_arr):,}):")
        for pct in [5, 25, 50, 75, 95]:
            print(f"  P{pct:2d}: {np.percentile(ms_arr, pct):.1f}")
        print(f"  Mean: {ms_arr.mean():.1f}  Std: {ms_arr.std():.1f}")

        print(f"\nKendall's tau (Jaccard vs MaxSim ranking agreement):")
        print(f"  Mean tau:   {np.mean(taus):.3f}")
        print(f"  Median tau: {np.median(taus):.3f}")
        print(f"  Std tau:    {np.std(taus):.3f}")
        print(f"  Range:      [{min(taus):.3f}, {max(taus):.3f}]")

        # Groups with highest disagreement (lowest tau)
        low_tau = sorted(results, key=lambda r: r.get("kendall_tau", 1.0))[:5]
        print(f"\nTop 5 groups with LOWEST agreement (MaxSim disagrees most):")
        for r in low_tau:
            tau = r.get("kendall_tau", "N/A")
            print(f"  {r['headword']:>10s}  tau={tau:.3f}  "
                  f"({r['n_entries']} entries, {r['n_pairs']} pairs)")

        # Normalization calibration
        print(f"\n{'─' * 40}")
        print("NORMALIZATION CALIBRATION")
        print(f"{'─' * 40}")
        print("To map MaxSim raw scores to [0, 1] for the scoring function:")
        p5 = np.percentile(ms_arr, 5)
        p95 = np.percentile(ms_arr, 95)
        print(f"  Recommended: normalize = (raw - {p5:.1f}) / ({p95:.1f} - {p5:.1f})")
        print(f"  This maps P5→0.0, P95→1.0")
        print(f"  Compare to proposal's: min(raw / 20.0, 1.0)")
        proposed_norm = np.clip(ms_arr / 20.0, 0, 1)
        calibrated_norm = np.clip((ms_arr - p5) / (p95 - p5), 0, 1)
        print(f"  Proposal normalization mean: {proposed_norm.mean():.3f}")
        print(f"  Calibrated normalization mean: {calibrated_norm.mean():.3f}")

        # Total disagreements
        total_disagree = sum(
            len(r.get("top_disagreements", [])) for r in results
        )
        print(f"\nPairs with rank diff >= 3: {total_disagree}")

    # ── Step 5: Save results ──────────────────────────────────────────
    if args.output:
        output = {
            "config": {
                "n_groups": len(results),
                "min_entries": args.min_entries,
                "model": MODEL_NAME if model else None,
                "device": args.device,
            },
            "aggregate": {
                "jaccard_mean": float(np.mean(jac_means)),
            },
            "groups": results,
        }
        if all_maxsim_raw:
            output["aggregate"]["maxsim_percentiles"] = {
                f"p{p}": float(np.percentile(ms_arr, p))
                for p in [5, 10, 25, 50, 75, 90, 95]
            }
            output["aggregate"]["kendall_tau_mean"] = float(np.mean(taus))
            output["aggregate"]["kendall_tau_median"] = float(np.median(taus))
            output["aggregate"]["normalization"] = {
                "p5": float(p5),
                "p95": float(p95),
                "formula": f"clip((raw - {p5:.1f}) / ({p95:.1f} - {p5:.1f}), 0, 1)",
            }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {output_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
