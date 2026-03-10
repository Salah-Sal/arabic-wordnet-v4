"""
config.py — LLM configuration for the DSPy linguistic review agents.

Supports Anthropic, Google Gemini, OpenAI, and Moonshot models via litellm.
API keys loaded from environment or .env file.

Reuses the same multi-provider pattern as linguist_workspace_agent/config.py.
"""
import os
from pathlib import Path
from typing import Optional

import dspy


# ═══════════════════════════════════════════════════════════════
# .env loading
# ═══════════════════════════════════════════════════════════════

def _load_env():
    """Load .env from this directory or ancestor directories."""
    for env_path in [
        Path(__file__).parent / ".env",
        Path(__file__).resolve().parent.parent.parent.parent.parent / ".env",
    ]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and value:
                            os.environ.setdefault(key, value)

_load_env()

# Normalize key name: GEM_API_KEY -> GEMINI_API_KEY (litellm expects GEMINI_API_KEY)
if os.environ.get("GEM_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GEM_API_KEY"]


# ═══════════════════════════════════════════════════════════════
# Model aliases and providers
# ═══════════════════════════════════════════════════════════════

MODEL_ALIASES = {
    # Anthropic
    "claude-sonnet": "anthropic/claude-sonnet-4-5-20250929",
    "claude-haiku": "anthropic/claude-haiku-4-5-20251001",
    "claude-opus": "anthropic/claude-opus-4-5-20250929",
    # Google Gemini
    "gemini-3.1-pro": "gemini/gemini-3.1-pro-preview",
    "gemini-3-flash": "gemini/gemini-3-flash-preview",
    "gemini-3.1-flash-lite": "gemini/gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash": "gemini/gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro": "gemini/gemini-2.5-pro-preview-05-06",
    "gemini-2.0-flash": "gemini/gemini-2.0-flash",
    # OpenAI
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    # Moonshot
    "kimi-k2": "moonshot/kimi-k2-0905-preview",
}

PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
}

# When the user picks a main model but not a sub-model, auto-select a cheaper one
SUB_MODEL_DEFAULTS = {
    "anthropic": "anthropic/claude-haiku-4-5-20251001",
    "gemini": "gemini/gemini-3.1-flash-lite-preview",
    "openai": "openai/gpt-4o-mini",
    "moonshot": "moonshot/kimi-k2-0905-preview",
}


# ═══════════════════════════════════════════════════════════════
# Resolution helpers
# ═══════════════════════════════════════════════════════════════

def resolve_model(model_name: str) -> str:
    """Resolve a friendly alias to a full litellm model ID."""
    return MODEL_ALIASES.get(model_name, model_name)


def get_provider(model_name: str) -> str:
    """Extract the provider from a model name."""
    resolved = resolve_model(model_name)
    if "/" in resolved:
        return resolved.split("/")[0]
    lower = resolved.lower()
    if "claude" in lower:
        return "anthropic"
    if "gemini" in lower:
        return "gemini"
    if "gpt" in lower or lower.startswith("o1") or lower.startswith("o3"):
        return "openai"
    if "moonshot" in lower or "kimi" in lower:
        return "moonshot"
    return "unknown"


def auto_select_sub_model(main_model: str) -> str:
    """Pick a cheaper sub-model from the same provider as main_model."""
    provider = get_provider(main_model)
    return SUB_MODEL_DEFAULTS.get(provider, "openai/gpt-4o-mini")


# ═══════════════════════════════════════════════════════════════
# Default model — change this to switch the default
# ═══════════════════════════════════════════════════════════════

DEFAULT_MODEL = "gemini-3.1-flash-lite"


# ═══════════════════════════════════════════════════════════════
# Core configuration
# ═══════════════════════════════════════════════════════════════

def configure_lm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 20000,
) -> dspy.LM:
    """Configure and return the main dspy.LM.

    Uses DEFAULT_MODEL when no --model is passed via CLI.
    """
    if model is None:
        model = DEFAULT_MODEL

    full_model = resolve_model(model)
    provider = get_provider(full_model)
    env_var = PROVIDER_ENV_VARS.get(provider)
    if env_var and not os.environ.get(env_var):
        raise ValueError(f"API key not found for {provider}. Set {env_var}.")

    lm = dspy.LM(full_model, temperature=temperature, max_tokens=max_tokens)
    dspy.configure(lm=lm)
    print(f"Configured LLM: {full_model}")
    return lm


def make_sub_lm(
    sub_model: Optional[str] = None,
    main_model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 8000,
) -> dspy.LM:
    """Create a sub-LM for llm_query() calls (NOT set as global default).

    If sub_model is None, auto-selects a cheaper model from the same provider.
    """
    if sub_model is None:
        resolved = auto_select_sub_model(main_model) if main_model else "openai/gpt-4o-mini"
    else:
        resolved = resolve_model(sub_model)

    return dspy.LM(resolved, temperature=temperature, max_tokens=max_tokens)


# ═══════════════════════════════════════════════════════════════
# CLI argument helpers
# ═══════════════════════════════════════════════════════════════

def add_model_args(parser):
    """Add --model, --temperature, --max-tokens to an argparse parser."""
    parser.add_argument(
        "--model", "-m", type=str, default=None,
        help=f"Main LLM model (default: {DEFAULT_MODEL}). Alias or full litellm ID."
    )
    parser.add_argument(
        "--sub-model", type=str, default=None,
        help="Sub-LLM for llm_query() calls (default: auto-select cheaper model from same provider)"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature (default: 0.7)"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=20000,
        help="Max tokens in response (default: 20000)"
    )
    return parser
