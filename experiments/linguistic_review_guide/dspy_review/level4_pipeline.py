#!/usr/bin/env python3
"""Level 4: Step-Decomposed Pipeline — 6 specialized modules.

Decomposes the 6-step review algorithm into a DSPy pipeline:
    Step 0 — RLM: Evidence classification (scans full evidence YAML)
    Step 1 — CoT: Lemma validation (works on Step 0 compact output)
    Step 2 — RLM: Missing lemmas (scans per_synset + reverse lookups)
    Step 3 — CoT: Definition processing (compact, reasoning-heavy)
    Step 4 — CoT: Relations check (compact, reasoning-heavy)
    Step 5 — CoT: Enrichment & cultural fit (compact)

Steps 2, 3, 4 are independent of each other and run sequentially
(parallel execution is a future enhancement).

Usage:
    # Review a single synset (auto-detects model from available API keys)
    python -m dspy_review.level4_pipeline awn4-13927849-n.evidence.yaml

    # Specify model explicitly
    python -m dspy_review.level4_pipeline --model gemini-3.1-pro awn4-13927849-n.evidence.yaml

    # Review all synsets with MLflow tracing
    python -m dspy_review.level4_pipeline --all --mlflow

    # Dry run — show what would be processed
    python -m dspy_review.level4_pipeline --all --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import yaml
import dspy

from dspy_review.config import configure_lm, make_sub_lm, add_model_args
from dspy_review.tracing import setup_mlflow, add_mlflow_args
from dspy_review.shared import (
    PROJECT_DIR,
    EVIDENCE_DIR,
    ALGORITHM_PATH,
    OUTPUT_SCHEMA_PATH,
    load_text,
    load_synset_data,
    list_evidence_files,
    extract_synset_id,
    dump_yaml,
)
from dspy_review.signatures import (
    Step0EvidenceClassification,
    Step1LemmaValidation,
    Step2MissingLemmas,
    Step3Definition,
    Step4Relations,
    Step5Enrichment,
)
from dspy_review.extractors import (
    extract_algorithm_section,
    extract_schema_section,
    extract_confirmed_lemmas,
    extract_added_lemmas,
    merge_lemma_lists,
    extract_definition_review_flag,
    extract_step0_evidence_summary,
    extract_candidate_evidence,
    extract_examples_evidence,
)

# Reuse the progress callback from Level 1
from dspy_review.level1_single_rlm import RLMProgressCallback


# ═══════════════════════════════════════════════════════════════
# Step 0 tools — evidence exploration for classification
# ═══════════════════════════════════════════════════════════════

def make_step0_tools(evidence_yaml: str, synset_info: str) -> list:
    """Create evidence tools for Step 0 (evidence classification).

    Step 0 needs to iterate over all dictionary entries per lemma and classify
    them as confirm/contradicts/expands. It needs:
    - evidence_summary() — quick orientation
    - get_lemma_evidence(lemma) — full data for one lemma at a time
    """
    parsed = yaml.safe_load(evidence_yaml)
    per_lemma = parsed.get("per_lemma", {})
    per_synset = parsed.get("per_synset", {})
    synset_meta = parsed.get("synset", {})
    lemma_list = list(per_lemma.keys())

    def evidence_summary() -> str:
        """Overview of evidence structure: lemmas, entry counts, dictionaries, roots."""
        lines = []
        lines.append(f"Synset: {synset_meta.get('id', '?')}")
        lines.append(f"POS: {synset_meta.get('pos', '?')}")
        lines.append(f"Lemmas ({len(lemma_list)}): {', '.join(lemma_list)}")
        lines.append(f"Definition (AR): {synset_meta.get('definition_ar', '?')}")
        lines.append(f"Definition (EN): {synset_meta.get('definition_en', '?')}")
        lines.append("")

        for lemma in lemma_list:
            ld = per_lemma.get(lemma, {})
            s1 = ld.get("step1_headword", {})
            entries = s1.get("entries", [])
            dicts = set()
            for e in entries:
                d = e.get("dict_name_ar") or e.get("dict_name_en") or e.get("dictionary_id", "")
                if d:
                    dicts.add(d)

            s3 = ld.get("step3_root_family", {})
            roots_raw = s3.get("roots_found", [])
            roots = []
            for r in roots_raw:
                if isinstance(r, str):
                    roots.append(r)
                elif isinstance(r, dict):
                    roots.append(r.get("root", str(r)))
            s6 = ld.get("step6_examples", {})
            examples = s6.get("examples", [])
            s8 = ld.get("step8_reverse_lookup", {})
            rev_entries = s8.get("entries", [])

            lines.append(f"  {lemma}:")
            lines.append(f"    headword entries: {len(entries)} from {len(dicts)} dictionaries")
            unique_roots = list(dict.fromkeys(roots))
            lines.append(f"    roots: {', '.join(unique_roots) if unique_roots else 'none'}")
            lines.append(f"    usage examples: {len(examples)}")
            lines.append(f"    reverse lookup entries: {len(rev_entries)}")

        lines.append("")
        lines.append(f"Total evidence YAML: {len(evidence_yaml):,} chars")
        return "\n".join(lines)

    def get_lemma_evidence(lemma: str) -> str:
        """Full evidence for one lemma: headword entries, root family, examples, reverse lookup."""
        ld = per_lemma.get(lemma)
        if ld is None:
            available = ", ".join(lemma_list)
            return f"[ERROR] Lemma '{lemma}' not found. Available lemmas: {available}"
        return yaml.dump(
            {lemma: ld}, allow_unicode=True, default_flow_style=False,
            sort_keys=False, width=200,
        )

    return [evidence_summary, get_lemma_evidence]


# ═══════════════════════════════════════════════════════════════
# Step 2 tools — candidate evidence navigation
# ═══════════════════════════════════════════════════════════════

def make_step2_tools(candidate_evidence_yaml: str, synset_info: str) -> list:
    """Create evidence tools for Step 2 (missing lemma discovery).

    Step 2 needs to scan per_synset evidence and reverse lookups to find
    synonym candidates. It needs:
    - candidate_summary() — overview of available candidate sources
    - get_section_evidence(section) — drill into specific evidence sections
    """
    parsed = yaml.safe_load(candidate_evidence_yaml)
    per_synset = parsed.get("per_synset", {})
    per_lemma_reverse = parsed.get("per_lemma_reverse", {})

    def candidate_summary() -> str:
        """Overview of candidate evidence: sections, entry counts, reverse lookup counts."""
        lines = []
        lines.append("Per-synset evidence sections:")
        for key, section in per_synset.items():
            if isinstance(section, dict):
                entries = section.get("entries", section.get("filters_applied", []))
                count = len(entries) if isinstance(entries, list) else "?"
                lines.append(f"  {key}: {count} entries")
            else:
                lines.append(f"  {key}: {type(section).__name__}")

        if per_lemma_reverse:
            lines.append("")
            lines.append("Reverse lookup data per lemma:")
            for lemma, data in per_lemma_reverse.items():
                s8 = data.get("step8_reverse_lookup", {})
                rev_entries = s8.get("entries", [])
                lines.append(f"  {lemma}: {len(rev_entries)} reverse lookup entries")

        lines.append("")
        lines.append(f"Total candidate evidence: {len(candidate_evidence_yaml):,} chars")
        return "\n".join(lines)

    def get_section_evidence(section: str) -> str:
        """Get evidence for a specific section: step4_fts_keyword, step5_english_bridge, step9_specialized, or a lemma name for reverse lookup."""
        # Check per_synset sections
        if section in per_synset:
            return yaml.dump(
                {section: per_synset[section]},
                allow_unicode=True, default_flow_style=False,
                sort_keys=False, width=200,
            )
        # Check reverse lookup by lemma name
        if section in per_lemma_reverse:
            return yaml.dump(
                {section: per_lemma_reverse[section]},
                allow_unicode=True, default_flow_style=False,
                sort_keys=False, width=200,
            )
        available = list(per_synset.keys()) + list(per_lemma_reverse.keys())
        return f"[ERROR] Section '{section}' not found. Available: {', '.join(available)}"

    return [candidate_summary, get_section_evidence]


# ═══════════════════════════════════════════════════════════════
# Step output validation
# ═══════════════════════════════════════════════════════════════

def _validate_step_yaml(yaml_text: str, expected_key: str, step_name: str) -> str:
    """Validate that a step's YAML output parses and contains the expected top-level key.

    Returns the YAML text if valid; raises ValueError on failure.
    """
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"{step_name} produced invalid YAML: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"{step_name} output is {type(data).__name__}, expected dict")

    if expected_key not in data:
        # Be lenient — the model might return the inner content without wrapping
        # Try to wrap it
        wrapped = {expected_key: data}
        yaml_text = yaml.dump(wrapped, allow_unicode=True, default_flow_style=False,
                              sort_keys=False, width=200)

    return yaml_text


# ═══════════════════════════════════════════════════════════════
# Pipeline compiler — merge per-step outputs into final review
# ═══════════════════════════════════════════════════════════════

def collect_actions(step_data) -> list[dict]:
    """Recursively collect all 'actions' lists from a step's parsed data."""
    actions = []
    if isinstance(step_data, dict):
        if "actions" in step_data and isinstance(step_data["actions"], list):
            actions.extend(step_data["actions"])
        for key, value in step_data.items():
            if key != "actions":
                actions.extend(collect_actions(value))
    elif isinstance(step_data, list):
        for item in step_data:
            actions.extend(collect_actions(item))
    return actions


