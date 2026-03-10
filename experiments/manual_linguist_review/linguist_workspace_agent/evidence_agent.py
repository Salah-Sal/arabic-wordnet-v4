"""
evidence_agent.py — DSPy RLM Agent for Arabic WordNet Evidence Collection.

A dspy.Module that uses an RLM to iteratively query a 760K-entry Arabic
dictionary database and the wn library, producing evidence artifacts
for AWN4 synsets.

Usage:
    from evidence_agent import EvidenceCollectionAgent

    agent = EvidenceCollectionAgent(db_path="data/arabic_dict.db")
    result = agent("awn4-05162506-n")
    print(result.evidence_json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import dspy

# Import from existing pipeline
_PIPELINE_DIR = str(Path(__file__).resolve().parent.parent / "linguist_workspace" / "tools")
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from collect_evidence import DictDB, WNBridge
from agent_tools import build_tools
from guidelines import get_evidence_guidelines


class EvidenceCollectionAgent(dspy.Module):
    """RLM agent that collects dictionary evidence for AWN4 synsets.

    The agent iteratively writes Python code in a sandboxed REPL,
    calling host-side tools to query the Arabic dictionary database
    and the wn library. Unlike the automated pipeline, the agent
    can reason about intermediate results and adapt its strategy.
    """

    def __init__(
        self,
        db_path: str = "data/arabic_dict.db",
        max_iterations: int = 40,
        max_llm_calls: int = 30,
        max_output_chars: int = 200_000,
        verbose: bool = False,
        sub_lm: Optional[dspy.LM] = None,
    ):
        super().__init__()

        # Resolve DB path relative to this file if not absolute
        db_resolved = Path(db_path)
        if not db_resolved.is_absolute():
            db_resolved = Path(__file__).resolve().parent / db_path

        self.db = DictDB(str(db_resolved))
        self.wn_bridge = WNBridge()
        self.guidelines = get_evidence_guidelines()

        tools = build_tools(self.db, self.wn_bridge)

        self.rlm = dspy.RLM(
            signature="synset_id: str, synset_data: str, guidelines: str -> evidence_json: str",
            max_iterations=max_iterations,
            max_llm_calls=max_llm_calls,
            max_output_chars=max_output_chars,
            verbose=verbose,
            tools=tools,
            sub_lm=sub_lm,
        )

    def forward(self, synset_id: str) -> dspy.Prediction:
        """Collect evidence for a single synset.

        Args:
            synset_id: AWN4 synset ID (e.g., "awn4-05162506-n")

        Returns:
            Prediction with evidence_json field (JSON string of the artifact)
        """
        # Pre-fetch synset data on host side (wn is not available in sandbox)
        synset_data = self.wn_bridge.get_synset_data(synset_id)
        synset_json = json.dumps(synset_data, ensure_ascii=False)

        return self.rlm(
            synset_id=synset_id,
            synset_data=synset_json,
            guidelines=self.guidelines,
        )

    def close(self):
        """Close database connection."""
        self.db.close()
