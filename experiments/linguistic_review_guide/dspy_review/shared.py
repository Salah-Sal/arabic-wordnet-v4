#!/usr/bin/env python3
"""Shared utilities for DSPy review implementations.

Reuses evidence processing from assemble_prompts_v2.py and provides
common LM configuration, evidence loading, and YAML helpers.

LM configuration is in config.py; MLflow tracing is in tracing.py.
"""
from __future__ import annotations

import gzip
import os
import sys
from pathlib import Path

import yaml

# Add legacy dir so we can import assemble_prompts_v2's processing logic
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "legacy"))

from assemble_prompts_v2 import (
    ArabicDumper,
    process_evidence,
    extract_synset_info,
)

# Re-export config utilities so callers can do: from dspy_review.shared import configure_lm
from dspy_review.config import configure_lm, resolve_model, make_sub_lm, add_model_args  # noqa: F401

# ── Paths ──

EVIDENCE_DIR = PROJECT_DIR / "evidence"
ALGORITHM_PATH = PROJECT_DIR / "spec" / "draft_api.md"
OUTPUT_SCHEMA_PATH = PROJECT_DIR / "spec" / "output_step0.yaml"

# ── YAML loader (prefer C extension) ──

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader


def load_text(path: Path | str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_evidence(path: Path | str) -> dict:
    """Read evidence file — handles both .yaml and .yaml.gz."""
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return yaml.load(f, Loader=_Loader)
    else:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.load(f, Loader=_Loader)


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        Dumper=ArabicDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=200,
    )


def list_evidence_files(evidence_dir: Path | str | None = None) -> list[Path]:
    """List all .evidence.yaml files in the evidence directory."""
    d = Path(evidence_dir) if evidence_dir else EVIDENCE_DIR
    files = sorted(d.glob("*.evidence.yaml")) + sorted(d.glob("*.evidence.yaml.gz"))
    return files


def extract_synset_id(filename: str) -> str:
    return filename.replace(".evidence.yaml.gz", "").replace(".evidence.yaml", "")


def load_synset_data(evidence_path: Path | str) -> dict:
    """Load and return raw evidence data + derived components.

    Returns dict with keys:
        raw: the raw parsed YAML dict
        synset_info: compact YAML string of synset metadata
        evidence_yaml: processed/slimmed evidence as YAML string
    """
    raw = read_evidence(evidence_path)
    synset_info = extract_synset_info(raw)
    processed = process_evidence(raw)
    evidence_yaml = dump_yaml(processed)
    return {
        "raw": raw,
        "synset_info": synset_info,
        "evidence_yaml": evidence_yaml,
    }
