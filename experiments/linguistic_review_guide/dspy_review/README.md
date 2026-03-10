# dspy_review — DSPy RLM Linguistic Reviewer for AWN4

Automated linguistic review of Arabic WordNet v4 synsets using DSPy's RLM (Recursive Language Model). An RLM receives dictionary evidence from 107 Arabic dictionaries and follows a 6-step algorithm to validate lemmas, author definitions, check relations, and enrich metadata.

## Prerequisites

- Python 3.11+
- [Deno](https://deno.com/) (required by DSPy's RLM for its sandboxed REPL)

## Environment Setup

### 1. Activate the Virtual Environment

The project uses a shared virtual environment at `arabic-wordnet-v4/.venv` (Python 3.11) with all dependencies pre-installed:

```bash
source /Users/salahmac/Desktop/MLProjects/wn-project/arabic-wordnet-v4/.venv/bin/activate
```

Installed packages: `dspy-ai 3.1.3`, `mlflow 3.10.1`, `pyyaml 6.0.3`, `wn 1.0.0`.

If you need to reinstall:

```bash
pip install dspy-ai pyyaml

# Optional: MLflow tracing
pip install mlflow>=2.18.0
```

### 2. API Keys

Set at least one provider's API key. The system auto-detects which provider to use based on available keys (priority: Anthropic > Gemini > OpenAI > Moonshot).

The `.env` file is at `arabic-wordnet-v4/.env` and is auto-loaded by `config.py`:

```
arabic-wordnet-v4/.env          <-- API keys live here
```

```bash
# Any one of these is sufficient
ANTHROPIC_API_KEY=sk-ant-...
GEM_API_KEY=AIza...          # auto-normalized to GEMINI_API_KEY
OPENAI_API_KEY=sk-...
MOONSHOT_API_KEY=sk-...
```

You can also export keys directly in your shell:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export GEMINI_API_KEY=AIza...
# or
export OPENAI_API_KEY=sk-...
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
# Auto-detect model from available API keys
python -m dspy_review.level1_single_rlm awn4-13927849-n.evidence.yaml

# Specify model explicitly
python -m dspy_review.level1_single_rlm --model claude-sonnet awn4-13927849-n.evidence.yaml
python -m dspy_review.level1_single_rlm --model gemini-2.5-flash awn4-13927849-n.evidence.yaml
```

### Review All Synsets

```bash
python -m dspy_review.level1_single_rlm --all
```

### Dry Run (list files without processing)

```bash
python -m dspy_review.level1_single_rlm --all --dry-run
```

### With MLflow Tracing

```bash
# Start MLflow server in a separate terminal
mlflow server --port 5000

# Run with tracing enabled — every LM call, RLM iteration, and sub-query is captured
python -m dspy_review.level1_single_rlm --mlflow awn4-13927849-n.evidence.yaml

# Custom tracking URI and experiment name
python -m dspy_review.level1_single_rlm --mlflow --mlflow-uri http://localhost:5000 --experiment my-experiment --all
```

Then open http://localhost:5000 to view traces.

## Model Aliases

Use short aliases instead of full litellm model IDs:

| Alias | Resolves To |
|-------|------------|
| `claude-sonnet` | `anthropic/claude-sonnet-4-5-20250929` |
| `claude-haiku` | `anthropic/claude-haiku-4-5-20251001` |
| `claude-opus` | `anthropic/claude-opus-4-5-20250929` |
| `gemini-2.5-flash` | `gemini/gemini-2.5-flash-preview-05-20` |
| `gemini-2.5-pro` | `gemini/gemini-2.5-pro-preview-05-06` |
| `gemini-2.0-flash` | `gemini/gemini-2.0-flash` |
| `gemini-3.1-pro` | `gemini/gemini-3.1-pro-preview` |
| `gemini-3-flash` | `gemini/gemini-3-flash-preview` |
| `gpt-4o` | `openai/gpt-4o` |
| `gpt-4o-mini` | `openai/gpt-4o-mini` |
| `kimi-k2` | `moonshot/kimi-k2-0905-preview` |

You can also pass any full litellm model ID directly (e.g., `--model openai/o3-mini`).

### Sub-Model Auto-Selection

The RLM uses a cheaper sub-model for `llm_query()` / `llm_query_batched()` calls. When `--sub-model` is not specified, the system auto-selects based on the main model's provider:

| Main Model Provider | Auto-Selected Sub-Model |
|--------------------|------------------------|
| Anthropic | `claude-haiku` |
| Gemini | `gemini-2.0-flash` |
| OpenAI | `gpt-4o-mini` |
| Moonshot | `kimi-k2` |

Override with `--sub-model`:

```bash
python -m dspy_review.level1_single_rlm --model claude-opus --sub-model claude-sonnet awn4-13927849-n.evidence.yaml
```

## CLI Reference

```
python -m dspy_review.level1_single_rlm [OPTIONS] [EVIDENCE_FILE]

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

## Output

For each reviewed synset, two files are written to `--output-dir` (default: `reviews_level1/`):

- `{synset_id}.review.yaml` — The complete review YAML conforming to `output_step0.yaml`
- `{synset_id}.trajectory.json` — Full RLM REPL trajectory for debugging

On errors:

- `{synset_id}.error.txt` — Traceback for failed reviews

## Module Structure

```
dspy_review/
  __init__.py            # package marker
  config.py              # multi-provider LM configuration + .env loading
  tracing.py             # MLflow setup (3 lines: set_tracking_uri, set_experiment, autolog)
  shared.py              # evidence loading, YAML helpers, path constants
  level1_single_rlm.py   # Level 1: single RLM end-to-end reviewer
```

## How MLflow Tracing Works

DSPy has a built-in callback system. When you call `mlflow.dspy.autolog()`, MLflow registers itself as a DSPy callback. From that point, **every** `dspy.LM` call, `dspy.Module.forward()`, RLM iteration, and tool call is automatically captured as nested OpenTelemetry spans — zero manual instrumentation needed.

```python
import mlflow
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("AWN-LinguisticReview")
mlflow.dspy.autolog()  # this single line enables full tracing
```
