# dspy_review — DSPy Linguistic Reviewer for AWN4

Automated linguistic review of Arabic WordNet v4 synsets using DSPy. A 6-step pipeline of specialized modules (2 RLMs + 4 ChainOfThoughts), each scoped to its relevant algorithm section, schema section, and evidence subset from 107 Arabic dictionaries.

## Prerequisites

- Python 3.11+
- [Deno](https://deno.com/) (required by DSPy's RLM for its sandboxed REPL)

## Environment Setup

### 1. Activate the Virtual Environment

```bash
source /Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/.venv/bin/activate
```

Installed packages: `dspy-ai 3.1.3`, `mlflow 3.10.1`, `pyyaml 6.0.3`, `wn 1.0.0`.

### 2. API Keys

Set at least one provider's API key. The system auto-detects which provider to use based on available keys (priority: Anthropic > Gemini > OpenAI > Moonshot).

The `.env` file is at `arabic-wordnet-v4/.env` and is auto-loaded by `config.py`:

```bash
# Any one of these is sufficient
ANTHROPIC_API_KEY=sk-ant-...
GEM_API_KEY=AIza...          # auto-normalized to GEMINI_API_KEY
OPENAI_API_KEY=sk-...
MOONSHOT_API_KEY=sk-...
```

### 3. Deno Setup

DSPy's RLM uses Deno + Pyodide WASM sandbox. Install Deno:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

On first run, Deno will download the Pyodide runtime (~40 MB, cached afterwards).

## Usage

Activate the venv and run from the `linguistic_review_guide/` directory:

```bash
source /Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/.venv/bin/activate
cd arabic-wordnet-v4/experiments/linguistic_review_guide
```

### Review a Single Synset

```bash
python -m dspy_review.pipeline awn4-13927849-n.evidence.yaml

# Specify model explicitly
python -m dspy_review.pipeline --model gemini-3.1-flash-lite awn4-13927849-n.evidence.yaml

# Different main and sub models
python -m dspy_review.pipeline --model gemini-3.1-pro --sub-model gemini-3.1-flash-lite awn4-13927849-n.evidence.yaml
```

### Review All Synsets

```bash
python -m dspy_review.pipeline --all
```

### Dry Run (list files without processing)

```bash
python -m dspy_review.pipeline --all --dry-run
```

### With MLflow Tracing

```bash
# Start MLflow server in a separate terminal
mlflow server --port 5000

# Run with tracing enabled
python -m dspy_review.pipeline --mlflow awn4-13927849-n.evidence.yaml
```

## Model Aliases

Use short aliases instead of full litellm model IDs:

| Alias | Resolves To |
|-------|------------|
| `claude-sonnet` | `anthropic/claude-sonnet-4-5-20250929` |
| `claude-haiku` | `anthropic/claude-haiku-4-5-20251001` |
| `claude-opus` | `anthropic/claude-opus-4-5-20250929` |
| `gemini-2.5-flash` | `gemini/gemini-2.5-flash-preview-05-20` |
| `gemini-2.5-pro` | `gemini/gemini-2.5-pro-preview-05-06` |
| `gemini-3.1-flash-lite` | `gemini/gemini-3.1-flash-lite-preview` |
| `gemini-3.1-pro` | `gemini/gemini-3.1-pro-preview` |
| `gpt-4o` | `openai/gpt-4o` |
| `gpt-4o-mini` | `openai/gpt-4o-mini` |
| `kimi-k2` | `moonshot/kimi-k2-0905-preview` |

You can also pass any full litellm model ID directly (e.g., `--model openai/o3-mini`).

## Pipeline Architecture

The 6-step algorithm is decomposed into specialized DSPy modules:

| Step | Module Type | Description |
|------|-------------|-------------|
| 0 | **RLM** | Evidence classification — scans full evidence YAML via tools |
| 1 | CoT | Lemma validation — works on Step 0's compact output |
| 2 | **RLM** | Missing lemmas — scans per_synset + reverse lookups via tools |
| 3 | CoT | Definition processing — reasoning-heavy |
| 4 | CoT | Relations check — reasoning-heavy |
| 5 | CoT | Enrichment & cultural fit |

**RLM** steps get sandboxed tool access (evidence exploration). **CoT** steps receive pre-extracted context from prior steps.

## Output

For each reviewed synset, files are written to `reviews_level4/`:

- `{synset_id}.review.yaml` — Compiled review (all 6 steps merged)
- `{synset_id}.step0.yaml` through `.step5.yaml` — Per-step outputs for debugging
- `{synset_id}.timings.json` — Per-step timing data

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
  archive/
    level1_single_rlm.py  # earlier monolithic single-RLM approach
```

## CLI Reference

```
python -m dspy_review.pipeline [OPTIONS] [EVIDENCE_FILE]

Positional:
  EVIDENCE_FILE          Evidence file name (e.g., awn4-13927849-n.evidence.yaml)

File selection:
  --all                  Process all evidence files in the evidence directory
  --evidence-dir DIR     Directory with .evidence.yaml files
  --output-dir DIR       Output directory for review YAML files
  --dry-run              Show what would be processed without running

Model configuration:
  --model, -m MODEL      Main LLM (alias or full litellm ID; default: auto-detect)
  --sub-model MODEL      Sub-LLM for llm_query() calls (default: auto from provider)
  --temperature FLOAT    Sampling temperature (default: 0.7)
  --max-tokens INT       Max tokens in response (default: 20000)

RLM parameters:
  --max-iterations INT   Max REPL loop iterations (default: 30)
  --max-llm-calls INT    Max llm_query/llm_query_batched calls (default: 80)
  --quiet                Suppress verbose REPL output

MLflow tracing:
  --mlflow               Enable MLflow tracing (requires mlflow>=2.18.0)
  --mlflow-uri URI       MLflow tracking URI (default: http://127.0.0.1:5000)
  --experiment NAME      MLflow experiment name (default: AWN-LinguisticReview)
```
