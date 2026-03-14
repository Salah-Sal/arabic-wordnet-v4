# dspy_review — DSPy Linguistic Reviewer for AWN4

Automated linguistic review of Arabic WordNet v4 synsets using DSPy. A 6-step pipeline of specialized modules (2 RLMs + 4 ChainOfThoughts), each scoped to its relevant algorithm section, schema section, and evidence subset from 107 Arabic dictionaries.

## Prerequisites

- Python 3.11+
- [Deno](https://deno.com/) (required by DSPy's RLM for its sandboxed REPL)

## Environment Setup

### 1. Virtual Environment

The project uses a dedicated `.venv` inside the `arabic-wordnet-v4/` directory:

```
arabic-wordnet-v4/.venv/       <-- dspy venv (Python 3.11, dspy 3.1.3)
```

> **Note:** There is also a `wn-project/venv/` at the repo root — that is for other tools and does **not** have dspy installed. Always use the `.venv` above.

Installed packages: `dspy-ai 3.1.3`, `mlflow 3.10.1`, `pyyaml 6.0.3`, `wn 1.0.0`.

### 2. API Keys

Set at least one provider's API key in `arabic-wordnet-v4/.env` (auto-loaded by `config.py`):

```bash
# Any one of these is sufficient
ANTHROPIC_API_KEY=sk-ant-...
GEM_API_KEY=AIza...              # auto-normalized to GEMINI_API_KEY
OPENAI_API_KEY=sk-...
MOONSHOT_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...     # free stealth models (hunter-alpha, healer-alpha)
CEREBRAS_API_KEY=csk-...         # free tier (cerebras-qwen, cerebras-gpt, cerebras-llama)
```

### 3. Deno Setup

DSPy's RLM uses Deno + Pyodide WASM sandbox. Install Deno:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

On first run, Deno will download the Pyodide runtime (~40 MB, cached afterwards).

## How to Run

**Important:** All commands must be run from the `linguistic_review_guide/` directory using the `.venv` Python. There are two ways:

### Option A: Activate the venv (interactive shells)

```bash
cd /Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/experiments/linguistic_review_guide
source /Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/.venv/bin/activate
python -m dspy_review.pipeline awn4-13927849-n.evidence.yaml
```

### Option B: Use the venv Python directly (recommended for scripts / background tasks)

This avoids `source activate` issues in non-interactive shells, background jobs, and CI:

```bash
cd /Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/experiments/linguistic_review_guide

# Use the full path to the .venv python
/Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/.venv/bin/python \
    -m dspy_review.pipeline awn4-13927849-n.evidence.yaml
```

> **Why does the directory matter?** The pipeline resolves evidence files relative to `linguistic_review_guide/evidence/`. The CLI argument is just the filename (e.g., `awn4-13927849-n.evidence.yaml`), not a path — the pipeline prepends the evidence directory automatically.

### Quick Reference (copy-paste ready)

```bash
# ── Variables (set once) ──
VENV=/Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/.venv/bin/python
WORKDIR=/Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/experiments/linguistic_review_guide

# ── Single synset ──
cd "$WORKDIR" && $VENV -m dspy_review.pipeline awn4-13927849-n.evidence.yaml

# ── With model selection ──
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --model healer-alpha awn4-05934990-n.evidence.yaml

# ── With main + sub model ──
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --model hunter-alpha --sub-model healer-alpha awn4-05934990-n.evidence.yaml

# ── OpenRouter with reasoning disabled (fastest) ──
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --model healer-alpha --reasoning-effort none awn4-05934990-n.evidence.yaml

# ── All synsets ──
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --all

# ── Dry run ──
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --all --dry-run

# ── Cost estimate ──
cd "$WORKDIR" && $VENV -m dspy_review.estimate_cost --evidence-dir evidence -n 5 --model healer-alpha
```

### With MLflow Tracing

```bash
# Start MLflow server in a separate terminal
mlflow server --port 5000

# Run with tracing enabled
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --mlflow awn4-13927849-n.evidence.yaml
```

## Model Aliases

Use short aliases instead of full litellm model IDs:

| Alias | Resolves To | Price |
|-------|------------|-------|
| `hunter-alpha` | `openrouter/openrouter/hunter-alpha` | Free |
| `healer-alpha` | `openrouter/openrouter/healer-alpha` | Free |
| `gemini-3.1-flash-lite` | `gemini/gemini-3.1-flash-lite-preview` | $0.25/$1.50 per 1M |
| `gemini-3-flash` | `gemini/gemini-3-flash-preview` | $0.15/$0.60 per 1M |
| `gemini-3.1-pro` | `gemini/gemini-3.1-pro-preview` | $1.25/$10.00 per 1M |
| `gemini-2.5-flash` | `gemini/gemini-2.5-flash-preview-05-20` | $0.15/$0.60 per 1M |
| `gemini-2.5-pro` | `gemini/gemini-2.5-pro-preview-05-06` | $1.25/$10.00 per 1M |
| `claude-sonnet` | `anthropic/claude-sonnet-4-5-20250929` | — |
| `claude-haiku` | `anthropic/claude-haiku-4-5-20251001` | — |
| `claude-opus` | `anthropic/claude-opus-4-5-20250929` | — |
| `gpt-4o` | `openai/gpt-4o` | — |
| `gpt-4o-mini` | `openai/gpt-4o-mini` | — |
| `kimi-k2` | `moonshot/kimi-k2-0905-preview` | — |
| `cerebras-qwen` | `cerebras/qwen-3-235b-a22b-instruct-2507` | Free |
| `cerebras-gpt` | `cerebras/gpt-oss-120b` | Free |
| `cerebras-llama` | `cerebras/llama3.1-8b` | Free |

You can also pass any full litellm model ID directly (e.g., `--model openai/o3-mini`).

### OpenRouter Stealth Models

Hunter Alpha and Healer Alpha are free stealth models on OpenRouter:

| Feature | Hunter Alpha | Healer Alpha |
|---------|-------------|--------------|
| Best for | RLM steps (agentic, tool use) | CoT steps (fast throughput) |
| Context | 1M tokens | 262K tokens |
| Throughput | ~39 tok/s | ~70 tok/s |
| Price | Free | Free |

**Reasoning control** — OpenRouter models support a `--reasoning-effort` flag to control internal chain-of-thought reasoning tokens. Disabling reasoning speeds up inference:

```bash
# Disable reasoning (fastest)
--reasoning-effort none

# Other levels: minimal, low, medium, high, xhigh
--reasoning-effort low
```

### Cerebras (Free Tier)

Cerebras offers free API access with extremely fast inference (~1,400-2,600 tok/s) via their Wafer-Scale Engine:

| Alias | Model | Params | Speed |
|-------|-------|--------|-------|
| `cerebras-qwen` | Qwen 3 235B A22B | 235B (22B active) | ~1,400 tok/s |
| `cerebras-gpt` | GPT-OSS 120B | 120B | — |
| `cerebras-llama` | Llama 3.1 8B | 8B | ~1,800 tok/s |

**Limitations:**
- **8K context window** — the pipeline auto-caps `max_tokens` to 4096 to leave room for input. This means RLM steps with large evidence files may hit context limits.
- **Rate limits:** 30 RPM, 1M tokens/day (org-level)
- **Best for:** CoT steps (3, 4, 5) on smaller synsets; not ideal for RLM steps that need large context

```bash
# Use Qwen 235B (strongest Cerebras model)
cd "$WORKDIR" && $VENV -m dspy_review.pipeline --model cerebras-qwen awn4-13927849-n.evidence.yaml
```

## Pipeline Architecture

The 6-step algorithm is decomposed into specialized DSPy modules:

| Step | Module Type | Description |
|------|-------------|-------------|
| 0 | **RLM** | Evidence classification — scans full evidence YAML via tools |
| 0.5 | **RLM** | Lemma generation — generates candidate lemmas from evidence |
| 1 | CoT | Lemma validation — works on Step 0's compact output |
| 3 | CoT | Definition processing — reasoning-heavy |
| 4 | CoT | Relations check — reasoning-heavy |
| 5 | CoT | Enrichment & cultural fit |

**RLM** steps get sandboxed tool access (evidence exploration). **CoT** steps receive pre-extracted context from prior steps.

## Output

For each reviewed synset, files are written to `output/reviews_level4/`:

- `{synset_id}.review.yaml` — Compiled review (all 6 steps merged)

On errors:
- `{synset_id}.error.txt` — Traceback for failed reviews

## Module Structure

```
dspy_review/
  __init__.py          # package marker
  pipeline.py          # main entry point — 6-step decomposed pipeline
  signatures.py        # 6 DSPy Signature classes (Step0-Step5)
  extractors.py        # inter-step data extraction helpers
  config.py            # multi-provider LM configuration + .env loading
  shared.py            # evidence loading, YAML helpers, path constants
  tracing.py           # RLMProgressCallback + MLflow setup
  estimate_cost.py     # token usage sampling + cost extrapolation
  archive/
    level1_single_rlm.py  # earlier monolithic single-RLM approach
```

## CLI Reference

```
python -m dspy_review.pipeline [OPTIONS] [EVIDENCE_FILE]

Positional:
  EVIDENCE_FILE          Evidence file name (e.g., awn4-13927849-n.evidence.yaml)
                         NOTE: just the filename, not the path — the pipeline
                         looks in the evidence/ directory automatically.

File selection:
  --all                  Process all evidence files in the evidence directory
  --evidence-dir DIR     Directory with .evidence.yaml files
  --output-dir DIR       Output directory for review YAML files
  --dry-run              Show what would be processed without running

Model configuration:
  --model, -m MODEL      Main LLM (alias or full litellm ID; default: gemini-3.1-flash-lite)
  --sub-model MODEL      Sub-LLM for llm_query() calls (default: auto from provider)
  --temperature FLOAT    Sampling temperature (default: 0.7)
  --max-tokens INT       Max tokens in response (default: 20000)
  --reasoning-effort     OpenRouter reasoning control: none, minimal, low, medium, high, xhigh
                         Use "none" to disable reasoning for maximum speed.

RLM parameters:
  --max-iterations INT   Max REPL loop iterations (default: 30)
  --max-llm-calls INT    Max llm_query/llm_query_batched calls (default: 80)
  --quiet                Suppress verbose REPL output

MLflow tracing:
  --mlflow               Enable MLflow tracing (requires mlflow>=2.18.0)
  --mlflow-uri URI       MLflow tracking URI (default: http://127.0.0.1:5000)
  --experiment NAME      MLflow experiment name (default: AWN-LinguisticReview)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'dspy'` | You're using the wrong Python. Use `.venv/bin/python`, not `venv/bin/python`. |
| `Error: evidence/evidence/file.yaml not found` | You passed `evidence/filename.yaml` — just pass `filename.yaml` (no directory prefix). |
| `source activate` not working in scripts | Use the full Python path directly: `/path/to/arabic-wordnet-v4/.venv/bin/python` |
| `API key not found for openrouter` | Add `OPENROUTER_API_KEY=sk-or-...` to `arabic-wordnet-v4/.env` |
| PyYAML not available in RLM sandbox | Known limitation — the Deno/Pyodide WASM sandbox doesn't have PyYAML. The model constructs YAML manually. |
