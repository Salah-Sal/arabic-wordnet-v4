# WordnetEditor — Single Editing Actions Reference

Complete catalogue of all mutation methods on `WordnetEditor`. Excludes read-only methods (get/find/list), validation, history queries, and import/export.

---

## Synset (3 actions)

| # | Method | What it does |
|---|--------|--------------|
| 4 | `create_synset(lexicon_id, pos, definition, *, id=None, ili=None, ili_definition=None, lexicalized=True, metadata=None)` | Create a synset with its initial definition. |
| 5 | `update_synset(synset_id, *, pos=None, metadata=_UNSET)` | Update POS or metadata. |
| 6 | `delete_synset(synset_id, cascade=False)` | Delete a synset. With `cascade=True`, also deletes all attached senses. Without cascade, raises `RelationError` if senses exist. |

---

## Entry (4 actions)

| # | Method | What it does |
|---|--------|--------------|
| 7 | `create_entry(lexicon_id, lemma, pos, *, id=None, forms=None, metadata=None)` | Create a new lexical entry (word + POS). |
| 8 | `update_entry(entry_id, *, pos=None, metadata=_UNSET)` | Update POS or metadata. |
| 9 | `delete_entry(entry_id, cascade=False)` | Delete an entry. With `cascade=True`, also deletes all attached senses. Without cascade, raises `RelationError` if senses exist. |
| 10 | `update_lemma(entry_id, new_lemma)` | Change the canonical written form of an entry. |

---

## Form (2 actions)

| # | Method | What it does |
|---|--------|--------------|
| 11 | `add_form(entry_id, written_form, *, id=None, script=None, tags=None)` | Add an inflected or variant written form to an entry. |
| 12 | `remove_form(entry_id, written_form)` | Remove a non-lemma form from an entry. The lemma form (rank 0) cannot be removed. |

---

## Sense (4 actions)

| # | Method | What it does |
|---|--------|--------------|
| 13 | `add_sense(entry_id, synset_id, *, id=None, lexicalized=True, adjposition=None, metadata=None)` | Link an entry to a synset by creating a new sense. |
| 14 | `remove_sense(sense_id)` | Delete a sense and its relations, examples, and counts. If the synset has no remaining senses, it becomes unlexicalized. |
| 15 | `move_sense(sense_id, target_synset_id)` | Move a sense from its current synset to a different synset. Source synset becomes unlexicalized if emptied; target becomes lexicalized if it was unlexicalized. |
| 16 | `reorder_senses(entry_id, sense_id_order)` | Set the ordering of senses within an entry. Requires a complete list of all sense IDs in the desired order. |

---

## Definition (3 actions)

| # | Method | What it does |
|---|--------|--------------|
| 17 | `add_definition(synset_id, text, *, language=None, source_sense=None, metadata=None)` | Add a definition to a synset. |
| 18 | `update_definition(synset_id, definition_index, text)` | Replace a definition's text by its zero-based index. |
| 19 | `remove_definition(synset_id, definition_index)` | Remove a definition by its zero-based index. |

---

## Example (4 actions)

| # | Method | What it does |
|---|--------|--------------|
| 20 | `add_synset_example(synset_id, text, *, language=None, metadata=None)` | Add a usage example to a synset. |
| 21 | `remove_synset_example(synset_id, example_index)` | Remove a synset example by its zero-based index. |
| 22 | `add_sense_example(sense_id, text, *, language=None, metadata=None)` | Add a usage example to a sense. |
| 23 | `remove_sense_example(sense_id, example_index)` | Remove a sense example by its zero-based index. |

---

## Relation (6 actions)

All relation-add methods silently ignore duplicates. Synset and sense relations support automatic inverse creation via the `auto_inverse` parameter (default `True`).

| # | Method | What it does |
|---|--------|--------------|
| 24 | `add_synset_relation(source_id, relation_type, target_id, *, auto_inverse=True, metadata=None)` | Add a directed synset-to-synset relation. When `auto_inverse=True`, the inverse (e.g. `hyponym` for `hypernym`) is also created. |
| 25 | `remove_synset_relation(source_id, relation_type, target_id, *, auto_inverse=True)` | Remove a directed synset-to-synset relation. No-op if it doesn't exist. |
| 26 | `add_sense_relation(source_id, relation_type, target_id, *, auto_inverse=True, metadata=None)` | Add a directed sense-to-sense relation. Auto-inverse supported. |
| 27 | `remove_sense_relation(source_id, relation_type, target_id, *, auto_inverse=True)` | Remove a directed sense-to-sense relation. No-op if it doesn't exist. |
| 28 | `add_sense_synset_relation(source_sense_id, relation_type, target_synset_id, *, metadata=None)` | Add a relation from a sense to a synset. No auto-inverse (cross-type). |
| 29 | `remove_sense_synset_relation(source_sense_id, relation_type, target_synset_id)` | Remove a relation from a sense to a synset. No-op if it doesn't exist. |

---

## ILI (3 actions)

| # | Method | What it does |
|---|--------|--------------|
| 30 | `link_ili(synset_id, ili_id)` | Link a synset to an existing ILI entry. Raises `ValidationError` if the synset already has an ILI. |
| 31 | `unlink_ili(synset_id)` | Remove the ILI mapping (or proposed ILI) from a synset. |
| 32 | `propose_ili(synset_id, definition, *, metadata=None)` | Propose a new ILI entry for a synset. Definition must be at least 20 characters. |

---

## Metadata (2 actions)

| # | Method | What it does |
|---|--------|--------------|
| 33 | `set_metadata(entity_type, entity_id, key, value)` | Set or delete a single metadata key on any entity (`"lexicon"`, `"synset"`, `"entry"`, `"sense"`). Pass `None` as value to delete the key. |
| 34 | `set_confidence(entity_type, entity_id, score)` | Convenience method to set the `confidenceScore` metadata key. |

---

## Compound Operations (2 actions)

These are multi-step operations executed atomically within a single transaction.

| # | Method | What it does |
|---|--------|--------------|
| 35 | `merge_synsets(source_id, target_id)` | Merge source synset into target. Moves all senses, definitions, examples, and relations from source into target, then deletes the source. Deduplicates definitions and removes self-loop relations. If only the source has an ILI, it transfers to the target. Raises `ConflictError` if both have ILI mappings. |
| 36 | `split_synset(synset_id, sense_groups)` | Split a synset into multiple new synsets. The first group keeps the original synset; each subsequent group creates a new synset. Outgoing relations are copied to all new synsets. Requires at least 2 groups. |

---

## Design Notes

- **CRUD pattern per entity type**: The API follows a consistent create/update/delete pattern, adapted to WordNet semantics.
- **Index-based addressing for definitions and examples**: These are ordered sequences without natural keys, so they use zero-based indexes rather than IDs.
- **Three relation flavors**: synset-to-synset, sense-to-sense, and sense-to-synset mirror the WN-LMF 1.4 specification exactly. Auto-inverse is supported for the first two; sense-to-synset relations are cross-type and have no defined inverse.
- **Lexicalization side effects**: `move_sense` and `remove_sense` automatically update the synset's `lexicalized` flag when senses are added or removed.
- **Cascade deletion**: `delete_synset` and `delete_entry` require explicit `cascade=True` to delete child senses, protecting against accidental data loss.
- **Batch mode**: Any combination of these actions can be grouped inside `with editor.batch():` for atomic, all-or-nothing execution.