def compile_review_yaml(
    synset_info: str,
    step0_yaml: str,
    step1_yaml: str,
    step2_yaml: str,
    step3_yaml: str,
    step4_yaml: str,
    step5_yaml: str,
) -> str:
    """Merge per-step YAML outputs into the final review document.

    Corresponds to Step 6 of the algorithm (lines 592-851 of draft_api.md),
    but only the compilation part. The API execution part is handled
    downstream by the AWN4 API client.
    """
    step_yamls = {
        "step0": step0_yaml,
        "step1": step1_yaml,
        "step2": step2_yaml,
        "step3": step3_yaml,
        "step4": step4_yaml,
        "step5": step5_yaml,
    }

    review = {}
    parsed_steps = {}

    for label, text in step_yamls.items():
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                parsed_steps[label] = data
                review.update(data)
        except yaml.YAMLError:
            # Include the raw text as a string if it can't be parsed
            review[f"{label}_raw"] = text

    # Collect all actions into a unified action queue
    all_actions = []
    for data in parsed_steps.values():
        all_actions.extend(collect_actions(data))

    if all_actions:
        review["actions"] = all_actions

    # Placeholder evaluation — to be replaced with rubric-based scoring
    review["evaluation"] = {
        "semantic_accuracy": None,
        "gloss_quality": None,
        "synonym_coherence": None,
        "completeness": None,
        "cultural_adequacy": None,
        "overall": None,
    }

    return yaml.dump(
        review, allow_unicode=True, default_flow_style=False,
        sort_keys=False, width=200,
    )


