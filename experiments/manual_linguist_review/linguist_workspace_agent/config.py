"""
config.py — LLM configuration for the RLM evidence collection agent.

Supports Anthropic, Google Gemini, OpenAI, and Moonshot models via litellm.
API keys loaded from environment or .env file.
"""
import os
from pathlib import Path
from typing import Optional

import dspy


# Load .env from this directory or project root
def _load_env():
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


def resolve_model(model_name: str) -> str:
    return MODEL_ALIASES.get(model_name, model_name)


def get_provider(model_name: str) -> str:
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


def configure_lm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 20000,
) -> dspy.LM:
    if model is None:
        for provider in ["anthropic", "gemini", "openai", "moonshot"]:
            env_var = PROVIDER_ENV_VARS.get(provider)
            if env_var and os.environ.get(env_var):
                defaults = {"anthropic": "claude-sonnet", "gemini": "gemini-2.0-flash",
                            "openai": "gpt-4o-mini", "moonshot": "kimi-k2"}
                model = defaults[provider]
                break
        if model is None:
            raise ValueError(f"No API keys found. Set one of: {', '.join(PROVIDER_ENV_VARS.values())}")

    full_model = resolve_model(model)
    provider = get_provider(full_model)
    env_var = PROVIDER_ENV_VARS.get(provider)
    if env_var and not os.environ.get(env_var):
        raise ValueError(f"API key not found for {provider}. Set {env_var}.")

    lm = dspy.LM(full_model, temperature=temperature, max_tokens=max_tokens)
    dspy.configure(lm=lm)
    print(f"Configured LLM: {full_model}")
    return lm


def add_model_args(parser):
    parser.add_argument("--model", "-m", type=str, default=None,
                        help="LLM model (alias or full litellm ID)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Sampling temperature (default: 0.7)")
    parser.add_argument("--max-tokens", type=int, default=20000,
                        help="Max tokens in response (default: 20000)")
    return parser
