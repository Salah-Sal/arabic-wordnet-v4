# DSPy RLM Linguist Review Agent — Implementation Report

## Table of Contents

1. [Introduction](#1-introduction)
2. [RLM Overview](#2-rlm-overview)
3. [Level 1: Single RLM](#3-level-1-single-rlm)
4. [Level 2: Multi-Stage Pipeline](#4-level-2-multi-stage-pipeline)
5. [Level 3: Optimized Pipeline](#5-level-3-optimized-pipeline)
6. [Comparison Table](#6-comparison-table)
7. [Implementation Roadmap](#7-implementation-roadmap)

---

## 1. Introduction

### The Problem

The current linguist review system assembles a **monolithic prompt** (8K–12K lines) by injecting four components into a single LLM call:

| Component | Size | Purpose |
|-----------|------|---------|
| `prompt_template.md` | ~150 lines | Persona + execution instructions |
| `draft_api.md` | ~1,000 lines | 6-step review algorithm |
| `output_step0.yaml` | ~1,350 lines | YAML output schema |
| Evidence YAML | 4K–22K lines | Dictionary evidence per synset |

This approach has three fundamental issues:

1. **Context rot** — LLM performance degrades on long contexts. With 12K+ lines, the model struggles to track evidence across 107 dictionaries while simultaneously following a complex 6-step algorithm.

2. **All-or-nothing** — A single LLM call must produce the complete review YAML. If any step fails (e.g., malformed YAML, missed lemma), the entire output is unusable.

3. **No selective attention** — The model receives all evidence for all lemmas simultaneously, even though each analysis step only needs a subset.

### Why RLM Fits

DSPy's **RLM (Recursive Language Model)** module ([Zhang, Kraska, Khattab, 2025](https://arxiv.org/abs/2512.24601)) directly addresses context rot. Instead of passing 22K lines of evidence into the prompt, RLM:

- Gives the LLM **metadata** about the data (type, length, preview)
- The LLM writes **Python code** to selectively examine the data
- Code runs in a **sandboxed WASM interpreter** (Deno + Pyodide)
- The LLM sees output and decides what to do next (iterative REPL loop)
- The LLM can call `llm_query(prompt)` to spawn **sub-LLM calls** on specific data slices
- When finished, the LLM calls `SUBMIT(output)` to return the final answer

This maps naturally to the linguist review workflow: the LLM can explore evidence programmatically, analyze specific dictionary entries with focused sub-queries, and build up the review YAML step by step.

---

## 2. RLM Overview

### How the REPL Loop Works

```
forward(synset_info="...", evidence_yaml="<22K lines>")
    │
    ├── Build REPLVariables (metadata + preview for each input)
    │     evidence_yaml: type=str, length=485,230 chars, preview="synset:\n  id: awn4-..."
    │
    └── REPL Loop (up to max_iterations):
          │
          ├── LLM generates: reasoning + Python code
          │     "I need to parse the evidence and find entries for the first lemma."
          │     ```python
          │     import yaml
          │     data = yaml.safe_load(evidence_yaml)
          │     lemmas = data['synset']['lemmas']
          │     print(f"Synset has {len(lemmas)} lemmas: {lemmas}")
          │     ```
          │
          ├── Sandbox executes code → output
          │     "Synset has 3 lemmas: ['كَتَبَ', 'سَطَّرَ', 'خَطَّ']"
          │
          ├── LLM sees output, writes next code block
          │     ```python
          │     # Analyze first lemma's evidence
          │     entries = data['per_lemma']['كَتَبَ']['step1_headword']['entries']
          │     for e in entries[:3]:
          │         result = llm_query(f"Does this entry confirm '{lemmas[0]}' means 'to write'? Entry: {e['definitions_text']}")
          │         print(f"  {e['dict_name_ar']}: {result}")
          │     ```
          │
          ├── ... (iterates until analysis complete)
          │
          └── LLM calls SUBMIT(review_yaml="step0_evidence:\n  per_lemma: ...")
```

### Key RLM Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `max_iterations` | 20 | Maximum REPL loop iterations |
| `max_llm_calls` | 50 | Cap on `llm_query()` / `llm_query_batched()` calls |
| `max_output_chars` | 10,000 | Truncation limit on REPL output shown to LLM |
| `tools` | None | Additional Python functions callable from REPL |
| `sub_lm` | None | Cheaper model for `llm_query()` sub-calls |
| `verbose` | False | Log reasoning/code on each step |

### Built-in Functions Available in REPL

- `llm_query(prompt: str) -> str` — Single sub-LLM call for semantic analysis
- `llm_query_batched(prompts: list[str]) -> list[str]` — Parallel sub-LLM calls
- `SUBMIT(**output_fields)` — Return final answer and exit the loop
- `print(...)` — Show output to the LLM for the next iteration
- Full Python stdlib (json, re, collections, etc.)

### Prerequisites

```bash
# RLM requires Deno for the WASM sandbox
curl -fsSL https://deno.land/install.sh | sh

# Install DSPy from local repo
pip install -e /path/to/dspy

# Verify
python -c "import dspy; print(dspy.RLM)"
```

---

## 3. Level 1: Single RLM

### Architecture

A single `dspy.RLM` module receives the complete evidence YAML as external data. The LLM autonomously explores it via Python code, processes all 6 steps in sequence, and submits the final review YAML.

```
┌──────────────────────────────────────────────┐
│                 dspy.RLM                     │
│                                              │
│  Inputs (as REPLVariables — metadata only):  │
│    ├── synset_info (small)                   │
│    ├── evidence_yaml (4K-22K lines)          │
│    ├── algorithm (1K lines)                  │
│    └── output_schema (1.3K lines)            │
│                                              │
│  REPL Loop:                                  │
│    Step 0: Parse evidence, classify entries   │
│    Step 1: Validate each lemma               │
│    Step 2: Search for missing lemmas         │
│    Step 3: Review definition                 │
│    Step 4: Check relations                   │
│    Step 5: Enrich lemmas                     │
│    SUBMIT(review_yaml=...)                   │
│                                              │
│  Output: review_yaml (str)                   │
└──────────────────────────────────────────────┘
```

### Complete Code

```python
#!/usr/bin/env python3
"""Level 1: Single RLM — Monolithic exploration."""

import sys
import yaml
import dspy

sys.path.insert(0, "/path/to/dspy")  # Local DSPy repo


# ── Signature ──

class SynsetReview(dspy.Signature):
    """You are an expert Arabic linguist-reviewer for Arabic WordNet v4.

    You have access to four variables:
    - synset_info: Synset metadata (ID, lemmas, definition, hypernym chain)
    - evidence_yaml: Dictionary evidence from 107 Arabic dictionaries (760,660 entries)
    - algorithm: The 6-step review algorithm you must follow
    - output_schema: The YAML schema your output must conform to

    Follow the algorithm step by step (Steps 0-5):
    - Step 0: Evidence Classification — parse evidence, classify each entry as confirm/contradicts/expands
    - Step 1: Lemma Validation — substitution test, MWE check, dialectal check
    - Step 2: Missing Lemmas — identify candidates from per_synset evidence
    - Step 3: Definition Review — assess current definition, author new ones if needed
    - Step 4: Relations Check — verify hypernymy, antonymy
    - Step 5: Enrichment — usage, eloquence, connotation, collocations, examples, morphology

    Use Python code to parse the evidence YAML. Use llm_query() for semantic analysis
    of individual dictionary entries. Build the review YAML incrementally.

    IMPORTANT: Write all analysis and notes in Arabic. Write field names in English.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata: ID, lemmas, definition, hypernym chain")
    evidence_yaml: str = dspy.InputField(desc="Full dictionary evidence YAML (4K-22K lines)")
    algorithm: str = dspy.InputField(desc="The 6-step review algorithm (pseudocode)")
    output_schema: str = dspy.InputField(desc="Expected YAML output schema with field descriptions")
    review_yaml: str = dspy.OutputField(desc="Complete review as a single valid YAML document")


# ── Reviewer Class ──

class SingleRLMReviewer:
    def __init__(self, model="openai/gpt-4o", sub_model="openai/gpt-4o-mini"):
        self.lm = dspy.LM(model)
        self.sub_lm = dspy.LM(sub_model)
        dspy.configure(lm=self.lm)

        self.rlm = dspy.RLM(
            SynsetReview,
            max_iterations=30,       # 6 steps × ~5 iterations each
            max_llm_calls=80,        # ~13 sub-queries per step
            max_output_chars=50_000, # Review YAML can be large
            sub_lm=self.sub_lm,
            verbose=True,
        )

    def review(self, synset_info: str, evidence_yaml: str,
               algorithm: str, output_schema: str) -> str:
        result = self.rlm(
            synset_info=synset_info,
            evidence_yaml=evidence_yaml,
            algorithm=algorithm,
            output_schema=output_schema,
        )
        return result.review_yaml


# ── Runner ──

def main():
    import os

    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(SCRIPT_DIR)

    # Load static components
    def load_text(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    algorithm = load_text(os.path.join(PARENT_DIR, "draft_api.md"))
    output_schema = load_text(os.path.join(PARENT_DIR, "output_step0.yaml"))

    # Load one evidence file
    evidence_dir = os.path.join(PARENT_DIR, "sample synsets with  dictionary evidenc")
    evidence_files = sorted(f for f in os.listdir(evidence_dir) if f.endswith(".evidence.yaml"))

    if not evidence_files:
        print("No evidence files found")
        return

    # Process first file as a test
    filename = evidence_files[0]
    filepath = os.path.join(evidence_dir, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Extract synset info
    synset = raw.get("synset", {})
    synset_info = yaml.dump({
        "id": synset.get("id", ""),
        "pos": synset.get("pos", ""),
        "lemmas": synset.get("lemmas", []),
        "definition_ar": synset.get("definition_ar", ""),
        "definition_en": synset.get("oewn", {}).get("definition_en", ""),
    }, allow_unicode=True, default_flow_style=False)

    evidence_yaml = load_text(filepath)

    # Run review
    reviewer = SingleRLMReviewer()
    review = reviewer.review(synset_info, evidence_yaml, algorithm, output_schema)

    # Save output
    synset_id = filename.replace(".evidence.yaml", "")
    output_path = os.path.join(SCRIPT_DIR, f"{synset_id}.review.yaml")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(review)
    print(f"Review saved to {output_path}")


if __name__ == "__main__":
    main()
```

### What Happens at Runtime

1. RLM wraps `evidence_yaml` (e.g., 485K chars) as a `REPLVariable` — the LLM sees only: `type=str, length=485,230, preview="synset:\n  id: awn4-..."` (first ~1K chars)
2. The LLM writes Python to parse the full YAML and explore it selectively
3. For semantic decisions (e.g., "does this entry confirm the lemma?"), the LLM calls `llm_query()` with a focused prompt + the specific entry text
4. After processing all 6 steps, the LLM builds the output YAML string and calls `SUBMIT(review_yaml="...")`

### Pros & Cons

| Pros | Cons |
|------|------|
| Simplest implementation (~50 lines) | No structure enforcement between steps |
| Eliminates context rot on large evidence | Single point of failure |
| LLM can focus on relevant data slices | High token cost (30 iterations + 80 sub-calls) |
| Can handle 22K-line evidence files | No optimization possible |
| Sub-LLM calls give focused semantic analysis | YAML output validated only at SUBMIT time |

---

## 4. Level 2: Multi-Stage Pipeline

### Architecture

Break the 6 analysis steps into separate DSPy modules within a custom `dspy.Module`. Steps that need to explore large evidence use `dspy.RLM`. Steps that work on already-extracted summaries use `dspy.ChainOfThought`.

```
                    ┌─────────────────────┐
                    │  evidence_yaml (full)│
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │  Step 0: RLM        │ ← Classify all evidence
                    │  → Step0Output      │
                    └────────┬────────────┘
                             │
              ┌──────────────┼───────────────┐
              │              │               │
     ┌────────▼─────┐  ┌────▼─────┐  ┌──────▼──────┐
     │ Step 1: RLM  │  │ summary  │  │ per_synset  │
     │ Validate     │  │ (built   │  │ evidence    │
     │ lemmas       │  │ from S0) │  │             │
     └────────┬─────┘  └────┬─────┘  └──────┬──────┘
              │              │               │
              │         ┌────▼─────┐  ┌──────▼──────┐
              │         │ Step 3:  │  │ Step 2: RLM │
              │         │ CoT      │  │ Missing     │
              │         │ Def.     │  │ lemmas      │
              │         └────┬─────┘  └──────┬──────┘
              │              │               │
              │         ┌────▼─────┐         │
              │         │ Step 4:  │         │
              │         │ CoT      │         │
              │         │ Relations│         │
              │         └────┬─────┘         │
              │              │               │
     ┌────────▼──────────────▼───────────────▼──┐
     │              Step 5: RLM                  │
     │              Enrichment                   │
     └─────────────────┬────────────────────────┘
                       │
              ┌────────▼────────┐
              │  compile_review │ ← Merge all step outputs → YAML
              └─────────────────┘
```

### Key Design: Evidence Partitioning

Each step receives **only the data it needs**:

| Step | Module | Evidence Received |
|------|--------|-------------------|
| Step 0 | RLM | Full `evidence_yaml` (must classify everything) |
| Step 1 | RLM | `per_lemma` evidence + Step 0 classifications |
| Step 2 | RLM | `per_synset` evidence (FTS, English bridge, specialized) |
| Step 3 | CoT | Summary from Step 0 (confirm/contradicts/expands counts + key texts) |
| Step 4 | CoT | `synset_info` (relations, hypernym chain) + confirmed lemma list |
| Step 5 | RLM | `per_lemma` evidence + Step 0 expands + confirmed lemma list |

### Complete Code

```python
#!/usr/bin/env python3
"""Level 2: Multi-Stage Pipeline — Step-decomposed modules."""

import json
import yaml
import dspy
from pydantic import BaseModel, Field
from typing import Literal, Optional


# ═══════════════════════════════════════════════════════════════
# Pydantic Models — Inter-step I/O
# ═══════════════════════════════════════════════════════════════

class EvidenceItem(BaseModel):
    text: str
    source: str
    conflict: Optional[str] = None
    addition: Optional[str] = None

class LemmaEvidence(BaseModel):
    lemma: str
    confirm: list[EvidenceItem] = []
    contradicts: list[EvidenceItem] = []
    expands: list[EvidenceItem] = []
    evidence_status: Optional[str] = None

class Step0Output(BaseModel):
    per_lemma: list[LemmaEvidence]

class LemmaDecision(BaseModel):
    lemma: str
    decision: Literal["confirmed", "removed", "escalated"]
    decision_reason: str
    evidence_case: str
    reasoning: dict
    actions: list[dict] = []

class Step1Output(BaseModel):
    per_lemma: list[LemmaDecision]

class CandidateDecision(BaseModel):
    candidate: str
    decision: Literal["added", "rejected", "proposed_new_synset"]
    decision_reason: str
    reasoning: dict
    actions: list[dict] = []

class Step2Output(BaseModel):
    per_candidate: list[CandidateDecision] = []

class Step3Output(BaseModel):
    assessment_decision: Literal["retain", "revise"]
    assessment_reason: str
    authored_definitions: list[dict] = []
    reasoning: dict
    actions: list[dict] = []

class Step4Output(BaseModel):
    hypernymy: dict
    reasoning: dict
    actions: list[dict] = []

class LemmaEnrichment(BaseModel):
    lemma: str
    enrichment: dict
    collocations: list[dict] = []
    examples: list[dict] = []
    morphology: Optional[dict] = None
    pos_check: dict

class Step5Output(BaseModel):
    per_lemma: list[LemmaEnrichment]
    cultural_fit: dict
    reasoning: dict
    actions: list[dict] = []


# ═══════════════════════════════════════════════════════════════
# DSPy Signatures
# ═══════════════════════════════════════════════════════════════

class EvidenceClassification(dspy.Signature):
    """Classify dictionary evidence for each lemma in an Arabic WordNet synset.

    Parse the evidence YAML and for each lemma, read all dictionary entries.
    Classify each entry as:
    - confirm: supports the lemma having the synset's meaning
    - contradicts: shows the lemma has a different meaning
    - expands: reveals an additional semantic dimension

    A single entry may appear in multiple categories.
    Use llm_query() for borderline semantic judgments.
    Write analysis in Arabic.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata: ID, lemmas, definition, hypernym chain")
    evidence_yaml: str = dspy.InputField(desc="Full evidence YAML with per_lemma and per_synset data")
    step0_output: Step0Output = dspy.OutputField(desc="Classified evidence per lemma")


class LemmaValidation(dspy.Signature):
    """Validate each lemma's membership in the synset.

    For each lemma, perform:
    1. Evidence assessment based on Step 0 classifications
    2. Substitution test: can this lemma replace others in multiple contexts?
    3. MWE check: is a multi-word expression a real lexical unit?
    4. Dialectal check: is the lemma Standard Arabic (fusha)?
    5. Calque/loanword detection

    Use llm_query() for substitution test judgments.
    Write reasoning in Arabic.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata")
    lemma_evidence: str = dspy.InputField(desc="Per-lemma evidence (step1_headword, step3_root_family, etc.)")
    step0_results: str = dspy.InputField(desc="Step 0 evidence classification results (JSON)")
    step1_output: Step1Output = dspy.OutputField(desc="Validation decision per lemma")


class MissingLemmas(dspy.Signature):
    """Discover missing lemmas from per_synset evidence.

    Search the per_synset evidence (FTS keyword search, English bridge, specialized filters)
    for lemma candidates not currently in the synset.

    For each candidate:
    1. Check if it appears in per_synset search results
    2. Verify it fits the synset's meaning via evidence gate
    3. Run substitution test against confirmed lemmas
    4. Decide: add / reject / propose_new_synset

    Use llm_query() for semantic evaluation of candidates.
    Write reasoning in Arabic.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata")
    per_synset_evidence: str = dspy.InputField(desc="Per-synset evidence: FTS, English bridge, specialized")
    confirmed_lemmas: str = dspy.InputField(desc="Lemmas confirmed in Step 1 (JSON list)")
    step2_output: Step2Output = dspy.OutputField(desc="Candidate evaluations")


class DefinitionReview(dspy.Signature):
    """Review the synset definition and author new definitions if needed.

    Based on the evidence summary from Step 0:
    1. Assess whether the current Arabic definition is accurate and complete
    2. If inadequate, author a new terminological definition (genus + differentia)
    3. Ensure the definition follows modern Arabic lexicography style (al-Wasit)
    4. Do NOT translate the English definition literally

    Write the definition and all reasoning in Arabic.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata with current definition")
    evidence_summary: str = dspy.InputField(desc="Summary of confirming/contradicting/expanding evidence")
    step1_flags: str = dspy.InputField(desc="Flags from Step 1 (e.g., definition_review_needed)")
    step3_output: Step3Output = dspy.OutputField(desc="Definition assessment and authored definitions")


class RelationsCheck(dspy.Signature):
    """Verify hypernymy, antonymy, and other semantic relations.

    Check:
    1. Hypernymy: is the current hypernym correct? Check 3 levels up.
    2. Antonymy: no two lemmas in the same synset should be antonyms.
    3. Internal conflict: are there contradictory lemmas?

    Write reasoning in Arabic.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata with relations and hypernym chain")
    confirmed_lemmas: str = dspy.InputField(desc="Active lemma list from Steps 1-2 (JSON)")
    evidence_summary: str = dspy.InputField(desc="Key evidence relevant to relations")
    step4_output: Step4Output = dspy.OutputField(desc="Relations verification results")


class Enrichment(dspy.Signature):
    """Enrich each confirmed lemma with linguistic metadata.

    For each lemma, determine:
    - usage: archaic / modern / common
    - eloquence: eloquent / neologism / colloquial / loanword
    - connotation: positive / negative / reverential / pejorative / neutral
    - literal_figurative: literal / figurative (+ figurative_relation if figurative)
    - root: Arabic root (e.g., ك-ت-ب)
    - collocations: strong collocations from evidence (verb_object, adj_noun, etc.)
    - examples: usage examples (from evidence or authored)
    - morphology: broken plural links, form corrections
    - POS check: syntactic frame for verbs, adverb acceptance, etc.

    Use llm_query() for nuanced decisions. Write reasoning in Arabic.
    """
    synset_info: str = dspy.InputField(desc="Synset metadata")
    lemma_evidence: str = dspy.InputField(desc="Per-lemma evidence for enrichment")
    step0_expands: str = dspy.InputField(desc="Expand evidence items to consume (JSON)")
    confirmed_lemmas: str = dspy.InputField(desc="Active lemma list (JSON)")
    step5_output: Step5Output = dspy.OutputField(desc="Enrichment data per lemma")


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def serialize(obj) -> str:
    """Serialize a Pydantic model to JSON string."""
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2)
    return json.dumps(obj, ensure_ascii=False, indent=2)


def extract_confirmed(step1: Step1Output) -> str:
    """Extract confirmed lemmas as a JSON list."""
    confirmed = [ld.lemma for ld in step1.per_lemma if ld.decision == "confirmed"]
    return json.dumps(confirmed, ensure_ascii=False)


def build_evidence_summary(step0: Step0Output) -> str:
    """Build a compact evidence summary for Steps 3-4."""
    summary = []
    for le in step0.per_lemma:
        entry = {
            "lemma": le.lemma,
            "confirm_count": len(le.confirm),
            "contradicts_count": len(le.contradicts),
            "expands_count": len(le.expands),
        }
        if le.confirm:
            entry["key_confirm"] = le.confirm[0].text[:200]
        if le.contradicts:
            entry["key_contradicts"] = le.contradicts[0].text[:200]
        summary.append(entry)
    return json.dumps(summary, ensure_ascii=False, indent=2)


def extract_expands(step0: Step0Output) -> str:
    """Extract expand evidence items for Step 5."""
    expands = {}
    for le in step0.per_lemma:
        if le.expands:
            expands[le.lemma] = [e.model_dump() for e in le.expands]
    return json.dumps(expands, ensure_ascii=False, indent=2)


def extract_flags(step1: Step1Output) -> str:
    """Extract flags from Step 1 for Step 3."""
    flags = {}
    for ld in step1.per_lemma:
        if ld.decision == "removed":
            flags["definition_review_needed"] = True
    return json.dumps(flags, ensure_ascii=False)


def partition_evidence(evidence_yaml: str) -> tuple[str, str]:
    """Split evidence into per_lemma and per_synset partitions."""
    data = yaml.safe_load(evidence_yaml)
    per_lemma = data.get("per_lemma", {})
    per_synset = data.get("per_synset", {})
    return (
        yaml.dump(per_lemma, allow_unicode=True, default_flow_style=False),
        yaml.dump(per_synset, allow_unicode=True, default_flow_style=False),
    )


def compile_review(s0, s1, s2, s3, s4, s5) -> str:
    """Compile all step outputs into the final review YAML."""
    review = {
        "step0_evidence": s0.step0_output.model_dump() if isinstance(s0.step0_output, BaseModel)
                          else s0.step0_output,
        "step1_lemma_validation": s1.step1_output.model_dump() if isinstance(s1.step1_output, BaseModel)
                                  else s1.step1_output,
        "step2_missing_lemmas": s2.step2_output.model_dump() if isinstance(s2.step2_output, BaseModel)
                                else s2.step2_output,
        "step3_definition": s3.step3_output.model_dump() if isinstance(s3.step3_output, BaseModel)
                            else s3.step3_output,
        "step4_relations": s4.step4_output.model_dump() if isinstance(s4.step4_output, BaseModel)
                           else s4.step4_output,
        "step5_enrichment": s5.step5_output.model_dump() if isinstance(s5.step5_output, BaseModel)
                            else s5.step5_output,
    }
    return yaml.dump(review, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ═══════════════════════════════════════════════════════════════
# Pipeline Module
# ═══════════════════════════════════════════════════════════════

class LinguistReviewPipeline(dspy.Module):
    def __init__(self, model="openai/gpt-4o", sub_model="openai/gpt-4o-mini"):
        super().__init__()
        self.sub_lm = dspy.LM(sub_model)

        # Steps needing evidence exploration → RLM
        self.step0 = dspy.RLM(
            EvidenceClassification,
            max_iterations=15, max_llm_calls=30, sub_lm=self.sub_lm,
        )
        self.step1 = dspy.RLM(
            LemmaValidation,
            max_iterations=15, max_llm_calls=30, sub_lm=self.sub_lm,
        )
        self.step2 = dspy.RLM(
            MissingLemmas,
            max_iterations=12, max_llm_calls=20, sub_lm=self.sub_lm,
        )
        self.step5 = dspy.RLM(
            Enrichment,
            max_iterations=15, max_llm_calls=30, sub_lm=self.sub_lm,
        )

        # Steps working on summaries → ChainOfThought
        self.step3 = dspy.ChainOfThought(DefinitionReview)
        self.step4 = dspy.ChainOfThought(RelationsCheck)

    def forward(self, synset_info: str, evidence_yaml: str):
        # Partition evidence
        per_lemma_yaml, per_synset_yaml = partition_evidence(evidence_yaml)

        # Step 0: Evidence Classification (full evidence)
        s0 = self.step0(synset_info=synset_info, evidence_yaml=evidence_yaml)

        # Step 1: Lemma Validation (per-lemma evidence + Step 0 results)
        s1 = self.step1(
            synset_info=synset_info,
            lemma_evidence=per_lemma_yaml,
            step0_results=serialize(s0.step0_output),
        )

        # Derive intermediate data
        confirmed = extract_confirmed(s1.step1_output)
        evidence_summary = build_evidence_summary(s0.step0_output)
        flags = extract_flags(s1.step1_output)

        # Step 2: Missing Lemmas (per-synset evidence)
        s2 = self.step2(
            synset_info=synset_info,
            per_synset_evidence=per_synset_yaml,
            confirmed_lemmas=confirmed,
        )

        # Step 3: Definition Review (summary only — no raw evidence)
        s3 = self.step3(
            synset_info=synset_info,
            evidence_summary=evidence_summary,
            step1_flags=flags,
        )

        # Step 4: Relations Check (summary only)
        s4 = self.step4(
            synset_info=synset_info,
            confirmed_lemmas=confirmed,
            evidence_summary=evidence_summary,
        )

        # Step 5: Enrichment (per-lemma evidence + expands from Step 0)
        s5 = self.step5(
            synset_info=synset_info,
            lemma_evidence=per_lemma_yaml,
            step0_expands=extract_expands(s0.step0_output),
            confirmed_lemmas=confirmed,
        )

        # Compile final YAML
        review_yaml = compile_review(s0, s1, s2, s3, s4, s5)
        return dspy.Prediction(review_yaml=review_yaml)


# ── Runner ──

def main():
    import os

    dspy.configure(lm=dspy.LM("openai/gpt-4o"))

    PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    evidence_dir = os.path.join(PARENT_DIR, "sample synsets with  dictionary evidenc")
    evidence_files = sorted(f for f in os.listdir(evidence_dir) if f.endswith(".evidence.yaml"))

    # Load synset info
    filepath = os.path.join(evidence_dir, evidence_files[0])
    with open(filepath, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    synset = raw.get("synset", {})
    synset_info = yaml.dump({
        "id": synset.get("id"), "pos": synset.get("pos"),
        "lemmas": synset.get("lemmas"), "definition_ar": synset.get("definition_ar"),
        "definition_en": synset.get("oewn", {}).get("definition_en"),
        "hypernym_chain": synset.get("hypernym_chain"),
        "relations": synset.get("relations"),
    }, allow_unicode=True, default_flow_style=False)

    with open(filepath, "r", encoding="utf-8") as f:
        evidence_yaml = f.read()

    pipeline = LinguistReviewPipeline()
    result = pipeline(synset_info=synset_info, evidence_yaml=evidence_yaml)

    synset_id = evidence_files[0].replace(".evidence.yaml", "")
    with open(f"{synset_id}.review.yaml", "w", encoding="utf-8") as f:
        f.write(result.review_yaml)
    print(f"Review saved: {synset_id}.review.yaml")


if __name__ == "__main__":
    main()
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Each step gets only relevant context | More complex orchestration code |
| Steps 3-4 are cheaper (CoT, no REPL) | Error propagation: bad Step 0 → bad everything |
| Typed Pydantic I/O validates at each boundary | Helper functions are non-trivial |
| Individual steps can be debugged/replaced | No optimization (no golden examples) |
| Modular: can swap RLM ↔ CoT per step | Still no structural quality checks |

---

## 5. Level 3: Optimized Pipeline

### Architecture

Same multi-stage pipeline as Level 2, with three additions:

1. **Custom Tools** — Domain-specific functions injected into RLM steps
2. **dspy.Refine** — Quality assurance wrapping on critical steps (0, 1)
3. **MIPROv2** — Prompt optimization using golden review examples

```
              ┌─────────────────────────────────────────┐
              │           Custom Tools                   │
              │  ┌─────────────────────────────────────┐ │
              │  │ extract_entries_for_lemma()         │ │
              │  │ lookup_root_family()                │ │
              │  │ run_substitution_test()             │ │
              │  │ check_arabic_morphology()           │ │
              │  │ parse_evidence_yaml()               │ │
              │  └─────────────────────────────────────┘ │
              └───────────────┬─────────────────────────┘
                              │ injected via tools=
                              ▼
┌──────────────────────────────────────────────────────────┐
│              LinguistReviewPipeline (Level 3)            │
│                                                          │
│  ┌─────────────────────┐                                 │
│  │  Step 0: RLM        │◄── tools: extract_entries,      │
│  │  wrapped in Refine  │    lookup_root, parse_yaml      │
│  │  (N=3, reward=0.8)  │                                 │
│  └────────┬────────────┘                                 │
│           │                                              │
│  ┌────────▼────────────┐                                 │
│  │  Step 1: RLM        │◄── tools: substitution_test,    │
│  │  wrapped in Refine  │    morphology_check,             │
│  │  (N=3, reward=0.8)  │    extract_entries               │
│  └────────┬────────────┘                                 │
│           │                                              │
│  ┌────────▼────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Step 2: RLM     │  │ Step 3: CoT  │  │ Step 4: CoT│  │
│  │ + tools         │  │ (no change)  │  │ (no change)│  │
│  └────────┬────────┘  └──────┬───────┘  └─────┬──────┘  │
│           │                  │                │          │
│  ┌────────▼──────────────────▼────────────────▼──────┐   │
│  │  Step 5: RLM + tools                              │   │
│  └───────────────────────┬───────────────────────────┘   │
│                          │                               │
│  ┌───────────────────────▼───────────────────────────┐   │
│  │  compile_review (same as Level 2)                 │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  Optimized with MIPROv2 (golden examples → tuned prompts)│
└──────────────────────────────────────────────────────────┘
```

### Custom Tools

```python
# ═══════════════════════════════════════════════════════════════
# tools.py — Domain-specific tools for RLM steps
# ═══════════════════════════════════════════════════════════════

def parse_evidence_yaml(evidence_yaml: str) -> str:
    """Parse evidence YAML and return a structured JSON summary.

    Returns a JSON object with keys:
    - synset: {id, lemmas, pos, definition_ar}
    - per_lemma_keys: list of lemma names
    - per_synset_keys: list of search step names
    - lemma_entry_counts: {lemma: {step: count}} for quick navigation
    """
    import yaml, json
    data = yaml.safe_load(evidence_yaml)

    synset = data.get("synset", {})
    per_lemma = data.get("per_lemma", {})
    per_synset = data.get("per_synset", {})

    counts = {}
    for lemma, steps in per_lemma.items():
        counts[lemma] = {}
        for step_name, step_data in steps.items():
            if isinstance(step_data, dict):
                entries = step_data.get("entries", [])
                by_root = step_data.get("by_root", {})
                total = len(entries) + sum(len(r.get("entries", [])) for r in by_root.values())
                if total > 0:
                    counts[lemma][step_name] = total

    summary = {
        "synset": {
            "id": synset.get("id"),
            "lemmas": synset.get("lemmas"),
            "pos": synset.get("pos"),
            "definition_ar": synset.get("definition_ar"),
        },
        "per_lemma_keys": list(per_lemma.keys()),
        "per_synset_keys": list(per_synset.keys()),
        "lemma_entry_counts": counts,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def extract_entries_for_lemma(evidence_yaml: str, lemma: str) -> str:
    """Extract all dictionary entries for a specific lemma.

    Searches across step1_headword, step3_root_family, step6_examples,
    and step8_reverse_lookup. Returns a compact JSON list of entries,
    each with: headword, root, definitions_text, dict_name_ar, dict_period.
    """
    import yaml, json
    data = yaml.safe_load(evidence_yaml)
    per_lemma = data.get("per_lemma", {})
    lemma_data = per_lemma.get(lemma, {})

    entries = []
    for step_key in ["step1_headword", "step3_root_family",
                     "step6_examples", "step8_reverse_lookup"]:
        step = lemma_data.get(step_key, {})
        if "entries" in step:
            entries.extend(step["entries"])
        if "by_root" in step:
            for root_data in step["by_root"].values():
                entries.extend(root_data.get("entries", []))

    # Deduplicate by (headword, dict_name_ar)
    seen = set()
    unique = []
    for e in entries:
        key = (e.get("headword", ""), e.get("dict_name_ar", ""))
        if key not in seen:
            seen.add(key)
            unique.append({
                "headword": e.get("headword"),
                "root": e.get("root"),
                "definitions_text": e.get("definitions_text", "")[:500],
                "dict_name_ar": e.get("dict_name_ar"),
                "dict_period": e.get("dict_period"),
            })
    return json.dumps(unique, ensure_ascii=False, indent=2)


def lookup_root_family(evidence_yaml: str, root: str) -> str:
    """Find all entries sharing a given Arabic root across all lemmas.

    Returns a JSON list of {lemma, entries} for each lemma that has
    entries with the specified root in step3_root_family.
    """
    import yaml, json
    data = yaml.safe_load(evidence_yaml)
    results = []
    for lemma_key, ld in data.get("per_lemma", {}).items():
        s3 = ld.get("step3_root_family", {})
        by_root = s3.get("by_root", {})
        if root in by_root:
            entries = by_root[root].get("entries", [])
            results.append({
                "lemma": lemma_key,
                "entry_count": len(entries),
                "entries": [
                    {"headword": e.get("headword"), "definitions_text": e.get("definitions_text", "")[:300]}
                    for e in entries[:5]
                ],
            })
    return json.dumps(results, ensure_ascii=False, indent=2)


def run_substitution_test(lemma_a: str, lemma_b: str, sentence: str) -> str:
    """Generate a substitution test: replace lemma_a with lemma_b in a sentence.

    Returns both the original and substituted sentences for the LLM to judge
    whether the meaning is preserved. The LLM should use llm_query() on the
    returned string for the semantic judgment.
    """
    substituted = sentence.replace(lemma_a, lemma_b)
    return (
        f"Original:    {sentence}\n"
        f"Substituted: {substituted}\n"
        f"Question: هل يحافظ الاستبدال على المعنى الأساسي؟ حلّل بدقة."
    )


def check_arabic_morphology(lemma: str) -> str:
    """Analyze basic Arabic morphological properties of a lemma.

    Returns a JSON object with:
    - is_mwe: whether the lemma contains spaces (multi-word expression)
    - has_tashkeel: whether diacritical marks are present
    - has_al_prefix: whether it starts with the definite article
    - char_count: total character count
    - arabic_ratio: ratio of Arabic characters to total
    """
    import re, json
    arabic_chars = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', lemma))
    total_chars = len(lemma.replace(" ", ""))
    return json.dumps({
        "is_mwe": " " in lemma,
        "has_tashkeel": bool(re.search(r'[\u064B-\u065F\u0670]', lemma)),
        "has_al_prefix": lemma.startswith("ال") or lemma.startswith("ٱل"),
        "char_count": len(lemma),
        "arabic_ratio": round(arabic_chars / total_chars, 2) if total_chars else 0,
    }, ensure_ascii=False, indent=2)
```

### Reward Functions

```python
# ═══════════════════════════════════════════════════════════════
# metrics.py — Reward functions for dspy.Refine
# ═══════════════════════════════════════════════════════════════

def step0_reward(args: dict, pred) -> float:
    """Structural quality check for Step 0 evidence classification."""
    try:
        output = pred.step0_output
        if not isinstance(output, Step0Output):
            return 0.0

        score = 0.0
        total_checks = 0

        # Check: all lemmas from synset_info are covered
        import yaml
        synset = yaml.safe_load(args.get("synset_info", ""))
        expected_lemmas = set(synset.get("lemmas", []))
        actual_lemmas = {le.lemma for le in output.per_lemma}
        if expected_lemmas == actual_lemmas:
            score += 1.0
        elif expected_lemmas.issubset(actual_lemmas):
            score += 0.5
        total_checks += 1

        # Check: each lemma has at least one classification or evidence_status
        for le in output.per_lemma:
            has_evidence = le.confirm or le.contradicts or le.expands
            if has_evidence or le.evidence_status == "no_material_found":
                score += 1.0
            total_checks += 1

        # Check: evidence items have text and source
        for le in output.per_lemma:
            for item in le.confirm + le.contradicts + le.expands:
                if item.text and item.source:
                    score += 1.0
                total_checks += 1

        return score / total_checks if total_checks > 0 else 0.0
    except Exception:
        return 0.0


def step1_reward(args: dict, pred) -> float:
    """Structural quality check for Step 1 lemma validation."""
    try:
        output = pred.step1_output
        if not isinstance(output, Step1Output):
            return 0.0

        score = 0.0
        total_checks = 0

        for ld in output.per_lemma:
            # Check: decision is valid
            if ld.decision in ("confirmed", "removed", "escalated"):
                score += 1.0
            total_checks += 1

            # Check: reasoning is non-empty
            if ld.reasoning and len(ld.reasoning) > 0:
                score += 1.0
            total_checks += 1

            # Check: removed lemmas have actions
            if ld.decision == "removed" and ld.actions:
                score += 1.0
            total_checks += 1

            # Check: decision_reason is substantive (>20 chars)
            if len(ld.decision_reason) > 20:
                score += 1.0
            total_checks += 1

        return score / total_checks if total_checks > 0 else 0.0
    except Exception:
        return 0.0


def review_quality_metric(example, prediction, trace=None) -> float:
    """Overall review quality metric for MIPROv2 optimization.

    Compares a predicted review YAML against a golden review.
    Checks structural completeness and key decision alignment.
    """
    import yaml
    try:
        pred = yaml.safe_load(prediction.review_yaml)
        gold = yaml.safe_load(example.golden_yaml)

        score = 0.0
        total = 0

        # Check: all 6 steps present
        for step in ["step0_evidence", "step1_lemma_validation", "step2_missing_lemmas",
                     "step3_definition", "step4_relations", "step5_enrichment"]:
            total += 1
            if step in pred:
                score += 1.0

        # Check: lemma decisions match golden
        gold_decisions = {}
        for ld in gold.get("step1_lemma_validation", {}).get("per_lemma", []):
            gold_decisions[ld["lemma"]] = ld["decision"]

        for ld in pred.get("step1_lemma_validation", {}).get("per_lemma", []):
            lemma = ld.get("lemma")
            if lemma in gold_decisions:
                total += 1
                if ld.get("decision") == gold_decisions[lemma]:
                    score += 1.0

        return score / total if total > 0 else 0.0
    except Exception:
        return 0.0
```

### Optimized Pipeline

```python
# ═══════════════════════════════════════════════════════════════
# level3_optimized.py — Pipeline with Tools + Refine + MIPROv2
# ═══════════════════════════════════════════════════════════════

import dspy
from tools import (
    parse_evidence_yaml, extract_entries_for_lemma,
    lookup_root_family, run_substitution_test,
    check_arabic_morphology,
)
from metrics import step0_reward, step1_reward


class OptimizedReviewPipeline(dspy.Module):
    def __init__(self, model="openai/gpt-4o", sub_model="openai/gpt-4o-mini"):
        super().__init__()
        self.sub_lm = dspy.LM(sub_model)

        # Tool sets per step
        tools_step0 = [parse_evidence_yaml, extract_entries_for_lemma, lookup_root_family]
        tools_step1 = [run_substitution_test, check_arabic_morphology, extract_entries_for_lemma]
        tools_step2 = [extract_entries_for_lemma, lookup_root_family]
        tools_step5 = [extract_entries_for_lemma, check_arabic_morphology]

        # Step 0: RLM + Refine (critical step — must classify correctly)
        step0_rlm = dspy.RLM(
            EvidenceClassification,  # Reuse Level 2 signature (or V3 enhanced)
            max_iterations=15, max_llm_calls=30,
            sub_lm=self.sub_lm, tools=tools_step0,
        )
        self.step0 = dspy.Refine(
            module=step0_rlm,
            N=3,                     # Up to 3 attempts
            reward_fn=step0_reward,
            threshold=0.8,           # Minimum quality score
        )

        # Step 1: RLM + Refine (critical step — lemma decisions)
        step1_rlm = dspy.RLM(
            LemmaValidation,
            max_iterations=15, max_llm_calls=30,
            sub_lm=self.sub_lm, tools=tools_step1,
        )
        self.step1 = dspy.Refine(
            module=step1_rlm,
            N=3,
            reward_fn=step1_reward,
            threshold=0.8,
        )

        # Step 2: RLM with tools (no Refine — fewer golden examples)
        self.step2 = dspy.RLM(
            MissingLemmas,
            max_iterations=12, max_llm_calls=20,
            sub_lm=self.sub_lm, tools=tools_step2,
        )

        # Steps 3, 4: ChainOfThought (work on summaries)
        self.step3 = dspy.ChainOfThought(DefinitionReview)
        self.step4 = dspy.ChainOfThought(RelationsCheck)

        # Step 5: RLM with tools (no Refine)
        self.step5 = dspy.RLM(
            Enrichment,
            max_iterations=15, max_llm_calls=30,
            sub_lm=self.sub_lm, tools=tools_step5,
        )

    def forward(self, synset_info: str, evidence_yaml: str):
        # Same orchestration as Level 2
        per_lemma_yaml, per_synset_yaml = partition_evidence(evidence_yaml)

        s0 = self.step0(synset_info=synset_info, evidence_yaml=evidence_yaml)
        s1 = self.step1(
            synset_info=synset_info,
            lemma_evidence=per_lemma_yaml,
            step0_results=serialize(s0.step0_output),
        )

        confirmed = extract_confirmed(s1.step1_output)
        evidence_summary = build_evidence_summary(s0.step0_output)
        flags = extract_flags(s1.step1_output)

        s2 = self.step2(
            synset_info=synset_info,
            per_synset_evidence=per_synset_yaml,
            confirmed_lemmas=confirmed,
        )
        s3 = self.step3(
            synset_info=synset_info,
            evidence_summary=evidence_summary,
            step1_flags=flags,
        )
        s4 = self.step4(
            synset_info=synset_info,
            confirmed_lemmas=confirmed,
            evidence_summary=evidence_summary,
        )
        s5 = self.step5(
            synset_info=synset_info,
            lemma_evidence=per_lemma_yaml,
            step0_expands=extract_expands(s0.step0_output),
            confirmed_lemmas=confirmed,
        )

        return dspy.Prediction(review_yaml=compile_review(s0, s1, s2, s3, s4, s5))


# ═══════════════════════════════════════════════════════════════
# MIPROv2 Optimization
# ═══════════════════════════════════════════════════════════════

def optimize(trainset, valset, model="openai/gpt-4o"):
    """Optimize pipeline prompts using golden review examples.

    trainset/valset: lists of dspy.Example with fields:
        - synset_info: str
        - evidence_yaml: str
        - golden_yaml: str (the human-reviewed output)
    """
    dspy.configure(lm=dspy.LM(model))

    pipeline = OptimizedReviewPipeline(model=model)

    optimizer = dspy.MIPROv2(
        metric=review_quality_metric,
        auto="medium",           # Balanced optimization (100 trials)
        num_threads=4,
    )

    optimized = optimizer.compile(
        pipeline,
        trainset=trainset,
        valset=valset,
    )

    optimized.save("optimized_review_pipeline.json")
    print("Optimized pipeline saved.")
    return optimized


def load_golden_examples(golden_dir: str):
    """Load golden review examples for optimization."""
    import os
    examples = []
    for fname in sorted(os.listdir(golden_dir)):
        if not fname.endswith(".review.yaml"):
            continue
        synset_id = fname.replace(".review.yaml", "")

        # Load evidence
        evidence_path = os.path.join(golden_dir, f"{synset_id}.evidence.yaml")
        if not os.path.exists(evidence_path):
            continue

        with open(evidence_path, "r", encoding="utf-8") as f:
            evidence_yaml = f.read()
            raw = yaml.safe_load(evidence_yaml)

        # Build synset_info
        synset = raw.get("synset", {})
        synset_info = yaml.dump({
            "id": synset.get("id"), "pos": synset.get("pos"),
            "lemmas": synset.get("lemmas"),
            "definition_ar": synset.get("definition_ar"),
        }, allow_unicode=True, default_flow_style=False)

        # Load golden review
        with open(os.path.join(golden_dir, fname), "r", encoding="utf-8") as f:
            golden_yaml = f.read()

        examples.append(dspy.Example(
            synset_info=synset_info,
            evidence_yaml=evidence_yaml,
            golden_yaml=golden_yaml,
        ).with_inputs("synset_info", "evidence_yaml"))

    return examples
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Custom tools eliminate YAML parsing errors in REPL | Most complex implementation |
| Refine catches structural errors and retries | Refine triples cost on Steps 0-1 |
| MIPROv2 tunes prompts for Arabic lexicography | Requires 20-30 golden review examples |
| `sub_lm` reduces cost 3-5x on bulk sub-queries | Tool impls must handle Arabic edge cases |
| Reward functions encode domain quality checks | Highest total token cost |
| Modular + optimizable + quality-assured | Deno/WASM may have Arabic string quirks |

---

## 6. Comparison Table

| Dimension | Level 1: Single RLM | Level 2: Pipeline | Level 3: Optimized |
|-----------|---------------------|--------------------|--------------------|
| **Complexity** | ~50 lines | ~300 lines | ~500 lines + tools/metrics |
| **Files** | 2 (shared + main) | 5 (shared, models, sigs, helpers, main) | 8 (+ tools, metrics, optimize) |
| **LLM Calls per Review** | 1 main × 30 iters + 80 sub | 4 RLM × 15 iters + 2 CoT + 110 sub | Same as L2 + up to 3× retry on Steps 0-1 |
| **Est. Token Cost** | ~$0.50-1.50 | ~$0.30-0.80 | ~$0.50-1.50 (with retries) |
| **Context per Step** | Full evidence (4K-22K lines) | Partitioned (1K-10K per step) | Same as L2 + tools reduce ad-hoc parsing |
| **Error Recovery** | None (single SUBMIT) | Per-step validation via Pydantic | Refine auto-retries on Steps 0-1 |
| **Output Quality** | Depends on LLM + prompt | Better (focused context) | Best (tuned prompts + quality checks) |
| **Optimization** | Not possible | Possible but manual | MIPROv2 + BootstrapFewShot |
| **Prerequisites** | Deno | Deno | Deno + 20-30 golden examples |
| **Setup Time** | 1-2 hours | 1-2 days | 5-7 days |
| **Best For** | Prototyping, quick test | Production (no golden data) | Production (with golden data) |

### Token Cost Breakdown (Estimated per Synset)

| Component | Level 1 | Level 2 | Level 3 |
|-----------|---------|---------|---------|
| Main LM (REPL iterations) | 30 × ~2K = 60K | 4×15 × ~1.5K = 90K | Same + up to 2× retry = 180K |
| Sub-LM (llm_query) | 80 × ~500 = 40K | 110 × ~400 = 44K | Same = 44K |
| CoT (Steps 3-4) | — | 2 × ~3K = 6K | 2 × ~3K = 6K |
| **Total tokens** | **~100K** | **~140K** | **~230K** |
| **Est. cost (GPT-4o + 4o-mini)** | **~$0.60** | **~$0.45** | **~$0.90** |

> Note: Level 2 is often *cheaper* than Level 1 because each RLM step has smaller context and converges faster.

---

## 7. Implementation Roadmap

### Phase 0: Prerequisites

```bash
# Install Deno (required for RLM sandbox)
curl -fsSL https://deno.land/install.sh | sh

# Install DSPy from local repo
cd /Users/salahmac/projects/wn-projects/linguistic_review_guide/dspy
pip install -e .

# Verify RLM works
python -c "
import dspy
dspy.configure(lm=dspy.LM('openai/gpt-4o-mini'))
rlm = dspy.RLM('text -> summary')
result = rlm(text='Hello world. This is a test.')
print(result.summary)
"
```

### Phase 1: Shared Foundation (all levels need this)

Create `dspy_review/shared.py`:
- Reuse `read_evidence()` and `process_evidence()` from `assemble_prompts_v2.py`
- YAML loading/dumping utilities
- LM configuration helper
- `extract_synset_info()` function (already exists in `assemble_prompts_v2.py`)

### Phase 2: Level 1 (1-2 hours)

1. Create `dspy_review/level1_single_rlm.py`
2. Test on 3 sample synsets with `verbose=True`
3. Observe REPL trajectory — does the LLM follow all 6 steps?
4. Tune `max_iterations` and `max_llm_calls`

### Phase 3: Level 2 (1-2 days)

1. Create `dspy_review/models.py` — Pydantic models
2. Create `dspy_review/signatures.py` — 6 DSPy signatures
3. Create `dspy_review/helpers.py` — Serialization, partitioning, compilation
4. Create `dspy_review/level2_pipeline.py` — Pipeline module
5. Test step-by-step: run each step individually first, then the full pipeline
6. Compare output quality vs Level 1

### Phase 4: Level 3 (5-7 days)

1. Create `dspy_review/tools.py` — 5 custom tools
2. Create `dspy_review/metrics.py` — Reward functions
3. Wrap Steps 0-1 in `dspy.Refine`
4. Test tools work correctly in the WASM sandbox
5. Create 20-30 golden review examples (manually review synsets using current prompt system)
6. Run MIPROv2 optimization
7. Evaluate optimized vs unoptimized on held-out synsets

### Recommended Starting Point

**Start with Level 1** to validate that RLM works with your evidence data format and produces reasonable reviews. Then progressively upgrade to Level 2 (better quality) and Level 3 (optimized quality) as you accumulate golden examples.

### Potential Issues to Watch

1. **YAML in WASM sandbox** — Pyodide may not include `pyyaml`. If not, register `parse_evidence_yaml` as a custom tool (Level 3 already does this) or use `json.loads()` after converting evidence to JSON.

2. **Arabic text in Pyodide** — Unicode should work, but test tashkeel handling and RTL text operations.

3. **Large variables** — RLM handles multi-MB strings via virtual filesystem injection. Evidence files up to ~500K chars should work. For very large files (>1MB), consider pre-partitioning.

4. **Pydantic output from REPL** — The LLM must construct a dict inside `SUBMIT()` that maps to the Pydantic model. For complex nested models, consider using simpler `dict` output types and validating externally.

### File Structure

```
dspy_review/
├── __init__.py
├── shared.py                    # LM config, evidence loading, YAML utils
├── models.py                    # Pydantic models for all 6 steps (Levels 2-3)
├── signatures.py                # DSPy signatures for all 6 steps (Levels 2-3)
├── helpers.py                   # serialize, partition, compile, extract (Levels 2-3)
├── tools.py                     # Custom tools (Level 3)
├── metrics.py                   # Reward functions + MIPROv2 metric (Level 3)
├── level1_single_rlm.py         # Level 1 implementation
├── level2_pipeline.py           # Level 2 implementation
├── level3_optimized.py          # Level 3 implementation
├── optimize.py                  # MIPROv2 optimization script (Level 3)
├── run.py                       # CLI entrypoint (--level 1|2|3)
└── golden/                      # Golden review examples (Level 3)
    ├── awn4-XXXXX.evidence.yaml
    └── awn4-XXXXX.review.yaml
```
