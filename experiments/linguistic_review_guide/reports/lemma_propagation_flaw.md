# Research Report: Removed Lemma Propagation Flaw in dspy_review Pipeline

## Problem Statement

When the pipeline marks a lemma as `removed` or `escalated` in Step 1 (lemma validation), that decision is **not propagated** to Steps 3, 4, and 5. Removed and escalated lemmas continue to receive full processing — antonym assignments, selectional restrictions, enrichment fields, collocations, and example sentences — creating contradictory outputs where a lemma is simultaneously removed and enriched.

First observed in `awn4-05124030-n.review.yaml`: `كثرة هائلة` is removed in Step 1 but receives a full enrichment block, antonym assignment (ندرة), and selectional restriction in Steps 4–5.

---

## Root Cause Analysis

### The Core Architectural Flaw: No Working Lemma Set Propagation

The algorithm specification (`draft_api.md`) defines two named lemma sets:
- **`اللمّات_المؤكدة`** (confirmed lemmas) — output of Step 1
- **`اللمّات_المؤكدة_والمضافة`** (confirmed + added) — merged from Steps 1 & 2

Steps 4 and 5 explicitly iterate over these filtered sets in the spec. The pipeline code (`pipeline.py`) correctly computes these sets via `extract_confirmed_lemmas()` and `merge_lemma_lists()`. **However, the filtered set is undermined by six bugs:**

### Bug 1: `synset_info` is never filtered (pipeline.py)

The same raw `synset_info` string — containing the **original, unfiltered lemma list** from the AWN database — is passed verbatim to every step. Steps 4 and 5 see both `confirmed_lemmas` (filtered) and `synset_info` (unfiltered) as inputs. The LLM naturally reasons over all lemmas it sees in `synset_info`, regardless of the `confirmed_lemmas` parameter.

**Location**: `pipeline.py` — `synset_info` is passed unchanged to `self.step4_cot()` (line ~501) and `self.step5_cot()` (line ~516).

### Bug 2: `extract_step0_evidence_summary()` is not Step-1-aware (extractors.py)

This function extracts evidence from Step 0's output for **all original lemmas**. It does not accept a `confirmed_lemmas` filter parameter. The result is passed to Step 5 as `confirmed_lemmas_with_evidence` — a misleading field name, since the value actually contains evidence for **all** lemmas including removed ones.

**Location**: `extractors.py` lines 223–270. The function signature is `extract_step0_evidence_summary(step0_yaml: str)` — no filter parameter.

### Bug 3: `extract_examples_evidence()` uses the raw evidence file (extractors.py)

This function pulls examples from the pre-review `evidence_yaml` for every lemma unconditionally. No awareness of Step 1 decisions.

**Location**: `extractors.py` lines 302–315. Iterates over `data["per_lemma"]` from the raw evidence file.

### Bug 4: Step 5 has no explicit `confirmed_lemmas` input field (signatures.py)

Unlike Step 4, which receives a `confirmed_lemmas` string input, Step 5's signature (`Step5Enrichment`) has no such field. The model must infer which lemmas are "active" solely from the evidence summary blob — which (per Bug 2) includes all lemmas.

**Location**: `signatures.py` — `Step5Enrichment` class, lines ~290–315. Compare with `Step4Relations` which has `confirmed_lemmas: str = dspy.InputField(...)`.

### Bug 5: `compile_review_yaml()` does blind merging with no consistency checks (pipeline.py)

The final review compiler collects actions from all steps via `collect_actions()` and concatenates them without deduplication or contradiction detection. A single review file can contain both "remove lemma X" (from Step 1) and "add antonym for lemma X" (from Step 4) in the same `actions` list.

**Location**: `pipeline.py` lines 260–318. `review.update(data)` and `all_actions.extend(collect_actions(data))`.

### Bug 6: Step 3 definitions accommodate escalated lemmas without human review (model behavior)

Step 3 (definition authoring) receives `synset_info` containing all lemmas and crafts definitions that accommodate escalated lemmas — effectively resolving conflicts that Step 1 explicitly flagged as requiring human review. This is a subtler issue: the model acts on escalated lemma semantics even though the algorithm says to defer to human review.

---

## Evidence: Per-File Analysis of All 5 Review Outputs

### awn4-05124030-n (وفرة مذهلة ومحيرة — bewildering profusion)

| Lemma | Step 1 Decision | Step 4 Leak | Step 5 Leak | Contradictory Actions |
|---|---|---|---|---|
| كثرة هائلة | **removed** | antonym ندرة assigned; selectional restriction written | full enrichment: root, usage, collocation, example | remove + add antonym + record enrichment note |
| متاهة | **escalated** | selectional restriction written | full enrichment: root, collocation, example | escalate + record split note + enrich |

### awn4-08453572-n (أهل الحرفة / نقابة — craft/guild)

| Lemma | Step 1 Decision | Step 4 Leak | Step 5 Leak | Contradictory Actions |
|---|---|---|---|---|
| أهل الحرفة | **removed** | antonymy check (no antonym found); selectional restriction | full enrichment: root أ-ه-ل, collocation, example | remove + record semantic note + request human review again |
| نقابة | **escalated** | selectional restriction; re-escalated | full enrichment: root ن-ق-ب, collocation, example | escalate + enrich + re-escalate |

