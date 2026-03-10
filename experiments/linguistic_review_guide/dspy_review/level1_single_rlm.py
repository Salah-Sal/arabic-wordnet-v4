#!/usr/bin/env python3
"""Level 1: Single RLM — Monolithic exploration.

A single dspy.RLM module receives the complete evidence YAML as external
data. The LLM explores it programmatically via a sandboxed REPL, processes
all 6 review steps, and submits the final review YAML.

Model/API key configuration is handled by config.py (supports Anthropic,
Gemini, OpenAI, Moonshot). MLflow tracing is optional — just pass --mlflow
and every DSPy call is traced automatically via dspy's callback system.

Usage:
    # Review a single synset (auto-detects model from available API keys)
    python -m dspy_review.level1_single_rlm awn4-13927849-n.evidence.yaml

    # Specify model explicitly
    python -m dspy_review.level1_single_rlm --model claude-sonnet awn4-13927849-n.evidence.yaml

    # Review all synsets with MLflow tracing
    python -m dspy_review.level1_single_rlm --all --mlflow

    # Dry run — show what would be processed
    python -m dspy_review.level1_single_rlm --all --dry-run
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
from dspy.utils.callback import BaseCallback

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


# ═══════════════════════════════════════════════════════════════
# Progress callback — real-time visibility into RLM execution
# ═══════════════════════════════════════════════════════════════

class RLMProgressCallback(BaseCallback):
    """Prints real-time progress for every RLM iteration and sub-LM call."""

    def __init__(self):
        self.rlm_start_time = None
        self.iteration = 0
        self.sub_lm_calls = 0
        self._lm_timers: dict[str, float] = {}
        self._rlm_call_id: str | None = None

    def on_module_start(self, call_id, instance, inputs):
        if isinstance(instance, dspy.RLM):
            self._rlm_call_id = call_id
            self.rlm_start_time = time.time()
            self.iteration = 0
            self.sub_lm_calls = 0
            print("  [RLM] Starting REPL execution loop")

    def on_module_end(self, call_id, outputs, exception):
        if call_id == self._rlm_call_id:
            elapsed = time.time() - (self.rlm_start_time or time.time())
            status = "ERROR" if exception else "OK"
            print(f"  [RLM] Done ({status}): {self.iteration} iterations, "
                  f"{self.sub_lm_calls} sub-LM calls, {elapsed:.1f}s total")
            self._rlm_call_id = None

    def on_lm_start(self, call_id, instance, inputs):
        self._lm_timers[call_id] = time.time()
        messages = inputs.get("messages", [])
        # Main LM calls include the REPL history in messages; sub-LM calls are short prompts
        is_main = any("repl" in str(m).lower() or "SUBMIT" in str(m) for m in messages)
        if is_main:
            self.iteration += 1
            elapsed = time.time() - (self.rlm_start_time or time.time())
            print(f"  [RLM] Iteration {self.iteration} — generating action ({elapsed:.0f}s elapsed)")
        else:
            self.sub_lm_calls += 1
            model = getattr(instance, 'model', '?')
            prompt_preview = str(messages[-1] if messages else inputs.get("prompt", ""))[:120]
            print(f"  [sub-LM #{self.sub_lm_calls}] {model} — {prompt_preview}...")

    def on_lm_end(self, call_id, outputs, exception):
        t0 = self._lm_timers.pop(call_id, None)
        dur = f"{time.time() - t0:.1f}s" if t0 else "?"
        if exception:
            print(f"  [LM] ERROR after {dur}: {exception}")
        elif outputs:
            # Show token usage if available
            usage = outputs.get("usage", {}) if isinstance(outputs, dict) else {}
            tokens = ""
            if usage:
                inp = usage.get("prompt_tokens", 0)
                out = usage.get("completion_tokens", 0)
                tokens = f" ({inp}+{out} tokens)"
            print(f"  [LM] Done in {dur}{tokens}")


# ═══════════════════════════════════════════════════════════════
# Signature
# ═══════════════════════════════════════════════════════════════

class SynsetReview(dspy.Signature):
    """أنت ناقد لغوي عربي خبير متخصص في المعجمية العربية، مُكلَّف بمراجعة مجموعة
    ترادفية في شبكة الكلمات العربية الإصدار الرابع (AWN4).

    You are an expert Arabic linguist-reviewer for AWN4.

    == AVAILABLE RESOURCES ==

    Variables (access via Python code):
      - synset_info: Synset metadata (ID, POS, lemmas, definitions, hypernym chain)
      - evidence_yaml: Full dictionary evidence YAML (large — use tools below instead of printing it)
      - algorithm: The 6-step review algorithm in Arabic/English pseudocode
      - output_schema: YAML schema your output must conform to

    Tools (call directly in your code):
      - evidence_summary() → compact overview: lemma count, entries per lemma, dictionaries, roots
      - get_lemma_evidence(lemma) → full evidence for one lemma (headword entries, root family, examples, reverse lookup)
      - get_candidate_synonyms() → per_synset candidate synonym data for Step 2
      - validate_review(yaml_text) → checks your review YAML has all required steps/lemmas; returns "VALID" or error list

    == MANDATORY 3-PHASE PROCEDURE ==

    ⚠ Do NOT call SUBMIT() until you complete ALL three phases below.

    PHASE 1 — ORIENT (iterations 1-3):
      1. Call evidence_summary() to see the evidence structure at a glance.
      2. Print synset_info to know the synset ID, lemmas, POS, and definitions.
      3. Skim the algorithm and output_schema (print first ~2000 chars of each).

    PHASE 2 — EXECUTE STEPS 0-5 (iterations 4-30):
      For EACH of the 6 steps below, use get_lemma_evidence(lemma) for per-lemma data
      and llm_query()/llm_query_batched() for semantic analysis of dictionary entries.
      Build your review as a Python dict incrementally.

      Step 0 — Evidence Classification: For each lemma, classify dictionary entries as
               confirm/contradicts/expands. Use llm_query() on actual entry texts.
      Step 1 — Lemma Validation: For each lemma, run substitution test, MWE check,
               dialectal check. Decide: confirmed / removed / escalated.
      Step 2 — Missing Lemmas: Call get_candidate_synonyms(). Evaluate candidates via
               cross-reference test + substitution test.
      Step 3 — Definition Review: Compare current definition with classical dictionary evidence.
               Decide: keep / revise / author new definition.
      Step 4 — Relations Check: Verify hypernymy (depth ≤ 3), check antonymy.
      Step 5 — Enrichment: Usage notes, eloquence, connotation, collocations, examples, morphology.

    PHASE 3 — VALIDATE AND SUBMIT (iterations 31-40):
      1. Convert your review dict to YAML: review_text = yaml.dump(review, allow_unicode=True, default_flow_style=False)
      2. Call validate_review(review_text) and confirm it returns "VALID".
      3. If errors are reported, fix them and re-validate.
      4. Only after "VALID": call SUBMIT(review_yaml=review_text)

    == CRITICAL RULES ==

    - Do NOT call SUBMIT() until ALL 6 steps (0-5) are complete and validate_review() returns "VALID".
    - Do NOT skip steps or give generic "keep all" answers — cite specific dictionary evidence.
    - Write all analysis notes and Arabic text in Arabic (العربية).
    - Write field names, technical values, and actions in English.
    - Follow DRY conventions from the output schema:
      * Omit fields with null/[]/{{}} values
      * Omit boolean fields that default to false
      * Step 5 data blocks are the source of truth — the parser derives API commands from them
    - The output schema step keys are: step0_evidence, step1_lemma_validation, step2_missing_lemmas,
      step3_definition, step4_relations, step5_enrichment
    """
    synset_info: str = dspy.InputField(
        desc="Synset metadata: ID, POS, lemmas, Arabic/English definitions, hypernym chain"
    )
    evidence_yaml: str = dspy.InputField(
        desc="Processed dictionary evidence YAML (per_lemma + per_synset data from 107 dictionaries)"
    )
    algorithm: str = dspy.InputField(
        desc="The 6-step review algorithm in Arabic/English pseudocode"
    )
    output_schema: str = dspy.InputField(
        desc="Expected YAML output schema with field descriptions, types, and examples"
    )
    review_yaml: str = dspy.OutputField(
        desc="Complete review as a single valid YAML document conforming to the output schema"
    )


# ═══════════════════════════════════════════════════════════════
# Evidence tools — host-side Python, callable from REPL sandbox
# ═══════════════════════════════════════════════════════════════

# Expected top-level keys in the review output
REVIEW_STEP_KEYS = [
    "step0_evidence",
    "step1_lemma_validation",
    "step2_missing_lemmas",
    "step3_definition",
    "step4_relations",
    "step5_enrichment",
]


def make_evidence_tools(evidence_yaml: str, synset_info: str) -> dict:
    """Create evidence exploration tools as closures over parsed data.

    These tools are injected into the RLM's Deno/Pyodide sandbox via the
    `tools={}` parameter. Each tool returns a string (required by RLM protocol).
    The evidence is parsed once here; tools serve pre-computed subsets on demand.
    """
    # Parse evidence once in host Python
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
            # roots_found may be list of strings or list of dicts with 'root' key
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
            unique_roots = list(dict.fromkeys(roots))  # deduplicate, preserve order
            lines.append(f"    roots: {', '.join(unique_roots) if unique_roots else 'none'}")
            lines.append(f"    usage examples: {len(examples)}")
            lines.append(f"    reverse lookup entries: {len(rev_entries)}")

        # per_synset summary
        ps_keys = list(per_synset.keys())
        if ps_keys:
            lines.append("")
            lines.append(f"Per-synset evidence sections: {', '.join(ps_keys)}")
            for k in ps_keys:
                section = per_synset[k]
                if isinstance(section, dict):
                    entries = section.get("entries", section.get("filters_applied", []))
                    if isinstance(entries, list):
                        lines.append(f"  {k}: {len(entries)} entries/filters")

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

    def get_candidate_synonyms() -> str:
        """Per-synset candidate synonym data for Step 2 (Missing Lemmas)."""
        if not per_synset:
            return "No per_synset evidence available."
        return yaml.dump(
            per_synset, allow_unicode=True, default_flow_style=False,
            sort_keys=False, width=200,
        )

    def validate_review(yaml_text: str) -> str:
        """Check review YAML: parses correctly, has all 6 step keys, covers all lemmas."""
        errors = []

        # 1. Parse check
        try:
            review = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            return f"[INVALID] YAML parse error: {e}"

        if not isinstance(review, dict):
            return f"[INVALID] Expected a YAML mapping, got {type(review).__name__}"

        # 2. Step keys check
        for key in REVIEW_STEP_KEYS:
            if key not in review:
                errors.append(f"Missing step key: {key}")

        # 3. Lemma coverage in step1
        s1 = review.get("step1_lemma_validation", {})
        s1_lemmas = set()
        if isinstance(s1, dict):
            # Check both flat 'lemmas' dict and per_lemma list styles
            lemmas_dict = s1.get("lemmas", {})
            if isinstance(lemmas_dict, dict):
                s1_lemmas = set(lemmas_dict.keys())
            per_lemma_list = s1.get("per_lemma", [])
            if isinstance(per_lemma_list, list):
                for item in per_lemma_list:
                    if isinstance(item, dict) and "lemma" in item:
                        s1_lemmas.add(item["lemma"])

        missing_lemmas = set(lemma_list) - s1_lemmas
        if missing_lemmas:
            errors.append(f"step1_lemma_validation missing lemmas: {', '.join(missing_lemmas)}")

        # 4. Step 0 per-lemma coverage
        s0 = review.get("step0_evidence", {})
        if isinstance(s0, dict):
            s0_pl = s0.get("per_lemma", [])
            if isinstance(s0_pl, list):
                s0_lemmas = {item.get("lemma") for item in s0_pl if isinstance(item, dict)}
                missing_s0 = set(lemma_list) - s0_lemmas
                if missing_s0:
                    errors.append(f"step0_evidence missing lemmas: {', '.join(missing_s0)}")

        if errors:
            return "[INVALID] " + "; ".join(errors)
        return "VALID"

    return [evidence_summary, get_lemma_evidence, get_candidate_synonyms, validate_review]


# ═══════════════════════════════════════════════════════════════
# Reviewer
# ═══════════════════════════════════════════════════════════════

class SingleRLMReviewer:
    """Level 1 reviewer: single RLM module for end-to-end synset review.

    Creates a fresh RLM instance per review() call so that custom tools
    can close over per-synset parsed evidence data.
    """

    def __init__(
        self,
        model: str | None = None,
        sub_model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 20000,
        max_iterations: int = 40,
        max_llm_calls: int = 80,
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

    def review(self, synset_info: str, evidence_yaml: str,
               algorithm: str, output_schema: str) -> dspy.Prediction:
        """Run the review and return the full prediction (includes trajectory).

        Creates a fresh RLM per call with tools bound to this synset's evidence.
        """
        # Build per-synset tools that close over the parsed evidence
        tools = make_evidence_tools(evidence_yaml, synset_info)

        rlm = dspy.RLM(
            SynsetReview,
            max_iterations=self.max_iterations,
            max_llm_calls=self.max_llm_calls,
            max_output_chars=self.max_output_chars,
            sub_lm=self.sub_lm,
            tools=tools,
            verbose=self.verbose,
        )

        return rlm(
            synset_info=synset_info,
            evidence_yaml=evidence_yaml,
            algorithm=algorithm,
            output_schema=output_schema,
        )


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Level 1: Single RLM synset reviewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s awn4-13927849-n.evidence.yaml             # single synset, auto-detect model
  %(prog)s --model claude-sonnet --all                # all synsets with Claude Sonnet
  %(prog)s --model gemini-2.5-flash --all --mlflow    # all synsets with Gemini + MLflow
  %(prog)s --all --dry-run                            # list files without processing
""",
    )
    parser.add_argument("evidence_file", nargs="?",
                        help="Evidence file name (e.g., awn4-13927849-n.evidence.yaml)")
    parser.add_argument("--all", action="store_true",
                        help="Process all evidence files in the evidence directory")
    parser.add_argument("--evidence-dir", type=str, default=str(EVIDENCE_DIR),
                        help="Directory with .evidence.yaml files")
    parser.add_argument("--output-dir", type=str, default=str(PROJECT_DIR / "reviews_level1"),
                        help="Output directory for review YAML files")
    parser.add_argument("--max-iterations", type=int, default=40,
                        help="Max REPL loop iterations (default: 40)")
    parser.add_argument("--max-llm-calls", type=int, default=80,
                        help="Max llm_query/llm_query_batched calls (default: 80)")
    parser.add_argument("--max-output-chars", type=int, default=100_000,
                        help="Max chars per REPL output before truncation (default: 100000)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without running")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose REPL output")

    add_model_args(parser)    # --model, --sub-model, --temperature, --max-tokens
    add_mlflow_args(parser)   # --mlflow, --mlflow-uri, --experiment
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

    # ── MLflow: just 3 lines, DSPy autolog handles the rest ──
    if args.mlflow:
        setup_mlflow(tracking_uri=args.mlflow_uri, experiment_name=args.experiment)

    # ── Load static components ────────────────────────────────
    algorithm = load_text(ALGORITHM_PATH)
    output_schema = load_text(OUTPUT_SCHEMA_PATH)

    print(f"Files to process: {len(files)}")
    print(f"Output directory: {output_dir}")
    print(f"Max iterations: {args.max_iterations} | Max LLM calls: {args.max_llm_calls} | Max output chars: {args.max_output_chars:,}")
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

    reviewer = SingleRLMReviewer(
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
        print(f"[{i}/{len(files)}] Reviewing {synset_id}...")

        data = load_synset_data(filepath)
        ev_lines = data["evidence_yaml"].count("\n")
        print(f"  Evidence: {ev_lines} lines")

        t0 = time.time()
        try:
            result = reviewer.review(
                synset_info=data["synset_info"],
                evidence_yaml=data["evidence_yaml"],
                algorithm=algorithm,
                output_schema=output_schema,
            )
            duration = time.time() - t0

            # Save review
            review_path = output_dir / f"{synset_id}.review.yaml"
            with open(review_path, "w", encoding="utf-8") as f:
                f.write(result.review_yaml)

            # Save trajectory for debugging
            trajectory_path = output_dir / f"{synset_id}.trajectory.json"
            with open(trajectory_path, "w", encoding="utf-8") as f:
                json.dump(result.trajectory, f, ensure_ascii=False, indent=2)

            review_lines = result.review_yaml.count("\n")
            steps = len(result.trajectory)
            print(f"  Done: {review_lines} lines, {steps} REPL steps, {duration:.1f}s")
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