# ═══════════════════════════════════════════════════════════════
# Pipeline reviewer
# ═══════════════════════════════════════════════════════════════

class StepDecomposedReviewer:
    """Level 4: Step-Decomposed Pipeline.

    Decomposes the 6-step review algorithm into specialized DSPy modules.
    Steps 0 & 2 use RLM (large evidence), Steps 1, 3, 4, 5 use ChainOfThought.

    Creates RLM instances per-call (they need per-synset tools as closures).
    CoT modules are created once in __init__ (they don't need tools).
    """

    def __init__(
        self,
        model: str | None = None,
        sub_model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 20000,
        max_iterations: int = 25,
        max_llm_calls: int = 60,
        max_output_chars: int = 100_000,
        verbose: bool = True,
    ):
        self.lm = configure_lm(model=model, temperature=temperature, max_tokens=max_tokens)
        self.sub_lm = make_sub_lm(sub_model=sub_model, main_model=model or self.lm.model)
        print(f"Sub-LLM: {self.sub_lm.model}")

        self.max_iterations = max_iterations
        self.max_llm_calls = max_llm_calls
        self.max_output_chars = max_output_chars
        self.verbose = verbose

        # Register progress callback for real-time visibility
        if verbose:
            self.progress_cb = RLMProgressCallback()
            dspy.configure(lm=self.lm, callbacks=[self.progress_cb])

        # CoT modules — created once, reusable across synsets (no tools needed)
        self.step1_cot = dspy.ChainOfThought(Step1LemmaValidation)
        self.step3_cot = dspy.ChainOfThought(Step3Definition)
        self.step4_cot = dspy.ChainOfThought(Step4Relations)
        self.step5_cot = dspy.ChainOfThought(Step5Enrichment)

    def review(
        self,
        synset_info: str,
        evidence_yaml: str,
        algorithm: str,
        output_schema: str,
    ) -> dict:
        """Run the full 6-step pipeline and return per-step + compiled results.

        Returns dict with keys:
            step0_yaml, step1_yaml, ..., step5_yaml: Per-step YAML strings
            review_yaml: Compiled final review
            step_timings: Dict of step → seconds
        """
        timings = {}
        results = {}

        # ── Step 0: Evidence Classification (RLM) ───────────────
        print("  [Pipeline] Step 0: Evidence Classification (RLM)")
        t0 = time.time()

        step0_tools = make_step0_tools(evidence_yaml, synset_info)
        step0_rlm = dspy.RLM(
            Step0EvidenceClassification,
            max_iterations=self.max_iterations,
            max_llm_calls=self.max_llm_calls,
            max_output_chars=self.max_output_chars,
            sub_lm=self.sub_lm,
            tools=step0_tools,
            verbose=self.verbose,
        )
        step0_result = step0_rlm(
            synset_info=synset_info,
            evidence_yaml=evidence_yaml,
            algorithm=extract_algorithm_section(algorithm, 0),
            output_schema=extract_schema_section(output_schema, 0),
        )
        step0_yaml = step0_result.step0_yaml
        timings["step0"] = time.time() - t0
        results["step0_yaml"] = step0_yaml
        print(f"  [Pipeline] Step 0 done ({timings['step0']:.1f}s)")

        # ── Step 1: Lemma Validation (CoT) ──────────────────────
        print("  [Pipeline] Step 1: Lemma Validation (CoT)")
        t0 = time.time()

        step1_result = self.step1_cot(
            synset_info=synset_info,
            step0_yaml=step0_yaml,
            algorithm=extract_algorithm_section(algorithm, 1),
            output_schema=extract_schema_section(output_schema, 1),
        )
        step1_yaml = step1_result.step1_yaml
        timings["step1"] = time.time() - t0
        results["step1_yaml"] = step1_yaml
        print(f"  [Pipeline] Step 1 done ({timings['step1']:.1f}s)")

        # ── Extract inter-step data ─────────────────────────────
        try:
            confirmed = extract_confirmed_lemmas(step1_yaml)
        except ValueError as e:
            print(f"  [Pipeline] Warning: could not extract confirmed lemmas: {e}")
            # Fallback: use all original lemmas
            parsed_ev = yaml.safe_load(evidence_yaml)
            confirmed = list(parsed_ev.get("per_lemma", {}).keys())

        definition_flag = extract_definition_review_flag(step1_yaml)

        try:
            evidence_summary = extract_step0_evidence_summary(step0_yaml)
        except ValueError as e:
            print(f"  [Pipeline] Warning: could not extract Step 0 summary: {e}")
            evidence_summary = step0_yaml  # Fallback: pass raw Step 0 output

        candidate_evidence = extract_candidate_evidence(evidence_yaml)
        examples_evidence = extract_examples_evidence(evidence_yaml)

        confirmed_str = ", ".join(confirmed)
        print(f"  [Pipeline] Confirmed lemmas: {confirmed_str}")
        print(f"  [Pipeline] Definition review flag: {definition_flag}")

        # ── Step 2: Missing Lemmas (RLM) ────────────────────────
        print("  [Pipeline] Step 2: Missing Lemmas (RLM)")
        t0 = time.time()

        step2_tools = make_step2_tools(candidate_evidence, synset_info)
        step2_rlm = dspy.RLM(
            Step2MissingLemmas,
            max_iterations=self.max_iterations,
            max_llm_calls=self.max_llm_calls,
            max_output_chars=self.max_output_chars,
            sub_lm=self.sub_lm,
            tools=step2_tools,
            verbose=self.verbose,
        )
        step2_result = step2_rlm(
            synset_info=synset_info,
            confirmed_lemmas=confirmed_str,
            candidate_evidence_yaml=candidate_evidence,
            algorithm=extract_algorithm_section(algorithm, 2),
            output_schema=extract_schema_section(output_schema, 2),
        )
        step2_yaml = step2_result.step2_yaml
        timings["step2"] = time.time() - t0
        results["step2_yaml"] = step2_yaml
        print(f"  [Pipeline] Step 2 done ({timings['step2']:.1f}s)")

        # ── Step 3: Definition Processing (CoT) ────────────────
        print("  [Pipeline] Step 3: Definition Processing (CoT)")
        t0 = time.time()

        step3_result = self.step3_cot(
            synset_info=synset_info,
            definition_review_flag=str(definition_flag).lower(),
            step0_evidence_summary=evidence_summary,
            algorithm=extract_algorithm_section(algorithm, 3),
            output_schema=extract_schema_section(output_schema, 3),
        )
        step3_yaml = step3_result.step3_yaml
        timings["step3"] = time.time() - t0
        results["step3_yaml"] = step3_yaml
        print(f"  [Pipeline] Step 3 done ({timings['step3']:.1f}s)")

        # ── Step 4: Relations Check (CoT) ───────────────────────
        print("  [Pipeline] Step 4: Relations Check (CoT)")
        t0 = time.time()

        # Merge confirmed + added lemmas for Steps 4 and 5
        try:
            added = extract_added_lemmas(step2_yaml)
        except ValueError:
            added = []
        all_lemmas = merge_lemma_lists(confirmed, added)
        all_lemmas_str = ", ".join(all_lemmas)

        step4_result = self.step4_cot(
            synset_info=synset_info,
            confirmed_lemmas=all_lemmas_str,
            algorithm=extract_algorithm_section(algorithm, 4),
            output_schema=extract_schema_section(output_schema, 4),
        )
        step4_yaml = step4_result.step4_yaml
        timings["step4"] = time.time() - t0
        results["step4_yaml"] = step4_yaml
        print(f"  [Pipeline] Step 4 done ({timings['step4']:.1f}s)")

        # ── Step 5: Enrichment & Cultural Fit (CoT) ─────────────
        print("  [Pipeline] Step 5: Enrichment & Cultural Fit (CoT)")
        t0 = time.time()

        step5_result = self.step5_cot(
            synset_info=synset_info,
            confirmed_lemmas_with_evidence=evidence_summary,
            examples_evidence=examples_evidence,
            algorithm=extract_algorithm_section(algorithm, 5),
            output_schema=extract_schema_section(output_schema, 5),
        )
        step5_yaml = step5_result.step5_yaml
        timings["step5"] = time.time() - t0
        results["step5_yaml"] = step5_yaml
        print(f"  [Pipeline] Step 5 done ({timings['step5']:.1f}s)")

        # ── Compile final review ────────────────────────────────
        review_yaml = compile_review_yaml(
            synset_info=synset_info,
            step0_yaml=step0_yaml,
            step1_yaml=step1_yaml,
            step2_yaml=step2_yaml,
            step3_yaml=step3_yaml,
            step4_yaml=step4_yaml,
            step5_yaml=step5_yaml,
        )
        results["review_yaml"] = review_yaml
        results["step_timings"] = timings

        total = sum(timings.values())
        print(f"  [Pipeline] All steps complete ({total:.1f}s total)")

        return results


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Level 4: Step-Decomposed Pipeline reviewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s awn4-13927849-n.evidence.yaml             # single synset, auto-detect model
  %(prog)s --model gemini-3.1-pro --all               # all synsets with Gemini Pro
  %(prog)s --all --mlflow                             # all synsets with MLflow tracing
  %(prog)s --all --dry-run                            # list files without processing
