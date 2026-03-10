"""
tracing.py — MLflow tracing for DSPy linguistic review.

DSPy has built-in MLflow support via its callback system. Calling
mlflow.dspy.autolog() hooks into every dspy.LM call, Module.forward(),
tool call, and RLM iteration automatically — zero manual instrumentation.

Usage:
    from dspy_review.tracing import setup_mlflow, add_mlflow_args
    setup_mlflow()  # 3 lines under the hood, that's it
"""
from __future__ import annotations

try:
    import mlflow
    import mlflow.dspy
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


def setup_mlflow(
    tracking_uri: str = "http://127.0.0.1:5000",
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
    parser.add_argument("--mlflow-uri", type=str, default="http://127.0.0.1:5000",
                        help="MLflow tracking URI (default: http://127.0.0.1:5000)")
    parser.add_argument("--experiment", type=str, default="AWN-LinguisticReview",
                        help="MLflow experiment name (default: AWN-LinguisticReview)")
    return parser
