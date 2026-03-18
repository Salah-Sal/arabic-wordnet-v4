"""Apply linguistic review actions to AWN4 via v1.0.0 WordnetEditor.

Replaces the legacy apply_reviews.py (which targets the broken wn_editor API)
with a new applicator built on wordnet_editor.WordnetEditor v1.0.0.

Usage:
    python apply_reviews_v2.py \
        --reviews-dir output/reviews_claude_db output/reviews_gemini_db \
        --db ../../wn-editor-extended/data/awn4_experiment.db \
        --lexicon awn4 \
        [--dry-run] [--no-copy] \
        [--manifest manifest.json] \
        [--validate] [--export output/awn4_reviewed.xml]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# Add wn-editor-extended to path so we can import wordnet_editor
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WN_EDITOR_SRC = _PROJECT_ROOT / "wn-editor-extended" / "src"
if str(_WN_EDITOR_SRC) not in sys.path:
    sys.path.insert(0, str(_WN_EDITOR_SRC))

from wordnet_editor import (
    WordnetEditor,
    EntityNotFoundError,
    DuplicateEntityError,
    ValidationError,
    RelationError,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Arabic command → English command normalization map.
# Only 1 of 675 gemini YAML files uses Arabic commands; retained as safety net.
ARABIC_COMMAND_MAP: dict[str, str] = {
    "أكّد صلاحية اللمّة": "_noop",
    "احذف ارتباط اللمّة بالمجموعة": "remove_sense",
    "أضف لمّة جديدة إلى المجموعة": "create_entry_and_add_sense",
    "عدّل نص التعريف": "update_definition",
    "تحديث نص التعريف": "update_definition",
    "ألّف تعريفاً جديداً": "add_definition",
    "أقرّ صحة العلاقات": "_noop",
    "أقرّ صحة العلاقة التعميمية": "_noop",
    "أضف علاقة دلالية": "add_synset_relation",
    "سجّل ملاحظة دلالية": "set_metadata",
    "سجّل ملاحظة اصطلاحية": "set_metadata",
    "صعّد للمراجع البشري": "escalate",
    "مراجعة بشرية": "escalate",
    "اقترح تغيير الأعم المباشر": "escalate",
}

NOOP_COMMANDS = {"_noop", "retain_definition"}
ESCALATION_COMMANDS = {"escalate"}

# Relation type normalization (review YAMLs use non-standard names)
RELATION_TYPE_MAP: dict[str, str] = {
    "is-a": "hypernym",
    "has-a": "holo_member",
    "antonym": "antonym",  # identity mapping — keeps it explicit
}

# Pseudo-relation types that are really escalation markers, not real DB relations
ESCALATION_RELATION_TYPES = {
    "needs_hypernym_review",
    "needs_closer_hypernym_review",
    "hypernym_review_needed",
    "needs_review",
}

# Dependency ordering: lower number = applied first.
# 7 phases: removals → modifications → creations → additions → relations → metadata → escalation
COMMAND_ORDER: dict[str, int] = {
    "remove_sense": 0,
    "remove_synset_relation": 1,
    "remove_sense_relation": 1,
    "remove_form": 1,
    "remove_definition": 1,
    "remove_synset_example": 1,
    "remove_sense_example": 1,
    "move_sense": 2,
    "update_definition": 3,
    "update_lemma": 4,
    "update_entry": 5,
    "update_synset": 5,
    "create_entry": 6,
    "add_sense": 7,
    "add_definition": 8,
    "add_form": 8,
    "add_synset_example": 9,
    "add_sense_example": 9,
    "add_synset_relation": 10,
    "add_sense_relation": 10,
    "set_metadata": 11,
    "set_confidence": 12,
    "escalate": 13,
}

# Pattern for {auto}, {auto:hint}, {auto-hint}, {auto — long hint}
AUTO_ID_RE = re.compile(r"^\{auto(?:\s*[:\-–—]\s*(.+?))?\s*\}$")

# Pattern for placeholder target IDs: {human_review_needed: ...}, {synset_for_...}
PLACEHOLDER_TARGET_RE = re.compile(r"^\{.+\}$")

# Arabic diacritics (tashkeel) to strip for fuzzy matching
_TASHKEEL = re.compile(r"[\u064B-\u065F\u0670]")


def strip_tashkeel(text: str) -> str:
    """Remove Arabic diacritical marks for fuzzy comparison."""
    return _TASHKEEL.sub("", text)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ContextualAction:
    """An action extracted from a review YAML with parent context."""
    command: str
    params: dict[str, Any]
    parent_lemma: Optional[str] = None
    synset_id: Optional[str] = None
    source_step: Optional[str] = None
    yaml_path: Optional[str] = None


@dataclass
class ActionResult:
    """Result of applying a single action."""
    command: str
    success: bool
    message: str
    params: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    escalated: bool = False
    error: Optional[str] = None


@dataclass
class SynsetReport:
    """Application report for a single synset."""
    synset_id: str
    yaml_source: str
    actions_applied: int = 0
    actions_skipped: int = 0
    actions_escalated: int = 0
    actions_failed: int = 0
    results: list[ActionResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def record(self, result: ActionResult) -> None:
        self.results.append(result)
        if result.escalated:
            self.actions_escalated += 1
        elif result.skipped:
            self.actions_skipped += 1
        elif result.success:
            self.actions_applied += 1
        else:
            self.actions_failed += 1

    def record_error(self, error: str) -> None:
        self.errors.append(error)
        self.actions_failed += 1


# ═══════════════════════════════════════════════════════════════════════════════
# ActionExtractor — Pure YAML walking (API-independent)
# ═══════════════════════════════════════════════════════════════════════════════


def _infer_step5_lemma(
    action: dict,
    example_to_lemma: dict[str, str],
    enrichment_key_to_lemma: dict[str, str],
    step5_lemmas: list[str],
) -> Optional[str]:
    """Infer parent lemma for a step5-level action using multiple strategies."""
    params = action.get("params", {})
    action_text = params.get("text", "")

    # Strategy 1: exact example text match
    if action_text and action_text in example_to_lemma:
        return example_to_lemma[action_text]

    # Strategy 2: diacritic-insensitive lemma-in-text match
    if action_text:
        bare_text = strip_tashkeel(action_text)
        for lm in step5_lemmas:
            bare_lm = strip_tashkeel(lm)
            if bare_lm in bare_text:
                return lm

    # Strategy 3: for set_metadata — match enrichment key to per_lemma
    cmd = action.get("command", "")
    if cmd in ("set_metadata", "set_confidence"):
        key = params.get("key", "")
        if key and key in enrichment_key_to_lemma:
            return enrichment_key_to_lemma[key]

    # Strategy 4: {auto-LEMMA_HINT} — extract hint from entity_id
    entity_id = str(params.get("entity_id", ""))
    m = AUTO_ID_RE.match(entity_id)
    if m and m.group(1):
        hint = m.group(1).strip()
        bare_hint = strip_tashkeel(hint)
        for lm in step5_lemmas:
            if strip_tashkeel(lm) == bare_hint:
                return lm
        return hint

    # Strategy 5: single-lemma fallback
    if len(step5_lemmas) == 1:
        return step5_lemmas[0]

    return None


def detect_review_format(data: dict) -> str:
    """Detect whether a review YAML uses v1 or v2 format.

    v2 format has top-level keys: stage1_review, stage2_evidence, stage3_analysis, ...
    v1 format has top-level keys: step0_evidence, step05_lemma_generation, step1_lemma_validation, ...
    """
    return "v2" if "stage1_review" in data else "v1"


class ActionExtractor:
    """Parse review YAML and collect all actions with parent context."""

    @staticmethod
    def extract_synset_id(yaml_path: Path) -> str:
        return yaml_path.name.replace(".review.yaml", "")

    @staticmethod
    def collect_actions(
        review_data: dict,
        synset_id: str,
        yaml_path: Path,
    ) -> list[ContextualAction]:
        all_actions: list[ContextualAction] = []

        # Step 1: lemma validation (per-lemma actions)
        step1 = review_data.get("step1_lemma_validation", {})
        if isinstance(step1, dict):
            for lemma_block in step1.get("per_lemma", []):
                if not isinstance(lemma_block, dict):
                    continue
                lemma = lemma_block.get("lemma", "")
                for action in lemma_block.get("actions", []):
                    if isinstance(action, dict):
                        all_actions.append(ContextualAction(
                            command=action.get("command", ""),
                            params=dict(action.get("params", {})),
                            parent_lemma=lemma,
                            synset_id=synset_id,
                            source_step="step1",
                            yaml_path=str(yaml_path),
                        ))

        # Step 3: definition (synset-level actions)
        step3 = review_data.get("step3_definition", {})
        if isinstance(step3, dict):
            for action in step3.get("actions", []):
                if isinstance(action, dict):
                    all_actions.append(ContextualAction(
                        command=action.get("command", ""),
                        params=dict(action.get("params", {})),
                        synset_id=synset_id,
                        source_step="step3",
                        yaml_path=str(yaml_path),
                    ))

        # Step 4: relations (synset-level actions)
        step4 = review_data.get("step4_relations", {})
        if isinstance(step4, dict):
            for action in step4.get("actions", []):
                if isinstance(action, dict):
                    all_actions.append(ContextualAction(
                        command=action.get("command", ""),
                        params=dict(action.get("params", {})),
                        synset_id=synset_id,
                        source_step="step4",
                        yaml_path=str(yaml_path),
                    ))

        # Step 5: enrichment (per-lemma + synset-level actions)
        step5 = review_data.get("step5_enrichment", {})
        if isinstance(step5, dict):
            # Build example text → lemma map
            example_to_lemma: dict[str, str] = {}
            for lemma_block in step5.get("per_lemma", []):
                if not isinstance(lemma_block, dict):
                    continue
                lemma = lemma_block.get("lemma", "")
                for ex in lemma_block.get("examples", []):
                    if isinstance(ex, dict) and "text" in ex:
                        example_to_lemma[ex["text"]] = lemma

            # Per-lemma enrichment actions
            for lemma_block in step5.get("per_lemma", []):
                if not isinstance(lemma_block, dict):
                    continue
                lemma = lemma_block.get("lemma", "")
                for action in lemma_block.get("actions", []):
                    if isinstance(action, dict):
                        all_actions.append(ContextualAction(
                            command=action.get("command", ""),
                            params=dict(action.get("params", {})),
                            parent_lemma=lemma,
                            synset_id=synset_id,
                            source_step="step5",
                            yaml_path=str(yaml_path),
                        ))

            # Collect per-lemma info for fallback matching
            step5_lemmas = [
                lb.get("lemma", "")
                for lb in step5.get("per_lemma", [])
                if isinstance(lb, dict) and lb.get("lemma")
            ]
            enrichment_key_to_lemma: dict[str, str] = {}
            for lb in step5.get("per_lemma", []):
                if not isinstance(lb, dict):
                    continue
                lm = lb.get("lemma", "")
                enrichment = lb.get("enrichment", {})
                if isinstance(enrichment, dict):
                    for ek in enrichment:
                        if ek not in ("root", "root_corrected"):
                            enrichment_key_to_lemma[ek] = lm

            # Synset-level enrichment actions — infer lemma from context
            for action in step5.get("actions", []):
                if isinstance(action, dict):
                    inferred_lemma = _infer_step5_lemma(
                        action, example_to_lemma,
                        enrichment_key_to_lemma, step5_lemmas,
                    )
                    all_actions.append(ContextualAction(
                        command=action.get("command", ""),
                        params=dict(action.get("params", {})),
                        parent_lemma=inferred_lemma,
                        synset_id=synset_id,
                        source_step="step5",
                        yaml_path=str(yaml_path),
                    ))

        # Top-level actions (older YAML anchor format)
        for action in review_data.get("actions", []):
            if isinstance(action, dict):
                all_actions.append(ContextualAction(
                    command=action.get("command", ""),
                    params=dict(action.get("params", {})),
                    synset_id=synset_id,
                    source_step="top_level",
                    yaml_path=str(yaml_path),
                ))

        return all_actions

    @staticmethod
    def collect_actions_v2(
        review_data: dict,
        synset_id: str,
        yaml_path: Path,
    ) -> list[ContextualAction]:
        """Walk v2 (pipeline v2) YAML structure and collect all actions.

        v2 top-level keys: stage1_review, stage2_evidence, stage3_analysis,
        stage4_content, stage5_enrichment.
        """
        all_actions: list[ContextualAction] = []

        def _collect(actions_list, parent_lemma=None, source_step=""):
            if not isinstance(actions_list, list):
                return
            for action in actions_list:
                if isinstance(action, dict):
                    all_actions.append(ContextualAction(
                        command=action.get("command", ""),
                        params=dict(action.get("params", {})),
                        parent_lemma=parent_lemma,
                        synset_id=synset_id,
                        source_step=source_step,
                        yaml_path=str(yaml_path),
                    ))

        # Stage 3: per-lemma membership + sense relation actions
        stage3 = review_data.get("stage3_analysis", {})
        if isinstance(stage3, dict):
            for lemma_block in stage3.get("per_lemma", []):
                if not isinstance(lemma_block, dict):
                    continue
                lemma = lemma_block.get("lemma", "")
                _collect(lemma_block.get("actions", []), lemma, "stage3")
            # Synset-level actions (e.g., update_synset)
            _collect(stage3.get("synset_actions", []), None, "stage3")

        # Stage 4: definition actions + example actions
        stage4 = review_data.get("stage4_content", {})
        if isinstance(stage4, dict):
            definition = stage4.get("definition", {})
            if isinstance(definition, dict):
                _collect(definition.get("actions", []), None, "stage4_def")
            examples = stage4.get("examples", {})
            if isinstance(examples, dict):
                # Infer parent lemma from per_lemma examples for sense-level actions
                example_to_lemma: dict[str, str] = {}
                for lemma_block in examples.get("per_lemma", []):
                    if isinstance(lemma_block, dict):
                        lm = lemma_block.get("lemma", "")
                        for ex in lemma_block.get("examples", []):
                            if isinstance(ex, dict) and "text" in ex:
                                example_to_lemma[ex["text"]] = lm
                for action in examples.get("actions", []):
                    if isinstance(action, dict):
                        # Try to infer parent lemma from the action's text
                        params = action.get("params", {})
                        text = params.get("text", "")
                        parent = example_to_lemma.get(text)
                        all_actions.append(ContextualAction(
                            command=action.get("command", ""),
                            params=dict(params),
                            parent_lemma=parent,
                            synset_id=synset_id,
                            source_step="stage4_ex",
                            yaml_path=str(yaml_path),
                        ))

        # Stage 5: enrichment actions (entry/sense/synset metadata + confidence)
        stage5 = review_data.get("stage5_enrichment", {})
        if isinstance(stage5, dict):
            # Build per_entry lemma map for entity_id inference
            entry_lemmas = [
                lb.get("lemma", "")
                for lb in stage5.get("per_entry", [])
                if isinstance(lb, dict) and lb.get("lemma")
            ]
            sense_lemmas = [
                lb.get("lemma", "")
                for lb in stage5.get("per_sense", [])
                if isinstance(lb, dict) and lb.get("lemma")
            ]
            all_lemmas = entry_lemmas + sense_lemmas
            for action in stage5.get("actions", []):
                if isinstance(action, dict):
                    params = action.get("params", {})
                    # Infer parent lemma from {auto:hint} in entity_id
                    entity_id = str(params.get("entity_id", ""))
                    inferred = None
                    m = AUTO_ID_RE.match(entity_id)
                    if m and m.group(1):
                        hint = m.group(1).strip()
                        bare_hint = strip_tashkeel(hint)
                        for lm in all_lemmas:
                            if strip_tashkeel(lm) == bare_hint:
                                inferred = lm
                                break
                        if not inferred:
                            inferred = hint
                    elif len(all_lemmas) == 1:
                        inferred = all_lemmas[0]
                    all_actions.append(ContextualAction(
                        command=action.get("command", ""),
                        params=dict(params),
                        parent_lemma=inferred,
                        synset_id=synset_id,
                        source_step="stage5",
                        yaml_path=str(yaml_path),
                    ))

        return all_actions


# ═══════════════════════════════════════════════════════════════════════════════
# AutoResolver — Resolve {auto} IDs using WordnetEditor API
# ═══════════════════════════════════════════════════════════════════════════════


class AutoResolver:
    """Resolve {auto} placeholder IDs to concrete entity IDs."""

    def __init__(self, editor: WordnetEditor, lexicon_id: str):
        self.editor = editor
        self.lexicon_id = lexicon_id

    def resolve_auto_ids(
        self,
        action: ContextualAction,
        created_entries: dict[str, str],
    ) -> None:
        """Resolve all {auto} IDs in an action's params, in place."""
        params = action.params
        synset_id = action.synset_id or params.get("synset_id", "")
        lemma = action.parent_lemma or ""

        # --- sense_id: "{auto}" ---
        if "sense_id" in params:
            raw = str(params["sense_id"])
            m = AUTO_ID_RE.match(raw)
            if m:
                hint = m.group(1) or lemma
                resolved = self._resolve_sense_id(hint, synset_id)
                if resolved is not None:
                    params["sense_id"] = resolved
                else:
                    params["_unresolved_sense"] = True
                    logger.warning(
                        "Could not resolve sense_id {auto} for lemma=%r synset=%s",
                        hint, synset_id,
                    )

        # --- entry_id: "{auto}" ---
        if "entry_id" in params:
            raw = str(params["entry_id"])
            m = AUTO_ID_RE.match(raw)
            if m:
                hint = m.group(1) or lemma
                # Check if we just created this entry in the same batch
                if hint in created_entries:
                    params["entry_id"] = created_entries[hint]
                else:
                    # Also check tashkeel-stripped match in created_entries
                    bare_hint = strip_tashkeel(hint)
                    matched = None
                    for ce_lemma, ce_id in created_entries.items():
                        if strip_tashkeel(ce_lemma) == bare_hint:
                            matched = ce_id
                            break
                    if matched:
                        params["entry_id"] = matched
                    else:
                        resolved = self._resolve_entry_id(hint)
                        if resolved is not None:
                            params["entry_id"] = resolved
                        else:
                            params["_unresolved_entry"] = True
                            logger.warning(
                                "Could not resolve entry_id {auto} for lemma=%r",
                                hint,
                            )

        # --- entity_id: "{auto}" (set_metadata / set_confidence) ---
        if "entity_id" in params:
            raw = str(params["entity_id"])
            m = AUTO_ID_RE.match(raw)
            if m:
                hint = m.group(1) or lemma
                entity_type = params.get("entity_type", "")
                if entity_type == "sense":
                    resolved = self._resolve_sense_id(hint, synset_id)
                    if resolved is not None:
                        params["entity_id"] = resolved
                    else:
                        params["_unresolved_entity"] = True
                elif entity_type == "entry":
                    if hint in created_entries:
                        params["entity_id"] = created_entries[hint]
                    else:
                        resolved = self._resolve_entry_id(hint)
                        if resolved is not None:
                            params["entity_id"] = resolved
                        else:
                            params["_unresolved_entity"] = True
                elif entity_type == "synset":
                    params["entity_id"] = synset_id
                else:
                    params["_unresolved_entity"] = True

    def _resolve_sense_id(self, lemma: str, synset_id: str) -> Optional[str]:
        """Find a sense ID for the given lemma in the given synset."""
        if not lemma or not synset_id:
            return None

        # Try 1: exact lemma match via find_entries
        entries = self.editor.find_entries(
            lemma=lemma, lexicon_id=self.lexicon_id,
        )
        for entry in entries:
            senses = self.editor.find_senses(
                entry_id=entry.id, synset_id=synset_id,
            )
            if senses:
                return senses[0].id

        # Try 2: tashkeel-stripped fallback over the synset's senses
        return self._resolve_sense_by_tashkeel(lemma, synset_id)

    def _resolve_sense_by_tashkeel(
        self, lemma: str, synset_id: str,
    ) -> Optional[str]:
        """Fallback: iterate senses of the synset, strip-compare lemmas."""
        bare = strip_tashkeel(lemma)
        try:
            senses = self.editor.find_senses(synset_id=synset_id)
        except EntityNotFoundError:
            return None
        for sense in senses:
            try:
                entry = self.editor.get_entry(sense.entry_id)
                if strip_tashkeel(entry.lemma) == bare:
                    return sense.id
            except EntityNotFoundError:
                continue
        return None

    def _resolve_entry_id(self, lemma: str) -> Optional[str]:
        """Find an entry ID for the given lemma."""
        if not lemma:
            return None
        entries = self.editor.find_entries(
            lemma=lemma, lexicon_id=self.lexicon_id,
        )
        if entries:
            return entries[0].id

        # Tashkeel fallback: search broader (all entries in lexicon with any pos)
        # This is expensive, so skip for now and return None
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewDispatcher — Map commands to WordnetEditor API calls
# ═══════════════════════════════════════════════════════════════════════════════