Step 3 also resolves the escalation unilaterally: the authored definition merges both "persons" and "institution" senses ("جماعة من المشتغلين بمهنة أو حرفة واحدة، أو الهيئة التنظيمية..."), bypassing the human review flag.

### awn4-13927849-n (حز / خدش / شق / وخزة — groove/scratch/nick)

| Lemma | Step 1 Decision | Step 4 Leak | Step 5 Leak | Contradictory Actions |
|---|---|---|---|---|
| وخزة | **escalated** | Correctly absent (sole clean case across all files) | full enrichment: root و-خ-ز, collocation "وخزة إبرة", example | escalate + defend inclusion in enrichment note |

Step 3 expands the definition to include "أو نقطي" specifically to accommodate `وخزة` — resolving a conflict flagged for human review.

### awn4-05934990-n and awn4-10691175-n (controls)

**No propagation issues** — all lemmas were confirmed in Step 1. These serve as controls demonstrating the pipeline works correctly when no removals or escalations occur.

---

## Data Flow Diagram

```
                    ┌──────────────┐
                    │ evidence.yaml│ (raw, all lemmas)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Step 0     │ (RLM: classify evidence per lemma)
                    │  ALL lemmas  │
                    └──────┬───────┘
                           │
              step0_yaml   │   synset_info (unfiltered, passed to ALL steps)
              (all lemmas)  │        │
                    ┌──────▼───────┐ │
                    │   Step 1     │ │  ← Decisions: confirmed / removed / escalated
                    └──────┬───────┘ │
                           │         │
            ┌──────────────┤         │
            │              │         │
   extract_confirmed_      │         │
   lemmas() ✓ CORRECT      │         │
            │              │         │
            ▼              │         │
   confirmed = [...]       │         │
   (only confirmed)        │         │
            │              │         │
    ┌───────▼──────┐       │         │
    │   Step 2     │       │         │
    │  confirmed   │ ✓     │         │
    │  lemmas only │       │         │
    └───────┬──────┘       │         │
            │              │         │
   all_lemmas = confirmed  │         │
              + added ✓    │         │
            │              │         │
    ┌───────▼──────┐  ┌────▼────┐   │
    │   Step 4     │  │ Step 3  │   │
    │ confirmed_   │  │ synset_ │←──┤  ← synset_info has ALL lemmas
    │ lemmas ✓     │  │ info ✗  │   │
    │ BUT synset_  │  └─────────┘   │
    │ info ✗       │                │
    └──────────────┘                │
                                    │
    ┌───────────────────────────────┤
    │   Step 5                      │
    │   synset_info ✗ ──────────────┘  ← unfiltered
    │   evidence_summary ✗             ← extract_step0_evidence_summary() has ALL lemmas
    │   examples_evidence ✗            ← extract_examples_evidence() has ALL lemmas
    │   NO confirmed_lemmas field      ← unlike Step 4, no explicit filtered list
    └───────────────────────────────┘

    ✓ = correctly filtered     ✗ = contains removed/escalated lemmas
```

---

## Cross-Cutting Patterns

### Pattern 1: Enrichment blindness to removal/escalation
In all 3 files with removed/escalated lemmas, Steps 4 and 5 include those lemmas. The pipeline's filtering is correct in the Python orchestration layer but does not reach the LLM's actual input context.

### Pattern 2: Definition revision as implicit reinstatement
In 2 of 3 files (awn4-05124030-n and awn4-13927849-n), Step 3 revises the definition to accommodate an escalated lemma's semantic field — unilaterally resolving a conflict flagged for human review.

### Pattern 3: Double escalation without resolution tracking
In awn4-08453572-n, `أهل الحرفة` is removed in Step 1, then surfaces for human review **again** in Step 5. No state tracking prevents reopening a resolved decision.

### Pattern 4: Contradictory action accumulation
The master `actions` list in all 3 problematic files contains simultaneous "remove" and "enrich" instructions for the same lemma. An action executor would face contradictions.

### Pattern 5: Step 4 selectional_restrictions as consistent offender
Across all 3 problematic files, Step 4's `selectional_restrictions` includes all original lemmas regardless of Step 1 outcome.

---

## Severity Assessment

| Bug | Severity | Impact |
|---|---|---|
| Bug 1: `synset_info` unfiltered | **High** | Affects Steps 3, 4, 5 — model sees removed lemmas in every step |
| Bug 2: `extract_step0_evidence_summary` unfiltered | **High** | Step 5 receives evidence for removed lemmas; field name misleading |
| Bug 3: `extract_examples_evidence` unfiltered | **Medium** | Step 5 receives examples for removed lemmas |
| Bug 4: Step 5 has no `confirmed_lemmas` field | **High** | Model has no authoritative filtered list to work from |
| Bug 5: Blind action merging | **Medium** | Contradictory actions in output; would break downstream executor |
| Bug 6: Step 3 resolves escalations unilaterally | **Low** | Subtle model behavior issue; harder to fix architecturally |

---

## Files Involved

| File | Lines of Interest | Issue |
|---|---|---|
| `dspy_review/pipeline.py` | ~424–525 (forward method), ~260–318 (compile) | Bugs 1, 5 |
| `dspy_review/extractors.py` | ~223–270 (step0 summary), ~302–315 (examples) | Bugs 2, 3 |
| `dspy_review/signatures.py` | ~290–315 (Step5Enrichment) | Bug 4 |
