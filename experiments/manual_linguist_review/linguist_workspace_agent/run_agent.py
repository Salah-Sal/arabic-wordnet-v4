#!/usr/bin/env python3
"""
run_agent.py — CLI entry point for the RLM evidence collection agent.

Runs the EvidenceCollectionAgent on one or more AWN4 synsets, applies
post-processing to the RLM output, and writes YAML evidence artifacts.

Usage:
    python run_agent.py awn4-05162506-n
    python run_agent.py awn4-05162506-n awn4-02493953-v --verbose
    python run_agent.py --batch batches/random_10.txt
    python run_agent.py awn4-05162506-n --model gemini-2.5-flash --save-trajectory
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add pipeline tools dir for collect_evidence imports
_PIPELINE_DIR = str(Path(__file__).resolve().parent.parent / "linguist_workspace" / "tools")
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)


def parse_evidence_json(raw: str) -> dict:
    """Parse the RLM's evidence_json output into a Python dict.

    Handles both valid JSON and Python dict literals (single quotes).
    """
    # Try JSON first
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try Python literal
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        pass

    # Try extracting JSON from markdown code fence
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse evidence_json (length={len(raw)})")


def post_process(artifact: dict, db_path: str) -> dict:
    """Apply post-processing to the RLM's evidence artifact.

    - Override _meta with authoritative values
    - Validate and fill missing sections
    """
    from collect_evidence import DictDB

    # Handle case where RLM submitted a list or other unexpected type
    if not isinstance(artifact, dict):
        artifact = {"_raw_output": artifact}

    # Override _meta
    db = DictDB(db_path)
    meta = artifact.get("_meta", {})
    meta["schema_version"] = "1.0.0"
    meta["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["generator"] = "rlm_agent"
    meta["db_path"] = db_path
    meta["db_stats"] = db.get_stats()
    artifact["_meta"] = meta
    db.close()

    # Ensure required top-level sections exist
    artifact.setdefault("synset", {})
    artifact.setdefault("per_lemma", {})
    artifact.setdefault("per_synset", {})

    # Fill missing per_lemma steps
    for lemma, lemma_data in artifact.get("per_lemma", {}).items():
        lemma_data.setdefault("identity", {"lemma": lemma})
        lemma_data.setdefault("step1_headword", {"result_count": 0, "entries": []})
        lemma_data.setdefault("step2_definitions", {"result_count": 0, "entries_with_senses": []})
        lemma_data.setdefault("step3_root_family", {"roots_found": [], "by_root": {}})
        lemma_data.setdefault("step6_examples", {"result_count": 0, "examples": []})
        lemma_data.setdefault("step7_chronological", {"result_count": 0, "entries": []})
        lemma_data.setdefault("step8_reverse_lookup", {"result_count": 0, "entries": []})

    # Fill missing per_synset steps
    per_synset = artifact.get("per_synset", {})
    per_synset.setdefault("step4_fts_keyword", {
        "keywords_extracted": [], "excluded_entry_ids": [],
        "result_count": 0, "entries": [],
    })
    per_synset.setdefault("step5_english_bridge", {
        "english_terms_used": [], "excluded_entry_ids": [],
        "result_count": 0, "entries": [],
    })
    per_synset.setdefault("step9_specialized", {"filters_applied": []})
    artifact["per_synset"] = per_synset

    return artifact


def write_yaml(artifact: dict, output_path: Path) -> None:
    """Write evidence artifact as YAML with Arabic-friendly formatting."""
    from collect_evidence import _ArabicDumper
    import yaml

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            artifact,
            f,
            Dumper=_ArabicDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )


def save_trajectory(trajectory_data: dict, output_path: Path) -> None:
    """Save the RLM execution trajectory for debugging."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(trajectory_data, f, ensure_ascii=False, indent=2)


