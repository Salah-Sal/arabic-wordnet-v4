"""Apply linguistic review actions to AWN4 via wn-editor-extended.

Bridges the review pipeline's YAML output (structured review actions) to the
wn-editor-extended editor classes. Each review YAML contains an actions: list
with concrete edit commands (remove_sense, update_definition, add_synset_example,
etc.) that this module resolves, normalizes, and applies to the WordNet database.

Usage:
    python apply_reviews.py --reviews-dir output/reviews_claude_db \\
                            --db data/awn4_experiment.db \\
                            --lexicon awn4 \\
                            [--dry-run] [--manifest manifest.json]

Architecture:
    ActionExtractor    — Parse review YAML, collect actions with parent context
    ActionNormalizer   — Arabic→English commands, {auto} ID resolution, dep sort
    ReviewApplicator   — Map actions to editor methods, wrap in tracking_session
    ApplicationReport  — JSON manifest of applied/skipped/failed/escalated
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Arabic command → English command normalization map
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

# Commands that are no-ops (affirmations/confirmations)
NOOP_COMMANDS = {"_noop", "retain_definition"}

# Commands that are log-only (not DB edits)
ESCALATION_COMMANDS = {"escalate"}

# Valid WN-LMF relation type names (from wn_editor.batch.schema.RELATION_TYPES)
VALID_RELATION_TYPES = {
    "also", "antonym", "attribute", "causes", "derivation",
    "domain_region", "domain_topic", "entails", "exemplifies",
    "has_domain_region", "has_domain_topic",
    "holo_member", "holo_part", "holo_substance",
    "hypernym", "hyponym", "instance_hypernym", "instance_hyponym",
    "is_caused_by", "is_entailed_by", "is_exemplified_by",
    "mero_member", "mero_part", "mero_substance",
    "other", "participle", "pertainym", "similar",
}

# Dependency ordering: lower number = applied first
COMMAND_ORDER = {
    "remove_sense": 0,
    "remove_synset_relation": 1,
    "create_entry": 2,
    "add_sense": 3,
    "update_definition": 4,
    "add_definition": 5,
    "add_synset_example": 6,
    "add_sense_example": 7,
    "add_synset_relation": 8,
    "set_metadata": 9,
    "set_confidence": 10,
    "move_sense": 1,  # alongside remove operations
}

# Pattern for {auto}, {auto:hint}, {auto-hint}, {auto — long hint}
AUTO_ID_RE = re.compile(r"^\{auto(?:\s*[:\-–—]\s*(.+?))?\s*\}$")

# Pattern for placeholder synset IDs like {synset_for_جزء}
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
    timestamp_start: str = ""
    timestamp_end: str = ""
    actions_applied: int = 0
    actions_skipped: int = 0
    actions_escalated: int = 0
    actions_failed: int = 0
    results: list[dict] = field(default_factory=list)
    skipped_reasons: list[str] = field(default_factory=list)
    escalation_reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# ActionExtractor
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
        # Match hint against step5_lemmas (diacritic-insensitive)
        bare_hint = strip_tashkeel(hint)
        for lm in step5_lemmas:
            if strip_tashkeel(lm) == bare_hint:
                return lm
        # Return hint as-is if no exact match (will be used for lookup)
        return hint

    # Strategy 5: single-lemma fallback
    if len(step5_lemmas) == 1:
        return step5_lemmas[0]

    return None


class ActionExtractor:
    """Parse review YAML and collect all actions with parent context."""

    @staticmethod
    def extract_synset_id(yaml_path: Path) -> str:
        """Extract synset ID from the YAML filename."""
        # e.g., awn4-00001740-n.review.yaml → awn4-00001740-n
        return yaml_path.name.replace(".review.yaml", "")

    @staticmethod
    def collect_actions(
        review_data: dict,
        synset_id: str,
        yaml_path: Path,
    ) -> list[ContextualAction]:
        """Walk the review YAML structure and extract all actions with context.

        Actions can appear in:
        - step1_lemma_validation.per_lemma[].actions
        - step3_definition.actions
        - step4_relations.actions
        - step5_enrichment.actions
        - step5_enrichment.per_lemma[].actions (sense-level examples)
        - top-level actions: (older format with YAML anchors)
        """
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
                            params=action.get("params", {}),
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
                        params=action.get("params", {}),
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
                        params=action.get("params", {}),
                        synset_id=synset_id,
                        source_step="step4",
                        yaml_path=str(yaml_path),
                    ))

        # Step 5: enrichment (per-lemma + synset-level actions)
        step5 = review_data.get("step5_enrichment", {})
        if isinstance(step5, dict):
            # Build example text → lemma map for inferring parent lemma
            # on synset-level actions that have {auto} sense IDs
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
                            params=action.get("params", {}),
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
            # Build enrichment key → lemma map (for set_metadata inference)
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
                        action,
                        example_to_lemma,
                        enrichment_key_to_lemma,
                        step5_lemmas,
                    )
                    all_actions.append(ContextualAction(
                        command=action.get("command", ""),
                        params=action.get("params", {}),
                        parent_lemma=inferred_lemma,
                        synset_id=synset_id,
                        source_step="step5",
                        yaml_path=str(yaml_path),
                    ))

        # Top-level actions: (older format with YAML anchors)
        for action in review_data.get("actions", []):
            if isinstance(action, dict):
                all_actions.append(ContextualAction(
                    command=action.get("command", ""),
                    params=action.get("params", {}),
                    synset_id=synset_id,
                    source_step="top_level",
                    yaml_path=str(yaml_path),
                ))

        return all_actions


# ═══════════════════════════════════════════════════════════════════════════════
# ActionNormalizer
# ═══════════════════════════════════════════════════════════════════════════════

class ActionNormalizer:
    """Normalize commands, resolve {auto} IDs, sort by dependency."""

    def __init__(self, lexicon_id: str):
        self.lexicon_id = lexicon_id

    def normalize_command(self, action: ContextualAction) -> ContextualAction:
        """Map Arabic command names to English equivalents."""
        cmd = action.command
        if cmd in ARABIC_COMMAND_MAP:
            action.command = ARABIC_COMMAND_MAP[cmd]
        return action

    def resolve_auto_ids(
        self,
        action: ContextualAction,
        created_entries: dict[str, Any],
    ) -> ContextualAction:
        """Resolve {auto} IDs using wn lookups and recently created entries.

        Args:
            action: The action with potential {auto} params.
            created_entries: Map of lemma → (entry_rowid, entry_id) for entries
                             created earlier in the same synset's action batch.
        """
        import wn

        params = action.params
        synset_id = action.synset_id or params.get("synset_id", "")
        lemma = action.parent_lemma or ""

        # --- sense_id: "{auto}" or "{auto:lemma_hint}" ---
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
                    resolved = self._resolve_entry_id(hint)
                    if resolved is not None:
                        params["entry_id"] = resolved
                    else:
                        params["_unresolved_entry"] = True
                        logger.warning(
                            "Could not resolve entry_id {auto} for lemma=%r",
                            hint,
                        )

        # --- entity_id: "{auto}" or "{auto:hint}" (set_metadata / set_confidence) ---
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

        return action

    def _resolve_sense_id(self, lemma: str, synset_id: str) -> Optional[Any]:
        """Find a wn.Sense object for the given lemma in the given synset."""
        import wn

        try:
            senses = wn.senses(form=lemma, lexicon=self.lexicon_id)
            for sense in senses:
                if sense.synset().id() == synset_id:
                    return sense
        except Exception as e:
            logger.debug("Sense lookup failed for %r in %s: %s", lemma, synset_id, e)
        return None

    def _resolve_entry_id(self, lemma: str) -> Optional[int]:
        """Find the entry row ID for the given lemma."""
        import wn
        from wn_editor import get_row_id

        try:
            words = wn.words(form=lemma, lexicon=self.lexicon_id)
            if words:
                word = words[0]
                # Get the internal row ID for the entry
                word_id = word.id()
                return get_row_id("entries", {"id": word_id})
        except Exception as e:
            logger.debug("Entry lookup failed for %r: %s", lemma, e)
        return None

    @staticmethod
    def sort_actions(actions: list[ContextualAction]) -> list[ContextualAction]:
        """Sort actions by dependency order within a synset."""
        return sorted(
            actions,
            key=lambda a: COMMAND_ORDER.get(a.command, 99),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewApplicator
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewApplicator:
    """Map review actions to wn-editor-extended editor calls."""

    def __init__(self, lexicon_id: str, dry_run: bool = False):
        self.lexicon_id = lexicon_id
        self.dry_run = dry_run
        self.normalizer = ActionNormalizer(lexicon_id)

    def apply_review(
        self,
        yaml_path: Path,
        review_data: dict,
    ) -> SynsetReport:
        """Apply all actions from a single review YAML."""
        import wn
        from wn_editor import (
            SynsetEditor, SenseEditor, EntryEditor,
            LexiconEditor, RelationType,
            tracking_session, enable_tracking, is_tracking_enabled,
        )
        from wn_editor.changelog import pre_change_hook, post_change_hook
        from wn_editor import set_changelog_hooks, clear_changelog_hooks

        synset_id = ActionExtractor.extract_synset_id(yaml_path)
        report = SynsetReport(
            synset_id=synset_id,
            yaml_source=yaml_path.name,
        )

        # Extract all actions
        raw_actions = ActionExtractor.collect_actions(
            review_data, synset_id, yaml_path,
        )
        if not raw_actions:
            logger.info("No actions found in %s", yaml_path.name)
            return report

        # Normalize commands (Arabic → English)
        for action in raw_actions:
            self.normalizer.normalize_command(action)

        # Filter out no-ops and escalations
        executable_actions = []
        for action in raw_actions:
            if action.command in NOOP_COMMANDS:
                report.actions_skipped += 1
                report.skipped_reasons.append(
                    f"No-op: {action.command}"
                )
                continue
            if action.command in ESCALATION_COMMANDS:
                report.actions_escalated += 1
                report.escalation_reasons.append(
                    f"Escalated: {action.params}"
                )
                continue
            executable_actions.append(action)

        if not executable_actions:
            logger.info("No executable actions in %s", yaml_path.name)
            return report

        # Sort by dependency order
        executable_actions = ActionNormalizer.sort_actions(executable_actions)

        # Apply within a tracking session
        report.timestamp_start = datetime.now(timezone.utc).isoformat()

        session_name = f"review:{synset_id}"
        session_desc = f"Applying linguistic review from {yaml_path.name}"

        if not self.dry_run:
            if not is_tracking_enabled():
                enable_tracking()
            set_changelog_hooks(pre_change_hook, post_change_hook)

        try:
            if self.dry_run:
                for action in executable_actions:
                    result = self._dry_run_action(action)
                    self._record_result(report, result)
            else:
                with tracking_session(session_name, session_desc):
                    created_entries: dict[str, Any] = {}
                    for action in executable_actions:
                        # Resolve {auto} IDs (needs created_entries for
                        # create_entry → add_sense chains)
                        self.normalizer.resolve_auto_ids(action, created_entries)
                        result = self._apply_action(action, created_entries)
                        self._record_result(report, result)

                    # Set synset-level review metadata
                    self._set_review_metadata(synset_id, yaml_path.name, report)
        except Exception as e:
            logger.exception("Session-level error applying %s", yaml_path.name)
            report.errors.append(f"Session error: {e}")
        finally:
            if not self.dry_run:
                clear_changelog_hooks()

        report.timestamp_end = datetime.now(timezone.utc).isoformat()
        return report

    def _apply_action(
        self,
        action: ContextualAction,
        created_entries: dict[str, Any],
    ) -> ActionResult:
        """Dispatch a single action to the appropriate editor method."""
        cmd = action.command
        params = action.params

        # Check for unresolved IDs
        if params.get("_unresolved_sense") or params.get("_unresolved_entry") \
                or params.get("_unresolved_entity"):
            return ActionResult(
                command=cmd,
                success=False,
                message="Unresolved {auto} ID",
                params=params,
                error="Could not resolve {auto} to a concrete ID",
            )

        try:
            if cmd == "remove_sense":
                return self._exec_remove_sense(params)
            elif cmd == "update_definition":
                return self._exec_update_definition(params)
            elif cmd == "add_definition":
                return self._exec_add_definition(params)
            elif cmd == "add_synset_example":
                return self._exec_add_synset_example(params)
            elif cmd == "add_sense_example":
                return self._exec_add_sense_example(params)
            elif cmd == "create_entry":
                return self._exec_create_entry(params, action, created_entries)
            elif cmd == "add_sense":
                return self._exec_add_sense(params)
            elif cmd == "set_metadata":
                return self._exec_set_metadata(params)
            elif cmd == "set_confidence":
                return self._exec_set_confidence(params)
            elif cmd == "add_synset_relation":
                return self._exec_add_synset_relation(params)
            elif cmd == "remove_synset_relation":
                return self._exec_remove_synset_relation(params)
            elif cmd == "move_sense":
                return self._exec_move_sense(params)
            elif cmd == "create_entry_and_add_sense":
                return self._exec_create_entry_and_add_sense(
                    params, action, created_entries,
                )
            else:
                return ActionResult(
                    command=cmd,
                    success=False,
                    message=f"Unknown command: {cmd}",
                    params=params,
                    skipped=True,
                )
        except Exception as e:
            logger.exception("Error executing %s", cmd)
            return ActionResult(
                command=cmd,
                success=False,
                message=f"Error: {e}",
                params=params,
                error=str(e),
            )

    # ─── Individual command executors ─────────────────────────────────────

    def _exec_remove_sense(self, params: dict) -> ActionResult:
        """Remove a sense (sense_id must be resolved to a wn.Sense)."""
        from wn_editor import SenseEditor

        sense = params.get("sense_id")
        if sense is None:
            return ActionResult(
                command="remove_sense", success=False,
                message="No sense_id", params=params,
                error="sense_id is None",
            )

        sense_editor = SenseEditor(sense)
        sense_editor.delete()
        return ActionResult(
            command="remove_sense", success=True,
            message=f"Removed sense {sense.id()}", params=params,
        )

    def _exec_update_definition(self, params: dict) -> ActionResult:
        """Update (modify) an existing definition by index."""
        import wn
        from wn_editor import SynsetEditor

        synset_id = params.get("synset_id", "")
        text = params.get("text", "")
        def_index = params.get("definition_index", 0)

        synset = wn.synset(id=synset_id, lexicon=self.lexicon_id)

        # Idempotency: check if definition already matches
        existing_defs = synset.definitions()
        if def_index < len(existing_defs) and existing_defs[def_index] == text:
            return ActionResult(
                command="update_definition", success=True,
                message="Definition already matches (idempotent skip)",
                params=params, skipped=True,
            )

        editor = SynsetEditor(synset)
        editor.mod_definition(text, indx=def_index)
        return ActionResult(
            command="update_definition", success=True,
            message=f"Updated definition[{def_index}] on {synset_id}",
            params=params,
        )

    def _exec_add_definition(self, params: dict) -> ActionResult:
        """Add a new definition to a synset."""
        import wn
        from wn_editor import SynsetEditor

        synset_id = params.get("synset_id", "")
        text = params.get("text", "")

        synset = wn.synset(id=synset_id, lexicon=self.lexicon_id)

        # Idempotency: check if definition already exists
        if text in synset.definitions():
            return ActionResult(
                command="add_definition", success=True,
                message="Definition already exists (idempotent skip)",
                params=params, skipped=True,
            )

        editor = SynsetEditor(synset)
        editor.add_definition(text)
        return ActionResult(
            command="add_definition", success=True,
            message=f"Added definition to {synset_id}", params=params,
        )

    def _exec_add_synset_example(self, params: dict) -> ActionResult:
        """Add an example to a synset."""
        import wn
        from wn_editor import SynsetEditor

        synset_id = params.get("synset_id", "")
        text = params.get("text", "")

        synset = wn.synset(id=synset_id, lexicon=self.lexicon_id)

        # Idempotency: check if example already exists
        if text in synset.examples():
            return ActionResult(
                command="add_synset_example", success=True,
                message="Example already exists (idempotent skip)",
                params=params, skipped=True,
            )

        editor = SynsetEditor(synset)
        editor.add_example(text)
        return ActionResult(
            command="add_synset_example", success=True,
            message=f"Added example to {synset_id}", params=params,
        )

    def _exec_add_sense_example(self, params: dict) -> ActionResult:
        """Add an example to a specific sense."""
        from wn_editor import SenseEditor

        sense = params.get("sense_id")
        text = params.get("text", "")

        if sense is None:
            return ActionResult(
                command="add_sense_example", success=False,
                message="No sense_id", params=params,
                error="sense_id is None",
            )

        # Idempotency: check if example already exists
        if text in sense.examples():
            return ActionResult(
                command="add_sense_example", success=True,
                message="Example already exists (idempotent skip)",
                params=params, skipped=True,
            )

        editor = SenseEditor(sense)
        editor.add_example(text)
        return ActionResult(
            command="add_sense_example", success=True,
            message=f"Added example to sense {sense.id()}", params=params,
        )

    def _exec_create_entry(
        self,
        params: dict,
        action: ContextualAction,
        created_entries: dict[str, Any],
    ) -> ActionResult:
        """Create a new lexical entry (word) in the lexicon."""
        from wn_editor import EntryEditor, LexiconEditor, get_row_id

        lemma = params.get("lemma", "")
        pos = params.get("pos", "n")

        # Get lexicon row ID
        lex_rowid = get_row_id("lexicons", {"id": self.lexicon_id})

        # Create new entry
        entry_editor = EntryEditor(lex_rowid, exists=False)
        if pos:
            entry_editor.set_pos(pos)
        entry_editor.add_form(lemma)

        # Store for later {auto} resolution in add_sense
        created_entries[lemma] = entry_editor.entry_id

        return ActionResult(
            command="create_entry", success=True,
            message=f"Created entry for '{lemma}' (id={entry_editor.entry_id})",
            params=params,
        )

    def _exec_add_sense(self, params: dict) -> ActionResult:
        """Add a sense linking an entry to a synset."""
        import wn
        from wn_editor import SenseEditor, get_row_id

        entry_id = params.get("entry_id")
        synset_id = params.get("synset_id", "")

        if entry_id is None:
            return ActionResult(
                command="add_sense", success=False,
                message="No entry_id", params=params,
                error="entry_id is None",
            )

        # entry_id is a row ID (int) from create_entry or resolution
        entry_rowid = entry_id

        # Get synset row ID
        synset = wn.synset(id=synset_id, lexicon=self.lexicon_id)
        synset_rowid = get_row_id("synsets", {"id": synset_id})

        # Get lexicon row ID
        lex_rowid = get_row_id("lexicons", {"id": self.lexicon_id})

        sense_editor = SenseEditor(
            lexicon_rowid=lex_rowid,
            entry_rowid=entry_rowid,
            synset_rowid=synset_rowid,
        )

        return ActionResult(
            command="add_sense", success=True,
            message=f"Added sense entry={entry_rowid} → synset={synset_id}",
            params=params,
        )

    def _exec_create_entry_and_add_sense(
        self,
        params: dict,
        action: ContextualAction,
        created_entries: dict[str, Any],
    ) -> ActionResult:
        """Combined create_entry + add_sense (from Arabic command shorthand)."""
        # First create the entry
        create_result = self._exec_create_entry(params, action, created_entries)
        if not create_result.success:
            return create_result

        # Then add the sense
        lemma = params.get("lemma", "")
        synset_id = action.synset_id or params.get("synset_id", "")
        sense_params = {
            "entry_id": created_entries.get(lemma),
            "synset_id": synset_id,
        }
        return self._exec_add_sense(sense_params)

    def _exec_set_metadata(self, params: dict) -> ActionResult:
        """Set metadata on a synset, sense, or entry."""
        import wn
        from wn_editor import SynsetEditor, SenseEditor, EntryEditor

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

        metadata = {key: value}

        if entity_type == "synset":
            if isinstance(entity_id, str):
                synset = wn.synset(id=entity_id, lexicon=self.lexicon_id)
                editor = SynsetEditor(synset)
            else:
                return ActionResult(
                    command="set_metadata", success=False,
                    message=f"Invalid synset entity_id type: {type(entity_id)}",
                    params=params, error="Invalid entity_id",
                )
            editor.set_metadata(metadata)
        elif entity_type == "sense":
            # entity_id should be a resolved wn.Sense
            editor = SenseEditor(entity_id)
            editor.set_metadata(metadata)
        elif entity_type == "entry":
            # entity_id should be a row ID (int)
            editor = EntryEditor(entity_id)
            editor.set_metadata(metadata)
        else:
            return ActionResult(
                command="set_metadata", success=False,
                message=f"Unknown entity_type: {entity_type}",
                params=params, error=f"Unknown entity_type: {entity_type}",
            )

        return ActionResult(
            command="set_metadata", success=True,
            message=f"Set {key}={value} on {entity_type}",
            params=params,
        )

    def _exec_set_confidence(self, params: dict) -> ActionResult:
        """Set confidence score via metadata (dc:confidence)."""
        # Implemented as set_metadata with dc:confidence key
        entity_type = params.get("entity_type", "")
        entity_id = params.get("entity_id")
        score = params.get("score", 0.0)

        meta_params = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "key": "dc:confidence",
            "value": str(score),
        }
        result = self._exec_set_metadata(meta_params)
        result.command = "set_confidence"
        return result

    def _exec_add_synset_relation(self, params: dict) -> ActionResult:
        """Add a relation between two synsets."""
        import wn
        from wn_editor import SynsetEditor, RelationType
        from wn_editor.batch.schema import RELATION_TYPES

        source_id = params.get("source_id", "")
        target_id = params.get("target_id", "")
        relation_type = params.get("relation_type", "")

        # Check for placeholder targets like {synset_for_جزء}
        if PLACEHOLDER_TARGET_RE.match(target_id):
            return ActionResult(
                command="add_synset_relation", success=False,
                message=f"Placeholder target: {target_id}",
                params=params, escalated=True,
                error=f"Cannot resolve placeholder target: {target_id}",
            )

        # Validate relation type
        if relation_type not in VALID_RELATION_TYPES:
            return ActionResult(
                command="add_synset_relation", success=False,
                message=f"Invalid relation type: {relation_type}",
                params=params, escalated=True,
                error=f"Invalid relation type: {relation_type}",
            )

        rel_type_id = RELATION_TYPES[relation_type]

        source = wn.synset(id=source_id, lexicon=self.lexicon_id)
        target = wn.synset(id=target_id, lexicon=self.lexicon_id)

        editor = SynsetEditor(source)
        editor.set_relation_to_synset(target, rel_type_id)

        return ActionResult(
            command="add_synset_relation", success=True,
            message=f"Added {relation_type}: {source_id} → {target_id}",
            params=params,
        )

    def _exec_remove_synset_relation(self, params: dict) -> ActionResult:
        """Remove a relation between two synsets."""
        import wn
        from wn_editor import SynsetEditor
        from wn_editor.batch.schema import RELATION_TYPES

        source_id = params.get("source_id", "")
        target_id = params.get("target_id", "")
        relation_type = params.get("relation_type", "")

        if relation_type not in VALID_RELATION_TYPES:
            return ActionResult(
                command="remove_synset_relation", success=False,
                message=f"Invalid relation type: {relation_type}",
                params=params, error=f"Invalid relation type: {relation_type}",
            )

        rel_type_id = RELATION_TYPES[relation_type]

        source = wn.synset(id=source_id, lexicon=self.lexicon_id)
        target = wn.synset(id=target_id, lexicon=self.lexicon_id)

        editor = SynsetEditor(source)
        editor.delete_relation_to_synset(target, rel_type_id)

        return ActionResult(
            command="remove_synset_relation", success=True,
            message=f"Removed {relation_type}: {source_id} → {target_id}",
            params=params,
        )

    def _exec_move_sense(self, params: dict) -> ActionResult:
        """Move a sense from one synset to another (delete + recreate)."""
        import wn
        from wn_editor import SenseEditor, get_row_id

        sense = params.get("sense_id")
        target_synset_id = params.get("target_synset_id", "")

        if sense is None:
            return ActionResult(
                command="move_sense", success=False,
                message="No sense_id", params=params,
                error="sense_id is None",
            )

        # Check if target is {auto} / placeholder
        if isinstance(target_synset_id, str) and PLACEHOLDER_TARGET_RE.match(target_synset_id):
            return ActionResult(
                command="move_sense", success=False,
                message=f"Placeholder target: {target_synset_id}",
                params=params, escalated=True,
                error=f"Cannot resolve placeholder target: {target_synset_id}",
            )

        # Capture entry info before deleting
        entry_rowid = sense._entry_id
        lex_rowid = get_row_id("lexicons", {"id": self.lexicon_id})
        target_synset_rowid = get_row_id("synsets", {"id": target_synset_id})

        # Delete old sense
        SenseEditor(sense).delete()

        # Create new sense in target synset
        SenseEditor(
            lexicon_rowid=lex_rowid,
            entry_rowid=entry_rowid,
            synset_rowid=target_synset_rowid,
        )

        return ActionResult(
            command="move_sense", success=True,
            message=f"Moved sense to {target_synset_id}",
            params=params,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _dry_run_action(self, action: ContextualAction) -> ActionResult:
        """Simulate an action without touching the DB."""
        return ActionResult(
            command=action.command,
            success=True,
            message=f"[DRY RUN] Would execute: {action.command}",
            params=action.params,
        )

    def _set_review_metadata(
        self, synset_id: str, yaml_name: str, report: SynsetReport,
    ) -> None:
        """Set review-tracking metadata on the synset."""
        import wn
        from wn_editor import SynsetEditor

        status = "reviewed"
        if report.actions_failed > 0:
            status = "partial"
        if report.actions_escalated > 0 and report.actions_applied == 0:
            status = "escalated"

        synset = wn.synset(id=synset_id, lexicon=self.lexicon_id)
        editor = SynsetEditor(synset)
        editor.set_metadata({
            "review_status": status,
            "review_source": yaml_name,
            "review_applied_at": datetime.now(timezone.utc).isoformat(),
            "review_version": "claude_db_v1",
        })

    @staticmethod
    def _record_result(report: SynsetReport, result: ActionResult) -> None:
        """Record an ActionResult into the SynsetReport."""
        entry = {
            "command": result.command,
            "success": result.success,
            "message": result.message,
        }
        if result.error:
            entry["error"] = result.error

        report.results.append(entry)

        if result.escalated:
            report.actions_escalated += 1
            report.escalation_reasons.append(result.message)
        elif result.skipped:
            report.actions_skipped += 1
            report.skipped_reasons.append(result.message)
        elif result.success:
            report.actions_applied += 1
        else:
            report.actions_failed += 1
            report.errors.append(result.message)


# ═══════════════════════════════════════════════════════════════════════════════
# ApplicationReport
# ═══════════════════════════════════════════════════════════════════════════════

class ApplicationReport:
    """Build and write the application manifest JSON."""

    def __init__(self, db_path: str, lexicon_id: str):
        self.db_path = db_path
        self.lexicon_id = lexicon_id
        self.sessions: list[dict] = []
        self.start_time = datetime.now(timezone.utc).isoformat()

    def add_synset_report(self, report: SynsetReport) -> None:
        self.sessions.append({
            "synset_id": report.synset_id,
            "yaml_source": report.yaml_source,
            "timestamp_start": report.timestamp_start,
            "timestamp_end": report.timestamp_end,
            "actions_applied": report.actions_applied,
            "actions_skipped": report.actions_skipped,
            "actions_escalated": report.actions_escalated,
            "actions_failed": report.actions_failed,
            "skipped_reasons": report.skipped_reasons,
            "escalation_reasons": report.escalation_reasons,
            "errors": report.errors,
        })

    def build_manifest(self) -> dict:
        total = len(self.sessions)
        applied = sum(1 for s in self.sessions if s["actions_failed"] == 0 and s["actions_applied"] > 0)
        partial = sum(1 for s in self.sessions if s["actions_failed"] > 0)
        escalated = sum(
            1 for s in self.sessions
            if s["actions_escalated"] > 0 and s["actions_applied"] == 0
        )
        skipped_only = total - applied - partial - escalated

        return {
            "applied_at": self.start_time,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "source_db": self.db_path,
            "lexicon": self.lexicon_id,
            "sessions": self.sessions,
            "summary": {
                "total_synsets": total,
                "fully_applied": applied,
                "partial": partial,
                "escalated_only": escalated,
                "skipped_only": skipped_only,
                "total_actions_applied": sum(s["actions_applied"] for s in self.sessions),
                "total_actions_skipped": sum(s["actions_skipped"] for s in self.sessions),
                "total_actions_escalated": sum(s["actions_escalated"] for s in self.sessions),
                "total_actions_failed": sum(s["actions_failed"] for s in self.sessions),
            },
        }

    def write(self, path: Path) -> None:
        manifest = self.build_manifest()
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Manifest written to %s", path)


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def apply_all_reviews(
    reviews_dir: Path,
    db_path: str,
    lexicon_id: str,
    manifest_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Apply all review YAMLs in a directory to the WordNet database.

    Args:
        reviews_dir: Directory containing *.review.yaml files.
        db_path: Path to the wn SQLite database (must be pre-loaded).
        lexicon_id: Lexicon identifier (e.g., "awn4").
        manifest_path: Where to write the JSON manifest.
        dry_run: If True, simulate without making changes.

    Returns:
        The manifest dict.
    """
    applicator = ReviewApplicator(lexicon_id=lexicon_id, dry_run=dry_run)
    report = ApplicationReport(db_path=db_path, lexicon_id=lexicon_id)

    yaml_files = sorted(reviews_dir.glob("*.review.yaml"))
    total = len(yaml_files)
    logger.info("Found %d review YAMLs in %s", total, reviews_dir)

    for i, yaml_path in enumerate(yaml_files, 1):
        logger.info("[%d/%d] Processing %s", i, total, yaml_path.name)
        try:
            review_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if not isinstance(review_data, dict):
                logger.warning("Skipping %s: not a valid YAML dict", yaml_path.name)
                continue
        except yaml.YAMLError as e:
            logger.error("YAML parse error in %s: %s", yaml_path.name, e)
            continue

        synset_report = applicator.apply_review(yaml_path, review_data)
        report.add_synset_report(synset_report)

        logger.info(
            "  → applied=%d skipped=%d escalated=%d failed=%d",
            synset_report.actions_applied,
            synset_report.actions_skipped,
            synset_report.actions_escalated,
            synset_report.actions_failed,
        )

    manifest = report.build_manifest()
    summary = manifest["summary"]
    logger.info(
        "Done. %d synsets processed: %d fully applied, %d partial, "
        "%d escalated, %d skipped",
        summary["total_synsets"],
        summary["fully_applied"],
        summary["partial"],
        summary["escalated_only"],
        summary["skipped_only"],
    )

    if manifest_path:
        report.write(manifest_path)

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Apply linguistic review actions to AWN4",
    )
    parser.add_argument(
        "--reviews-dir",
        type=Path,
        required=True,
        help="Directory containing *.review.yaml files",
    )
    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="Path to the wn SQLite database",
    )
    parser.add_argument(
        "--lexicon",
        type=str,
        default="awn4",
        help="Lexicon ID in the database",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path for output JSON manifest",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without making changes",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    manifest_path = args.manifest
    if manifest_path is None:
        manifest_path = args.reviews_dir / "application_manifest.json"

    manifest = apply_all_reviews(
        reviews_dir=args.reviews_dir,
        db_path=args.db,
        lexicon_id=args.lexicon,
        manifest_path=manifest_path,
        dry_run=args.dry_run,
    )

    # Print summary to stdout
    summary = manifest["summary"]
    print(f"\nApplication complete:")
    print(f"  Synsets:  {summary['total_synsets']}")
    print(f"  Applied:  {summary['total_actions_applied']}")
    print(f"  Skipped:  {summary['total_actions_skipped']}")
    print(f"  Escalated: {summary['total_actions_escalated']}")
    print(f"  Failed:   {summary['total_actions_failed']}")
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()
