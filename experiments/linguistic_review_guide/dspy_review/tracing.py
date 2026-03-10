"""
tracing.py — Observability for DSPy linguistic review.

Contains:
- RLMProgressCallback: real-time console progress for RLM iterations and sub-LM calls
- MLflow setup: optional tracing via DSPy's built-in callback system

Usage:
    from dspy_review.tracing import RLMProgressCallback, setup_mlflow, add_mlflow_args
"""
from __future__ import annotations

import time

import dspy
from dspy.utils.callback import BaseCallback

try:
    import mlflow
    import mlflow.dspy
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


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
            usage = outputs.get("usage", {}) if isinstance(outputs, dict) else {}
            tokens = ""
            if usage:
                inp = usage.get("prompt_tokens", 0)
                out = usage.get("completion_tokens", 0)
                tokens = f" ({inp}+{out} tokens)"
            print(f"  [LM] Done in {dur}{tokens}")


# ═══════════════════════════════════════════════════════════════
# MLflow tracing
# ═══════════════════════════════════════════════════════════════

def setup_mlflow(
    tracking_uri: str = "http://127.0.0.1:8080",
    experiment_name: str = "AWN-LinguisticReview",
) -> bool:
    """Enable MLflow tracing for all DSPy calls. Returns False if mlflow is missing."""
    if not MLFLOW_AVAILABLE:
        print("Warning: mlflow not installed. Install with: pip install mlflow>=2.18.0")
        return False

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    mlflow.dspy.autolog()
    print(f"MLflow tracing enabled: {tracking_uri} (experiment: {experiment_name})")
    return True


def add_mlflow_args(parser):
    """Add --mlflow, --mlflow-uri, --experiment to argparse."""
    parser.add_argument("--mlflow", action="store_true",
                        help="Enable MLflow tracing (requires mlflow>=2.18.0)")
    parser.add_argument("--mlflow-uri", type=str, default="http://127.0.0.1:8080",
                        help="MLflow tracking URI (default: http://127.0.0.1:8080)")
    parser.add_argument("--experiment", type=str, default="AWN-LinguisticReview",
                        help="MLflow experiment name (default: AWN-LinguisticReview)")
    return parser
