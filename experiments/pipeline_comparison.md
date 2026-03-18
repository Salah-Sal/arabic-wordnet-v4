# Pipeline Comparison: Current vs. Proposed Stage Ordering

Both approaches are **single-session** (one `claude -p` invocation per synset). The difference is how the stages are ordered and structured within that session.

---

## 1. Step Ordering

### Current Pipeline (`claude_code_db/`)

```
┌─ Single session ─────────────────────────────────────────────┐
│                                                               │
│  Step 0:   Evidence Classification                            │
│            Query DB for ALL existing lemmas.                  │
│            Classify dictionary quotes: confirm/contradict/    │
│            expand per lemma.                                  │
│                        ↓                                      │
│  Step 0.5: Lemma Generation                                   │
│            Read masked synset_info (lemmas hidden).           │
│            Query DB (FTS keyword + English bridge).           │
│            Generate 2–4 candidates.                           │
│            ⚠ LLM already saw lemmas in Step 0.               │
│                        ↓                                      │
│  Step 1:   Lemma Validation (10+ checks)                      │
│            Validate existing + candidates together.           │
│                        ↓                                      │
│  Step 3:   Definition Processing                              │
│            Retain or revise Arabic definition.                │
│                        ↓                                      │
│  Step 4:   Relations Check                                    │
│            Hypernymy, antonymy, verb frames.                  │
│                        ↓                                      │
│  Step 5:   Enrichment & Cultural Fit                          │
│            Roots, examples, morphology, cultural assessment.  │
│                                                               │
│  → Output: {synset_id}.review.yaml                            │
└───────────────────────────────────────────────────────────────┘
```

**Order: Evidence → Generate → Validate → Definition → Relations → Enrichment**

### Proposed Pipeline (`my_notes.md`)

```
┌─ Single session ─────────────────────────────────────────────┐
│                                                               │
│  Stage 1:  Review + Generate                                  │
│            Read synset info (with existing lemmas visible).   │
│            NO DB queries. NO dictionary evidence.             │
│            Assess existing content linguistically.            │
│            Generate 4 new/improved lemma candidates           │
│            using terminology guide only.                      │
│                        ↓                                      │
│  Stage 2:  Evidence Gathering                                 │
│            Query DB + read pre-computed evidence files.       │
│            Gather dictionary quotes for ALL lemmas            │
│            (existing + Stage 1 candidates).                   │
│            Classify: support / refute / expand.               │
│                        ↓                                      │
│  Stage 3:  Lemma Analysis                                     │
│            Judge each lemma (include/exclude) using           │
│            Stage 2 evidence + terminology guide.              │
│                        ↓                                      │
│  Stage 4:  Definition & Examples                              │
│            Revise existing definition.                        │
│            Author 2 additional definitions                    │
│            (encyclopedic + linguistic).                       │
│            Add examples per approved lemma.                   │
│                                                               │
│  → Output: review YAML                                        │
└───────────────────────────────────────────────────────────────┘
```

**Order: Generate → Evidence → Validate → Definition+Examples**

---

## 2. The Core Difference: When Lemmas Are Generated

This is the fundamental structural change.