class ReviewDispatcher:
    """Dispatch review actions to WordnetEditor v1.0.0 methods."""

    def __init__(
        self,
        editor: WordnetEditor,
        lexicon_id: str,
        dry_run: bool = False,
    ):
        self.editor = editor
        self.lexicon_id = lexicon_id
        self.dry_run = dry_run

    def dispatch(
        self,
        action: ContextualAction,
        created_entries: dict[str, str],
    ) -> ActionResult:
        """Dispatch a single action to the appropriate editor method."""
        cmd = action.command
        params = action.params

        # Check for unresolved IDs
        if params.get("_unresolved_sense") or params.get("_unresolved_entry") \
                or params.get("_unresolved_entity"):
            # For remove_sense: unresolved = sense already absent (idempotent)
            if cmd == "remove_sense" and params.get("_unresolved_sense"):
                return ActionResult(
                    command=cmd, success=True,
                    message="Sense not found — already absent (idempotent)",
                    params=params, skipped=True,
                )
            return ActionResult(
                command=cmd, success=False,
                message="Unresolved {auto} ID",
                params=params,
                error=f"Could not resolve {{auto}} for {cmd}",
            )

        if self.dry_run:
            return ActionResult(
                command=cmd, success=True,
                message=f"[DRY RUN] Would execute {cmd}",
                params=params, skipped=True,
            )

        try:
            dispatch_map = {
                "remove_sense": self._exec_remove_sense,
                "update_definition": self._exec_update_definition,
                "add_definition": self._exec_add_definition,
                "remove_definition": self._exec_remove_definition,
                "add_synset_example": self._exec_add_synset_example,
                "add_sense_example": self._exec_add_sense_example,
                "remove_synset_example": self._exec_remove_synset_example,
                "remove_sense_example": self._exec_remove_sense_example,
                "add_synset_relation": self._exec_add_synset_relation,
                "remove_synset_relation": self._exec_remove_synset_relation,
                "add_sense_relation": self._exec_add_sense_relation,
                "remove_sense_relation": self._exec_remove_sense_relation,
                "update_lemma": self._exec_update_lemma,
                "update_entry": self._exec_update_entry,
                "update_synset": self._exec_update_synset,
                "add_form": self._exec_add_form,
                "remove_form": self._exec_remove_form,
                "set_metadata": self._exec_set_metadata,
                "set_confidence": self._exec_set_confidence,
                "move_sense": self._exec_move_sense,
            }

            # create_entry and add_sense need created_entries tracking
            if cmd == "create_entry":
                return self._exec_create_entry(action, created_entries)
            elif cmd == "add_sense":
                return self._exec_add_sense(params)
            elif cmd == "create_entry_and_add_sense":
                return self._exec_create_entry_and_add_sense(
                    action, created_entries,
                )
            elif cmd in dispatch_map:
                return dispatch_map[cmd](params)
            else:
                return ActionResult(
                    command=cmd, success=False,
                    message=f"Unknown command: {cmd}",
                    params=params, skipped=True,
                )
        except Exception as e:
            logger.exception("Error executing %s", cmd)
            return ActionResult(
                command=cmd, success=False,
                message=f"Error: {e}", params=params, error=str(e),
            )

    # ─── Individual command executors ─────────────────────────────────────

    def _exec_remove_sense(self, params: dict) -> ActionResult:
        sense_id = params.get("sense_id")
        if sense_id is None:
            return ActionResult(
                command="remove_sense", success=False,
                message="No sense_id", params=params, error="sense_id is None",
            )
        try:
            self.editor.remove_sense(sense_id)
            return ActionResult(
                command="remove_sense", success=True,
                message=f"Removed sense {sense_id}", params=params,
            )
        except EntityNotFoundError:
            return ActionResult(
                command="remove_sense", success=True,
                message=f"Sense already removed (idempotent): {sense_id}",
                params=params, skipped=True,
            )

    def _exec_update_definition(self, params: dict) -> ActionResult:
        synset_id = params.get("synset_id", "")
        text = params.get("text", "")
        def_index = int(params.get("definition_index", 0))

        # Idempotency: check if definition already matches
        try:
            defs = self.editor.get_definitions(synset_id)
            if def_index < len(defs) and defs[def_index].text == text:
                return ActionResult(
                    command="update_definition", success=True,
                    message="Definition already matches (idempotent)",
                    params=params, skipped=True,
                )
        except EntityNotFoundError:
            pass

        self.editor.update_definition(synset_id, def_index, text)
        return ActionResult(
            command="update_definition", success=True,
            message=f"Updated definition[{def_index}] on {synset_id}",
            params=params,
        )

    def _exec_add_definition(self, params: dict) -> ActionResult:
        synset_id = params.get("synset_id", "")
        text = params.get("text", "")

        # Idempotency: check if definition text already exists
        try:
            defs = self.editor.get_definitions(synset_id)
            if any(d.text == text for d in defs):
                return ActionResult(
                    command="add_definition", success=True,
                    message="Definition already exists (idempotent)",
                    params=params, skipped=True,
                )
        except EntityNotFoundError:
            pass

        self.editor.add_definition(synset_id, text)
        return ActionResult(
            command="add_definition", success=True,
            message=f"Added definition to {synset_id}", params=params,
        )

    def _exec_add_synset_example(self, params: dict) -> ActionResult:
        synset_id = params.get("synset_id", "")
        text = params.get("text", "")

        # Idempotency
        try:
            examples = self.editor.get_synset_examples(synset_id)
            if any(ex.text == text for ex in examples):
                return ActionResult(
                    command="add_synset_example", success=True,
                    message="Example already exists (idempotent)",
                    params=params, skipped=True,
                )
        except EntityNotFoundError:
            pass

        self.editor.add_synset_example(synset_id, text)
        return ActionResult(
            command="add_synset_example", success=True,
            message=f"Added example to {synset_id}", params=params,
        )

    def _exec_add_sense_example(self, params: dict) -> ActionResult:
        sense_id = params.get("sense_id")
        text = params.get("text", "")

        if sense_id is None:
            return ActionResult(
                command="add_sense_example", success=False,
                message="No sense_id", params=params, error="sense_id is None",
            )

        # Idempotency
        try:
            examples = self.editor.get_sense_examples(sense_id)
            if any(ex.text == text for ex in examples):
                return ActionResult(
                    command="add_sense_example", success=True,
                    message="Sense example already exists (idempotent)",
                    params=params, skipped=True,
                )
        except EntityNotFoundError:
            pass

        self.editor.add_sense_example(sense_id, text)
        return ActionResult(
            command="add_sense_example", success=True,
            message=f"Added example to sense {sense_id}", params=params,
        )

    def _exec_create_entry(
        self,
        action: ContextualAction,
        created_entries: dict[str, str],
    ) -> ActionResult:
        params = action.params
        lemma = params.get("lemma", "")
        pos = params.get("pos", "n")

        # Idempotency: check if entry with same lemma+pos already exists
        existing = self.editor.find_entries(
            lemma=lemma, pos=pos, lexicon_id=self.lexicon_id,
        )
        if existing:
            entry_id = existing[0].id
            created_entries[lemma] = entry_id
            return ActionResult(
                command="create_entry", success=True,
                message=f"Entry already exists (reusing {entry_id})",
                params=params, skipped=True,
            )

        entry = self.editor.create_entry(self.lexicon_id, lemma, pos)
        created_entries[lemma] = entry.id
        return ActionResult(
            command="create_entry", success=True,
            message=f"Created entry '{lemma}' (id={entry.id})",
            params=params,
        )

    def _exec_add_sense(self, params: dict) -> ActionResult:
        entry_id = params.get("entry_id")
        synset_id = params.get("synset_id", "")

        if entry_id is None:
            return ActionResult(
                command="add_sense", success=False,
                message="No entry_id", params=params, error="entry_id is None",
            )

        try:
            sense = self.editor.add_sense(entry_id, synset_id)
            return ActionResult(
                command="add_sense", success=True,
                message=f"Added sense {sense.id}: {entry_id} → {synset_id}",
                params=params,
            )
        except DuplicateEntityError:
            return ActionResult(
                command="add_sense", success=True,
                message=f"Sense already exists (idempotent): {entry_id} → {synset_id}",
                params=params, skipped=True,
            )

    def _exec_create_entry_and_add_sense(
        self,
        action: ContextualAction,
        created_entries: dict[str, str],
    ) -> ActionResult:
        """Combined create_entry + add_sense (from Arabic command shorthand)."""
        create_result = self._exec_create_entry(action, created_entries)
        if not create_result.success:
            return create_result

        lemma = action.params.get("lemma", "")
        synset_id = action.synset_id or action.params.get("synset_id", "")
        sense_params = {
            "entry_id": created_entries.get(lemma),
            "synset_id": synset_id,
        }
        sense_result = self._exec_add_sense(sense_params)
        if not sense_result.success:
            return sense_result

        return ActionResult(
            command="create_entry_and_add_sense", success=True,
            message=f"Created entry+sense for '{lemma}' → {synset_id}",
            params=action.params,
        )

    def _exec_set_metadata(self, params: dict) -> ActionResult:
        entity_type = params.get("entity_type", "")
        entity_id = params.get("entity_id")
        key = params.get("key", "")
        value = params.get("value", "")

        if entity_id is None:
            return ActionResult(
                command="set_metadata", success=False,
                message="No entity_id", params=params,
                error="entity_id is None",
            )

        try:
            # Idempotency: check if metadata key already has the same value
            existing = self.editor.get_metadata(entity_type, entity_id)
            if existing.get(key) == value:
                return ActionResult(
                    command="set_metadata", success=True,
                    message=f"Metadata already set (idempotent): {key}",
                    params=params, skipped=True,
                )
            self.editor.set_metadata(entity_type, entity_id, key, value)
            return ActionResult(
                command="set_metadata", success=True,
                message=f"Set {key}={value} on {entity_type} {entity_id}",
                params=params,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="set_metadata", success=False,
                message=f"Entity not found: {e}",
                params=params, escalated=True,
                error=str(e),
            )

    def _exec_set_confidence(self, params: dict) -> ActionResult:
        entity_type = params.get("entity_type", "")
        entity_id = params.get("entity_id")
        score = float(params.get("score", 0.0))

        if entity_id is None:
            return ActionResult(
                command="set_confidence", success=False,
                message="No entity_id", params=params,
                error="entity_id is None",
            )

        try:
            # Idempotency: check if confidence already matches
            existing = self.editor.get_metadata(entity_type, entity_id)
            if existing.get("confidenceScore") == score:
                return ActionResult(
                    command="set_confidence", success=True,
                    message=f"Confidence already set (idempotent): {score}",
                    params=params, skipped=True,
                )
            self.editor.set_confidence(entity_type, entity_id, score)
            return ActionResult(
                command="set_confidence", success=True,
                message=f"Set confidence={score} on {entity_type} {entity_id}",
                params=params,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="set_confidence", success=False,
                message=f"Entity not found: {e}",
                params=params, escalated=True,
                error=str(e),
            )

    def _exec_add_synset_relation(self, params: dict) -> ActionResult:
        source_id = params.get("source_id", "")
        target_id = str(params.get("target_id", ""))
        relation_type = params.get("relation_type", "")

        # Check for placeholder targets
        if PLACEHOLDER_TARGET_RE.match(target_id):
            return ActionResult(
                command="add_synset_relation", success=False,
                message=f"Placeholder target: {target_id}",
                params=params, escalated=True,
                error=f"Cannot resolve placeholder: {target_id}",
            )

        # Check for pseudo-relation escalation markers
        if relation_type in ESCALATION_RELATION_TYPES:
            return ActionResult(
                command="add_synset_relation", success=False,
                message=f"Escalation marker relation: {relation_type}",
                params=params, escalated=True,
                error=f"Pseudo-relation type (escalation): {relation_type}",
            )

        # Normalize non-standard relation type names
        if relation_type in RELATION_TYPE_MAP:
            relation_type = RELATION_TYPE_MAP[relation_type]

        try:
            # Idempotency: check if relation already exists
            rels = self.editor.get_synset_relations(
                source_id, relation_type=relation_type,
            )
            if any(r.target_id == target_id for r in rels):
                return ActionResult(
                    command="add_synset_relation", success=True,
                    message=f"Relation already exists (idempotent): {relation_type} {source_id} → {target_id}",
                    params=params, skipped=True,
                )
            self.editor.add_synset_relation(source_id, relation_type, target_id)
            return ActionResult(
                command="add_synset_relation", success=True,
                message=f"Added {relation_type}: {source_id} → {target_id}",
                params=params,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="add_synset_relation", success=False,
                message=f"Missing entity: {e}",
                params=params, escalated=True,
                error=f"Target or source not found: {e}",
            )
        except (RelationError, ValidationError) as e:
            return ActionResult(
                command="add_synset_relation", success=False,
                message=f"Invalid relation: {e}",
                params=params, escalated=True,
                error=str(e),
            )

    def _exec_remove_synset_relation(self, params: dict) -> ActionResult:
        source_id = params.get("source_id", "")
        target_id = params.get("target_id", "")
        relation_type = params.get("relation_type", "")

        # Normalize relation type (same as add)
        if relation_type in RELATION_TYPE_MAP:
            relation_type = RELATION_TYPE_MAP[relation_type]

        try:
            # Idempotency: check if relation actually exists
            rels = self.editor.get_synset_relations(
                source_id, relation_type=relation_type,
            )
            if not any(r.target_id == target_id for r in rels):
                return ActionResult(
                    command="remove_synset_relation", success=True,
                    message=f"Already absent (idempotent): {relation_type} {source_id} → {target_id}",
                    params=params, skipped=True,
                )
            self.editor.remove_synset_relation(source_id, relation_type, target_id)
            return ActionResult(
                command="remove_synset_relation", success=True,
                message=f"Removed {relation_type}: {source_id} → {target_id}",
                params=params,
            )
        except EntityNotFoundError:
            return ActionResult(
                command="remove_synset_relation", success=True,
                message=f"Already absent (idempotent): {relation_type} {source_id} → {target_id}",
                params=params, skipped=True,
            )

    def _exec_move_sense(self, params: dict) -> ActionResult:
        sense_id = params.get("sense_id")
        target_synset_id = params.get("target_synset_id", "")

        if sense_id is None:
            return ActionResult(
                command="move_sense", success=False,
                message="No sense_id", params=params, error="sense_id is None",
            )

        if PLACEHOLDER_TARGET_RE.match(str(target_synset_id)):
            return ActionResult(
                command="move_sense", success=False,
                message=f"Placeholder target: {target_synset_id}",
                params=params, escalated=True,
                error=f"Cannot resolve placeholder: {target_synset_id}",
            )

        self.editor.move_sense(sense_id, target_synset_id)
        return ActionResult(
            command="move_sense", success=True,
            message=f"Moved sense {sense_id} → {target_synset_id}",
            params=params,
        )

    # ─── v2 pipeline handlers ────────────────────────────────────────────

    def _exec_update_lemma(self, params: dict) -> ActionResult:
        entry_id = params.get("entry_id")
        new_lemma = params.get("new_lemma", "")

        if entry_id is None:
            return ActionResult(
                command="update_lemma", success=False,
                message="No entry_id", params=params, error="entry_id is None",
            )

        try:
            entry = self.editor.get_entry(entry_id)
            if entry.lemma == new_lemma:
                return ActionResult(
                    command="update_lemma", success=True,
                    message=f"Lemma already matches (idempotent): {new_lemma}",
                    params=params, skipped=True,
                )
            self.editor.update_lemma(entry_id, new_lemma)
            return ActionResult(
                command="update_lemma", success=True,
                message=f"Updated lemma on {entry_id}: {entry.lemma} → {new_lemma}",
                params=params,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="update_lemma", success=False,
                message=f"Entry not found: {e}",
                params=params, error=str(e),
            )

    def _exec_update_entry(self, params: dict) -> ActionResult:
        entry_id = params.get("entry_id")
        pos = params.get("pos")

        if entry_id is None:
            return ActionResult(
                command="update_entry", success=False,
                message="No entry_id", params=params, error="entry_id is None",
            )

        try:
            entry = self.editor.get_entry(entry_id)
            if entry.pos == pos:
                return ActionResult(
                    command="update_entry", success=True,
                    message=f"POS already matches (idempotent): {pos}",
                    params=params, skipped=True,
                )
            self.editor.update_entry(entry_id, pos=pos)
            return ActionResult(
                command="update_entry", success=True,
                message=f"Updated entry {entry_id} POS → {pos}",
                params=params,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="update_entry", success=False,
                message=f"Entry not found: {e}",
                params=params, error=str(e),
            )

    def _exec_update_synset(self, params: dict) -> ActionResult:
        synset_id = params.get("synset_id", "")
        pos = params.get("pos")

        try:
            synset = self.editor.get_synset(synset_id)
            if synset.pos == pos:
                return ActionResult(
                    command="update_synset", success=True,
                    message=f"Synset POS already matches (idempotent): {pos}",
                    params=params, skipped=True,
                )
            self.editor.update_synset(synset_id, pos=pos)
            return ActionResult(
                command="update_synset", success=True,
                message=f"Updated synset {synset_id} POS → {pos}",
                params=params,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="update_synset", success=False,
                message=f"Synset not found: {e}",
                params=params, error=str(e),
            )

    def _exec_add_form(self, params: dict) -> ActionResult:
        entry_id = params.get("entry_id")
        written_form = params.get("written_form", "")

        if entry_id is None:
            return ActionResult(
                command="add_form", success=False,
                message="No entry_id", params=params, error="entry_id is None",
            )

        try:
            self.editor.add_form(entry_id, written_form)
            return ActionResult(
                command="add_form", success=True,
                message=f"Added form '{written_form}' to entry {entry_id}",
                params=params,
            )
        except DuplicateEntityError:
            return ActionResult(
                command="add_form", success=True,
                message=f"Form already exists (idempotent): {written_form}",
                params=params, skipped=True,
            )

    def _exec_remove_form(self, params: dict) -> ActionResult:
        entry_id = params.get("entry_id")
        written_form = params.get("written_form", "")

        if entry_id is None:
            return ActionResult(
                command="remove_form", success=False,
                message="No entry_id", params=params, error="entry_id is None",
            )

        try:
            self.editor.remove_form(entry_id, written_form)
            return ActionResult(
                command="remove_form", success=True,
                message=f"Removed form '{written_form}' from entry {entry_id}",
                params=params,
            )
        except EntityNotFoundError:
            return ActionResult(
                command="remove_form", success=True,
                message=f"Form already absent (idempotent): {written_form}",
                params=params, skipped=True,
            )

    def _exec_remove_definition(self, params: dict) -> ActionResult:
        synset_id = params.get("synset_id", "")
        def_index = int(params.get("definition_index", 0))

        try:
            defs = self.editor.get_definitions(synset_id)
            if def_index >= len(defs):
                return ActionResult(
                    command="remove_definition", success=True,
                    message=f"Definition index {def_index} out of range (idempotent)",
                    params=params, skipped=True,
                )
            self.editor.remove_definition(synset_id, def_index)
            return ActionResult(
                command="remove_definition", success=True,
                message=f"Removed definition[{def_index}] from {synset_id}",
                params=params,
            )
        except (EntityNotFoundError, IndexError) as e:
            return ActionResult(
                command="remove_definition", success=True,
                message=f"Already absent (idempotent): {e}",
                params=params, skipped=True,
            )

    def _exec_remove_synset_example(self, params: dict) -> ActionResult:
        synset_id = params.get("synset_id", "")
        example_index = int(params.get("example_index", 0))

        try:
            examples = self.editor.get_synset_examples(synset_id)
            if example_index >= len(examples):
                return ActionResult(
                    command="remove_synset_example", success=True,
                    message=f"Example index {example_index} out of range (idempotent)",
                    params=params, skipped=True,
                )
            self.editor.remove_synset_example(synset_id, example_index)
            return ActionResult(
                command="remove_synset_example", success=True,
                message=f"Removed synset example[{example_index}] from {synset_id}",
                params=params,
            )
        except (EntityNotFoundError, IndexError) as e:
            return ActionResult(
                command="remove_synset_example", success=True,
                message=f"Already absent (idempotent): {e}",
                params=params, skipped=True,
            )

    def _exec_remove_sense_example(self, params: dict) -> ActionResult:
        sense_id = params.get("sense_id")
        example_index = int(params.get("example_index", 0))

        if sense_id is None:
            return ActionResult(
                command="remove_sense_example", success=False,
                message="No sense_id", params=params, error="sense_id is None",
            )

        try:
            examples = self.editor.get_sense_examples(sense_id)
            if example_index >= len(examples):
                return ActionResult(
                    command="remove_sense_example", success=True,
                    message=f"Example index {example_index} out of range (idempotent)",
                    params=params, skipped=True,
                )
            self.editor.remove_sense_example(sense_id, example_index)
            return ActionResult(
                command="remove_sense_example", success=True,
                message=f"Removed sense example[{example_index}] from {sense_id}",
                params=params,
            )
        except (EntityNotFoundError, IndexError) as e:
            return ActionResult(
                command="remove_sense_example", success=True,
                message=f"Already absent (idempotent): {e}",
                params=params, skipped=True,
            )

    def _exec_add_sense_relation(self, params: dict) -> ActionResult:
        source_id = params.get("source_id", "")
        target_id = str(params.get("target_id", ""))
        relation_type = params.get("relation_type", "")

        if PLACEHOLDER_TARGET_RE.match(target_id):
            return ActionResult(
                command="add_sense_relation", success=False,
                message=f"Placeholder target: {target_id}",
                params=params, escalated=True,
                error=f"Cannot resolve placeholder: {target_id}",
            )

        try:
            self.editor.add_sense_relation(source_id, relation_type, target_id)
            return ActionResult(
                command="add_sense_relation", success=True,
                message=f"Added sense {relation_type}: {source_id} → {target_id}",
                params=params,
            )
        except DuplicateEntityError:
            return ActionResult(
                command="add_sense_relation", success=True,
                message=f"Sense relation already exists (idempotent): {relation_type} {source_id} → {target_id}",
                params=params, skipped=True,
            )
        except EntityNotFoundError as e:
            return ActionResult(
                command="add_sense_relation", success=False,
                message=f"Missing entity: {e}",
                params=params, escalated=True,
                error=f"Source or target sense not found: {e}",
            )
        except (RelationError, ValidationError) as e:
            return ActionResult(
                command="add_sense_relation", success=False,
                message=f"Invalid relation: {e}",
                params=params, escalated=True,
                error=str(e),
            )

    def _exec_remove_sense_relation(self, params: dict) -> ActionResult:
        source_id = params.get("source_id", "")
        target_id = params.get("target_id", "")
        relation_type = params.get("relation_type", "")

        try:
            self.editor.remove_sense_relation(source_id, relation_type, target_id)
            return ActionResult(
                command="remove_sense_relation", success=True,
                message=f"Removed sense {relation_type}: {source_id} → {target_id}",
                params=params,
            )
        except EntityNotFoundError:
            return ActionResult(
                command="remove_sense_relation", success=True,
                message=f"Already absent (idempotent): {relation_type} {source_id} → {target_id}",
                params=params, skipped=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# ApplicationReport
# ═══════════════════════════════════════════════════════════════════════════════


class ApplicationReport:
    """Aggregate per-synset reports and produce a JSON manifest."""

    def __init__(self):
        self.reports: list[SynsetReport] = []
        self.start_time = datetime.now(timezone.utc)

    def add(self, report: SynsetReport) -> None:
        self.reports.append(report)

    @property
    def total_applied(self) -> int:
        return sum(r.actions_applied for r in self.reports)

    @property
    def total_skipped(self) -> int:
        return sum(r.actions_skipped for r in self.reports)

    @property
    def total_escalated(self) -> int:
        return sum(r.actions_escalated for r in self.reports)

    @property
    def total_failed(self) -> int:
        return sum(r.actions_failed for r in self.reports)

    def write(self, path: Optional[str]) -> None:
        if path is None:
            return
        manifest = {
            "timestamp": self.start_time.isoformat(),
            "duration_seconds": (
                datetime.now(timezone.utc) - self.start_time
            ).total_seconds(),
            "summary": {
                "synsets_processed": len(self.reports),
                "actions_applied": self.total_applied,
                "actions_skipped": self.total_skipped,
                "actions_escalated": self.total_escalated,
                "actions_failed": self.total_failed,
            },
            "synsets": [
                {
                    "synset_id": r.synset_id,
                    "yaml_source": r.yaml_source,
                    "applied": r.actions_applied,
                    "skipped": r.actions_skipped,
                    "escalated": r.actions_escalated,
                    "failed": r.actions_failed,
                    "errors": r.errors,
                    "results": [
                        {
                            "command": ar.command,
                            "success": ar.success,
                            "message": ar.message,
                            "skipped": ar.skipped,
                            "escalated": ar.escalated,
                            "error": ar.error,
                        }
                        for ar in r.results
                    ],
                }
                for r in self.reports
            ],
        }
        Path(path).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        logger.info("Manifest written to %s", path)

    def print_summary(self) -> None:
        failed_synsets = [r for r in self.reports if r.actions_failed > 0]
        escalated_synsets = [r for r in self.reports if r.actions_escalated > 0]

        print("\n" + "=" * 60)
        print("REVIEW APPLICATION SUMMARY")
        print("=" * 60)
        print(f"Synsets processed: {len(self.reports)}")
        print(f"Actions applied:   {self.total_applied}")
        print(f"Actions skipped:   {self.total_skipped}")
        print(f"Actions escalated: {self.total_escalated}")
        print(f"Actions failed:    {self.total_failed}")
        print(f"Duration:          {(datetime.now(timezone.utc) - self.start_time).total_seconds():.1f}s")

        if failed_synsets:
            print(f"\nFailed synsets ({len(failed_synsets)}):")
            for r in failed_synsets[:20]:
                print(f"  {r.synset_id}: {r.actions_failed} failures")
                for err in r.errors[:3]:
                    print(f"    - {err}")

        if escalated_synsets:
            print(f"\nEscalated synsets ({len(escalated_synsets)}):")
            for r in escalated_synsets[:20]:
                print(f"  {r.synset_id}: {r.actions_escalated} escalations")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline helpers
# ═══════════════════════════════════════════════════════════════════════════════


def normalize_command(action: ContextualAction) -> None:
    """Map Arabic command names to English equivalents, in place."""
    if action.command in ARABIC_COMMAND_MAP:
        action.command = ARABIC_COMMAND_MAP[action.command]


def filter_and_sort(
    actions: list[ContextualAction],
    report: SynsetReport,
) -> list[ContextualAction]:
    """Remove no-ops/escalations and sort by dependency order."""
    executable = []
    for action in actions:
        if action.command in NOOP_COMMANDS:
            report.actions_skipped += 1
            continue
        if action.command in ESCALATION_COMMANDS:
            report.actions_escalated += 1
            report.results.append(ActionResult(
                command=action.command, success=True,
                message=f"Escalated: {action.params}",
                params=action.params, escalated=True,
            ))
            continue
        executable.append(action)
    return sorted(executable, key=lambda a: COMMAND_ORDER.get(a.command, 99))


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════


def process_review(
    yaml_path: Path,
    editor: WordnetEditor,
    resolver: AutoResolver,
    dispatcher: ReviewDispatcher,
) -> SynsetReport:
    """Process a single review YAML file."""
    synset_id = ActionExtractor.extract_synset_id(yaml_path)
    report = SynsetReport(synset_id=synset_id, yaml_source=yaml_path.name)

    try:
        review_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception as e:
        report.record_error(f"YAML parse error: {e}")
        return report

    if not isinstance(review_data, dict):
        report.record_error("YAML root is not a dict")
        return report

    # Detect format and collect actions accordingly
    fmt = detect_review_format(review_data)
    if fmt == "v2":
        raw_actions = ActionExtractor.collect_actions_v2(review_data, synset_id, yaml_path)
    else:
        raw_actions = ActionExtractor.collect_actions(review_data, synset_id, yaml_path)
    if not raw_actions:
        return report

    # Normalize Arabic → English
    for action in raw_actions:
        normalize_command(action)

    # Filter no-ops/escalations and sort by dependency
    actions = filter_and_sort(raw_actions, report)
    if not actions:
        return report

    # Apply atomically per synset
    created_entries: dict[str, str] = {}
    try:
        with editor.batch():
            for action in actions:
                resolver.resolve_auto_ids(action, created_entries)
                result = dispatcher.dispatch(action, created_entries)
                report.record(result)
    except Exception as e:
        report.record_error(f"Batch error: {e}")
        logger.exception("Error processing %s", yaml_path.name)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply linguistic review actions to AWN4 via WordnetEditor v1.0.0",
    )
    parser.add_argument(
        "--reviews-dir", nargs="+", required=True,
        help="Directories containing .review.yaml files",
    )
    parser.add_argument(
        "--db", required=True,
        help="Path to the WordnetEditor SQLite database",
    )
    parser.add_argument(
        "--lexicon", default="awn4",
        help="Lexicon ID within the database (default: awn4)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and resolve but don't execute mutations",
    )
    parser.add_argument(
        "--no-copy", action="store_true",
        help="Modify the DB directly instead of auto-copying",
    )
    parser.add_argument(
        "--manifest", default=None,
        help="Path to write JSON manifest of results",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Run validation after applying all reviews",
    )
    parser.add_argument(
        "--export", default=None,
        help="Export the modified DB to WN-LMF XML at this path",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Collect all YAML files
    yaml_files: list[Path] = []
    for dir_path in args.reviews_dir:
        d = Path(dir_path)
        if not d.is_dir():
            logger.error("Not a directory: %s", d)
            sys.exit(1)
        yaml_files.extend(sorted(d.glob("*.review.yaml")))

    if not yaml_files:
        logger.error("No .review.yaml files found in %s", args.reviews_dir)
        sys.exit(1)

    # Deduplicate: when multiple sources review the same synset, keep the first.
    # Since --reviews-dir is ordered, place the preferred source first.
    seen_synsets: dict[str, Path] = {}
    deduped_files: list[Path] = []
    duplicates = 0
    for yf in yaml_files:
        synset_id = ActionExtractor.extract_synset_id(yf)
        if synset_id in seen_synsets:
            duplicates += 1
            logger.info(
                "Skipping duplicate %s (already from %s)",
                yf.name, seen_synsets[synset_id].name,
            )
            continue
        seen_synsets[synset_id] = yf
        deduped_files.append(yf)
    yaml_files = deduped_files

    print(f"Found {len(yaml_files)} unique review YAML files ({duplicates} duplicates skipped)")

    # Auto-copy DB for safety
    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        sys.exit(1)

    if not args.no_copy and not args.dry_run:
        dst = db_path.with_stem(db_path.stem + "_reviewed")
        print(f"Copying {db_path.name} -> {dst.name}")
        shutil.copy2(db_path, dst)
        db_path = dst

    # Open editor and apply
    with WordnetEditor(str(db_path)) as editor:
        resolver = AutoResolver(editor, args.lexicon)
        dispatcher = ReviewDispatcher(editor, args.lexicon, args.dry_run)
        app_report = ApplicationReport()

        for i, yaml_file in enumerate(yaml_files, 1):
            if i % 100 == 0 or i == len(yaml_files):
                print(f"  Processing {i}/{len(yaml_files)}: {yaml_file.name}")

            report = process_review(yaml_file, editor, resolver, dispatcher)
            app_report.add(report)

        # Optional: validate
        if args.validate:
            print("\nRunning validation...")
            issues = editor.validate(lexicon_id=args.lexicon)
            errors = [i for i in issues if i.severity == "error"]
            warnings = [i for i in issues if i.severity == "warning"]
            print(f"  Validation: {len(errors)} errors, {len(warnings)} warnings")
            if errors:
                for issue in errors[:20]:
                    print(f"  [ERROR] {issue.entity_id}: {issue.message}")

        # Optional: export
        if args.export:
            print(f"\nExporting to {args.export}...")
            editor.export_lmf(args.export)
            print("  Export complete.")

    # Write manifest and print summary
    app_report.write(args.manifest)
    app_report.print_summary()

    print(f"\nDatabase: {db_path}")


if __name__ == "__main__":
    main()