def parse_batch_file(batch_path: Path) -> list[str]:
    """Parse a batch file for synset IDs (handles YAML compact + plain text)."""
    target_ids = []
    with open(batch_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.search(r"synset_id:\s*(awn4-\S+)", line)
            if m:
                target_ids.append(m.group(1))
                continue
            token = line.split()[0].lstrip("-").strip()
            if token.startswith("awn4-"):
                target_ids.append(token)
    return target_ids


def main():
    parser = argparse.ArgumentParser(
        description="RLM Agent — Collect dictionary evidence for AWN4 synsets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s awn4-05162506-n
  %(prog)s --batch batches/random_10.txt --verbose
  %(prog)s awn4-05162506-n --model gemini-2.5-flash --save-trajectory
""",
    )
    parser.add_argument("synset_ids", nargs="*", help="Synset IDs (e.g., awn4-05162506-n)")
    parser.add_argument("--batch", metavar="FILE", help="Read synset IDs from file")
    parser.add_argument("--output-dir", default="output/evidence",
                        help="Output directory (default: output/evidence)")
    parser.add_argument("--db", default="data/arabic_dict.db",
                        help="Path to arabic_dict.db")
    parser.add_argument("--max-iterations", type=int, default=40,
                        help="Max RLM iterations (default: 40)")
    parser.add_argument("--max-llm-calls", type=int, default=30,
                        help="Max sub-LLM calls (default: 30)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show RLM execution details")
    parser.add_argument("--save-trajectory", action="store_true",
                        help="Save RLM trajectory to output/trajectories/")

    # Model configuration
    try:
        from config import add_model_args, configure_lm
        add_model_args(parser)
        has_config = True
    except ImportError:
        parser.add_argument("--model", "-m", type=str, default=None,
                            help="LLM model (alias or full litellm ID)")
        has_config = False

    args = parser.parse_args()

    # Collect target IDs
    target_ids: list[str] = list(args.synset_ids)
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.is_absolute():
            batch_path = Path(__file__).resolve().parent / args.batch
        target_ids.extend(parse_batch_file(batch_path))

    if not target_ids:
        parser.error("No synset IDs provided. Use positional args or --batch.")

    # Configure LM
    if has_config:
        lm = configure_lm(
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    else:
        import dspy
        if args.model:
            lm = dspy.LM(args.model, temperature=0.7, max_tokens=20000)
            dspy.configure(lm=lm)
        else:
            print("Error: No model specified and config.py not found.", file=sys.stderr)
            print("Set --model or ensure config.py is accessible.", file=sys.stderr)
            sys.exit(1)

    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = script_dir / args.db
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = script_dir / args.output_dir

    # Create agent
    from evidence_agent import EvidenceCollectionAgent
    agent = EvidenceCollectionAgent(
        db_path=str(db_path),
        max_iterations=args.max_iterations,
        max_llm_calls=args.max_llm_calls,
        verbose=args.verbose,
    )

    # Process synsets
    succeeded = 0
    failed = 0

    for synset_id in target_ids:
        print(f"\n{'='*60}")
        print(f"Processing: {synset_id}")
        print(f"{'='*60}")

        try:
            result = agent(synset_id)

            # Parse the RLM output
            artifact = parse_evidence_json(result.evidence_json)

            # Post-process
            artifact = post_process(artifact, str(db_path))

            # Write YAML
            yaml_path = output_dir / f"{synset_id}.evidence.yaml"
            write_yaml(artifact, yaml_path)
            print(f"[OK] Written: {yaml_path}")

            # Summary
            n_lemmas = len(artifact.get("per_lemma", {}))
            total_entries = sum(
                lemma_data.get("step1_headword", {}).get("result_count", 0)
                for lemma_data in artifact.get("per_lemma", {}).values()
            )
            print(f"     {n_lemmas} lemmas, {total_entries} headword entries")

            # Save trajectory if requested
            if args.save_trajectory:
                traj_dir = script_dir / "output" / "trajectories"
                traj_path = traj_dir / f"{synset_id}.trajectory.json"
                traj_data = {
                    "synset_id": synset_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "evidence_json_raw": result.evidence_json,
                }
                save_trajectory(traj_data, traj_path)
                print(f"     Trajectory: {traj_path}")

            succeeded += 1

        except Exception as e:
            print(f"[FAILED] {synset_id}: {e}", file=sys.stderr)
            if args.verbose:
                traceback.print_exc()
            failed += 1

    # Final summary
    agent.close()
    print(f"\n{'='*60}")
    print(f"Done: {succeeded} succeeded, {failed} failed (of {len(target_ids)} total)")
    print(f"{'='*60}")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