| | Current | Proposed |
|---|---|---|
| **Step order** | Evidence first → then generate | Generate first → then evidence |
| **DB access during generation** | Yes — Step 0.5 runs FTS keyword + English bridge queries | No — Stage 1 has zero DB access |
| **What the LLM has seen before generating** | All existing lemmas + their classified dictionary evidence (from Step 0) | Existing lemmas (from synset_info) but NO dictionary evidence |
| **Bias type mitigated** | Tries to hide existing lemmas (masked YAML) — but evidence from Step 0 is still in context | Prevents evidence contamination — LLM generates before seeing any dictionary material |
| **Generation grounding** | Evidence-informed (DB queries provide dictionary attestations) | Knowledge-only (terminology guide + LLM's linguistic knowledge) |
| **Candidates produced** | 2–4 | 4 |

**What this means in practice:**

In the current pipeline, by the time the LLM reaches Step 0.5, it has already:
- Read every existing lemma in Step 0
- Queried the DB and seen dictionary definitions for each
- Classified evidence as confirm/contradicts/expands

The masked YAML is a soft fix — the LLM's attention weights are already shaped by what it saw. The proposed pipeline avoids this entirely by generating candidates as the **very first thing**, before any dictionary material enters the context.

The trade-off: current candidates are grounded in real dictionary attestations; proposed candidates rely purely on linguistic knowledge and the terminology guide.

---

## 3. Evidence Gathering: Same Task, Different Position

| | Current | Proposed |
|---|---|---|
| **When it happens** | Step 0 (first thing) — only for existing lemmas | Stage 2 (after generation) — for existing + generated lemmas |
| **Scope** | Evidence for existing lemmas only; candidates get separate validation queries in Step 1 | Evidence for ALL lemmas at once (existing + 4 candidates from Stage 1) |
| **Pre-fetching** | `evidence.json` pre-computes headword lookup + enrichment + English bridge | Also uses "automated evidence generated files from db" |
| **Classification** | confirm / contradicts / expands | support / refute / expand (same taxonomy) |
| **Query budget** | Strict: 6–8 queries (or 2–3 with evidence.json) | Not specified |

**Advantage of proposed ordering:** Stage 2 gathers evidence for generated candidates alongside existing lemmas in one pass, rather than needing a separate candidate-validation query later (which the current Step 1 does).

---

## 4. Analysis Depth

| Check | Current | Proposed |
|-------|---------|----------|
| MWE classification (إضافي / وصفي / مزجي) | Step 1 | Not specified |
| Dialect detection | Step 1 | Not specified |
| Substitution test | Step 1 | Not specified |
| Nuance differentiation (no absolute synonymy) | Step 1 (mandatory) | Not specified |
| Borrowing analysis (loanword / blind literal / calque) | Step 1 (3 sub-checks) | Not specified |
| Quality gate (6 criteria: currency, ease, fitness, heritage, Arabic pref, derivability) | Step 1 | Not specified |
| Morphological fitness (pattern vs. function) | Step 1 | Not specified |
| **Hypernymy check** (3 levels) | Step 4 | **Missing** |
| **Antonymy per lemma** | Step 4 | **Missing** |
| **Verb frames / selectional restrictions** | Step 4 | **Missing** |
| Root extraction/verification | Step 5 | **Missing** |
| Morphological enrichment (broken plurals) | Step 5 | **Missing** |
| Cultural fit assessment | Step 5 | **Missing** |
| Definition processing | Step 3: retain or revise | Stage 4: revise + author 2 additional |
| Examples | Step 5: 3-source priority (DB → quotes → author) | Stage 4: per approved lemma |
| Overall linguistic assessment | Not present as standalone output | Stage 1 output |
| Machine-readable actions | Yes (create_entry, add_sense, remove_sense, etc.) | Not specified |

**Summary:** The current pipeline has 10+ explicit validation checks and 2 additional analysis steps (relations, enrichment) that the proposed pipeline does not mention. The proposed pipeline adds an upfront "overall linguistic assessment" that the current pipeline lacks. The proposed pipeline is richer on definitions (always 3 vs. retain-or-revise).

---

## 5. What the Proposed Pipeline Gets Right

1. **Generate-before-evidence ordering** — The single most impactful change. By generating candidates before any DB interaction, the session avoids evidence contamination. This is structurally superior to the current masked-YAML workaround.

2. **Unified evidence pass** — Stage 2 gathers evidence for existing AND generated lemmas together, instead of the current two-pass approach (Step 0 for existing, then ad-hoc validation queries in Step 1 for candidates).

3. **More candidates** — 4 candidates vs. 2–4 gives the validation stage (Stage 3) more material to work with.

4. **Upfront linguistic assessment** — Stage 1 produces an overall assessment of the synset before diving into evidence. This high-level view can guide the rest of the session.

5. **Richer definition output** — Always authoring 3 definitions (revised + encyclopedic + linguistic) instead of the current retain-or-revise approach.

---

## 6. What the Proposed Pipeline Is Missing

1. **Lemma validation depth** — Stage 3 says "based on terminology guide and evidence" but doesn't specify the 10+ checks the current Step 1 performs. These checks need to be defined:
   - MWE type classification
   - Dialect detection
   - Substitution test
   - Nuance differentiation (mandatory — no absolute synonymy principle)
   - 3-part borrowing analysis (loanword / blind literal translation / calque)
   - 6-criterion quality gate
   - Morphological fitness

2. **Relations check** — Current Step 4 (hypernymy validation, antonymy, verb frames, selectional restrictions) has no equivalent. Could be folded into Stage 3 or added as a Stage 5.

3. **Enrichment layer** — Current Step 5 (root verification, morphological links, cultural fit assessment) is absent except for examples. Could be folded into Stage 4.

4. **Output schema** — No structured YAML format or machine-readable action queue defined. The current pipeline's actions (create_entry, add_sense, remove_sense, update_definition, etc.) are needed to apply reviews programmatically.

5. **Query discipline** — No query budget specified for Stage 2. The current pipeline's strict 2–8 query budget keeps costs and turn count under control.

6. **Terminology guide** — Referenced as a separate input but doesn't exist as a standalone document. The methodology lives in `review_instructions.md` lines 92–119 (metaphor → derivation → composition → Arabization priority + coinage test + lexical fixation test).

---

## 7. Stage Mapping

| Proposed Stage | Current Equivalent | Key Delta |
|---|---|---|
| Stage 1: Review + Generate 4 lemmas | Step 0.5 (lemma generation) | Proposed runs FIRST (before evidence); generates 4 vs 2–4; adds "overall linguistic assessment"; sees existing lemmas but no evidence |
| Stage 2: Gather evidence | Step 0 (evidence classification) + evidence.json | Proposed runs AFTER generation; covers all lemmas (existing + candidates) in one pass |
| Stage 3: Lemma analysis | Step 1 (lemma validation) | Current has 10+ specified checks; proposed is underspecified |
| Stage 4: Definition + examples | Step 3 (definition) + parts of Step 5 (examples) | Proposed always produces 3 definitions; current retains if adequate |
| **No equivalent** | Step 4 (relations check) | Hypernymy, antonymy, verb frames — absent |
| **No equivalent** | Step 5 enrichment (roots, morphology, cultural fit) | Only examples survive |

---

## 8. Summary

The proposed pipeline makes one structural change that matters: **generate lemmas before evidence**. This is the right call — it eliminates the evidence-contamination bias that the current masked-YAML approach only partially mitigates.

Everything else is a matter of porting existing depth into the new ordering:

- The 10+ validation checks from current Step 1 → proposed Stage 3
- Relations check from current Step 4 → proposed Stage 3 or new Stage 5
- Enrichment from current Step 5 → proposed Stage 4
- Output schema and action queue → needs to be defined
- Terminology guide → needs extraction from `review_instructions.md`

The new ordering also simplifies evidence gathering — one unified pass for all lemmas instead of two.

---

## Appendix: File Reference

| File | Purpose |
|------|---------|
| `claude_code_db/review_instructions.md` | Current system prompt (6 steps, 34K chars, bilingual) |
| `claude_code_db/db_reference.md` | DB schema, 9 query patterns, normalization rules |
| `claude_code_db/batch_runner.py` | Async batch orchestrator (AIMD, cooldown, status DB) |
| `claude_code_db/batch_status.py` | SQLite WAL-mode status tracking |
| `claude_code_db/extract_synset_info.py` | Synset data extraction + evidence.json pre-fetching |
| `claude_code_db/run_review.sh` | Shell wrapper for single-synset Claude CLI invocation |
| `claude_code_db/docker/` | Dockerfile, egress firewall, entrypoint, batch launcher |
| `spec/draft_api.md` | Formal pseudocode algorithm (collect-then-execute model, 1055 lines) |
| `spec/output_step0.yaml` | Output schema conventions |
| `experiments/my_notes.md` | Proposed 4-stage ordering |