""",
    )
    parser.add_argument("evidence_file", nargs="?",
                        help="Evidence file name (e.g., awn4-13927849-n.evidence.yaml)")
    parser.add_argument("--all", action="store_true",
                        help="Process all evidence files in the evidence directory")
    parser.add_argument("--evidence-dir", type=str, default=str(EVIDENCE_DIR),
                        help="Directory with .evidence.yaml files")
    parser.add_argument("--output-dir", type=str,
                        default=str(PROJECT_DIR / "reviews_level4"),
                        help="Output directory for review YAML files")
    parser.add_argument("--max-iterations", type=int, default=25,
                        help="Max REPL loop iterations per RLM step (default: 25)")
    parser.add_argument("--max-llm-calls", type=int, default=60,
                        help="Max llm_query/llm_query_batched calls per RLM step (default: 60)")
    parser.add_argument("--max-output-chars", type=int, default=100_000,
                        help="Max chars per REPL output before truncation (default: 100000)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without running")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose REPL output")

    add_model_args(parser)
    add_mlflow_args(parser)
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir)
    output_dir = Path(args.output_dir)

    # ── Determine which files to process ──────────────────────
    if args.all:
        files = list_evidence_files(evidence_dir)
    elif args.evidence_file:
        filepath = evidence_dir / args.evidence_file
        if not filepath.exists():
            print(f"Error: {filepath} not found")
            sys.exit(1)
        files = [filepath]
    else:
        parser.print_help()
        sys.exit(1)

    if not files:
        print(f"No evidence files found in {evidence_dir}")
        sys.exit(1)

    # ── MLflow ────────────────────────────────────────────────
    if args.mlflow:
        setup_mlflow(tracking_uri=args.mlflow_uri, experiment_name=args.experiment)

    # ── Load static components ────────────────────────────────
    algorithm = load_text(ALGORITHM_PATH)
    output_schema = load_text(OUTPUT_SCHEMA_PATH)

    print(f"Files to process: {len(files)}")
    print(f"Output directory: {output_dir}")
    print(f"Max iterations (per RLM step): {args.max_iterations} | "
          f"Max LLM calls: {args.max_llm_calls} | "
          f"Max output chars: {args.max_output_chars:,}")
    print()

    if args.dry_run:
        for f in files:
            synset_id = extract_synset_id(f.name)
            data = load_synset_data(f)
            ev_lines = data["evidence_yaml"].count("\n")
            print(f"  {synset_id}: {ev_lines} evidence lines")
        print(f"\nDry run complete. {len(files)} files would be processed.")
        return

    # ── Create output dir + reviewer ──────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)

    reviewer = StepDecomposedReviewer(
        model=args.model,
        sub_model=args.sub_model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_iterations=args.max_iterations,
        max_llm_calls=args.max_llm_calls,
        max_output_chars=args.max_output_chars,
        verbose=not args.quiet,
    )

    # ── Process files ─────────────────────────────────────────
    success_count = 0
    error_count = 0

    for i, filepath in enumerate(files, 1):
        synset_id = extract_synset_id(filepath.name)
        print(f"[{i}/{len(files)}] Reviewing {synset_id} (Level 4 pipeline)...")

        data = load_synset_data(filepath)
        ev_lines = data["evidence_yaml"].count("\n")
        print(f"  Evidence: {ev_lines} lines")

        t0 = time.time()
        try:
            results = reviewer.review(
                synset_info=data["synset_info"],
                evidence_yaml=data["evidence_yaml"],
                algorithm=algorithm,
                output_schema=output_schema,
            )
            duration = time.time() - t0

            # Save compiled review
            review_path = output_dir / f"{synset_id}.review.yaml"
            with open(review_path, "w", encoding="utf-8") as f:
                f.write(results["review_yaml"])

            # Save per-step YAMLs for debugging
            for step_num in range(6):
                step_key = f"step{step_num}_yaml"
                if step_key in results:
                    step_path = output_dir / f"{synset_id}.step{step_num}.yaml"
                    with open(step_path, "w", encoding="utf-8") as f:
                        f.write(results[step_key])

            # Save timings
            timings_path = output_dir / f"{synset_id}.timings.json"
            with open(timings_path, "w", encoding="utf-8") as f:
                json.dump(results.get("step_timings", {}), f, indent=2)

            review_lines = results["review_yaml"].count("\n")
            timings = results.get("step_timings", {})
            step_summary = " | ".join(f"S{k[-1]}:{v:.0f}s" for k, v in timings.items())
            print(f"  Done: {review_lines} lines, {duration:.1f}s ({step_summary})")
            print(f"  Saved: {review_path}")
            success_count += 1

        except Exception as e:
            duration = time.time() - t0
            print(f"  ERROR ({duration:.1f}s): {e}")
            error_path = output_dir / f"{synset_id}.error.txt"
            with open(error_path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
            print(f"  Error details saved to {error_path}")
            error_count += 1

        print()

    print(f"Done. {success_count} ok, {error_count} errors -> {output_dir}/")


if __name__ == "__main__":
    main()
