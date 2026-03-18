## stage 1: review sysnset info without any aditional context then generate 4 additional entries based on terimnology guide. 
    - inputs: 
        1. sysnet info in Arabic and Engish.
        2. termminlogy creation guide. 
        3. general isntuctions (prompt)
    - outputs:
        1. overall linguistic assessment of content of the Arabic sysnet.
        2.  4 new lemmas (entreis) either that are totally new or imporved versions of exting lemmas or enteries. **All generated lemmas must include full diacritics (tashkeel).**

## stage 2: browse the dictionary file and db to gather as much evidence related to the lexical entries of the Arabic sysnset, its lemmas (enteries), its defintion, its examples. 
    - inputs: 
        1. db. 
        2. automated evidance generated files from db. 
        3. db guide and reference on how to query the db.  
        4. general isntuctions (prompt)

    -outputs:
        - for each lemma: list all the quotations from the dictionary evidence and db found that either support, refute, expand the use of such lemma in the context of the semantic of this synset inferred from its definition, and english synset info. that include the exsting lemmas and the generated lemmas. 

## stage 3: lemma linguistic analysis: given the sysnet info in Arabic and English and the genreated lemmas and the linguistic assessment of stage 1, the gathered linguistic material from dictionaries perform linguisc analysis where you will judge each Arabic entery (lemma) to include it or exclude it from the sysnset based on erminology guide  and evidence if availble or your linguistic knowldge and the terminology guide if evidence is absent. 
    - inputs: 
        1. dicitonary material gathered in Stage 2. 
        2. terminlaogy guide. 
        3. synset info in Arabic and english.
        4. general isntuctions (prompt) 

    - outputs:
        - a list of decisions for each lemma.
        - **fully diacritized form for every approved lemma** (existing or generated).

## stage 4: definition and examples lingusic analysis: given the sysnet info in Arabic and English and the genreated lemmas and the linguistic assessment of stage 1, the gathered linguistic material from dictionaries perform linguisc analysis where you will assess the quality of the current arabic defintion and enrich by adding two more defintions (encylopidic defintion, linguisc definition). you will also assess the quality of the current examples in the sysnet and enrich it by adding at least on example for each approved entery or lemma. 
    - inputs: 
        1. dicitonary material gathered in Stage 2. 
        2. terminlaogy guide. 
        3. synset info in Arabic and english. 
        4. general isntuctions (prompt). 

    - outputs:
        - revised definition.
        - two more defintions added.
        - revised examples and added examples for each appraoved lemma.

---

## Possible Actions for Stages 3 & 4

Stages 3 and 4 are the only stages that produce decisions resulting in mutations against the synset. Below is the complete list of possible actions per stage, mapped to the `WordnetEditor` API (`spec/editing-actions.md`).

### Stage 3: Lemma Analysis — All Possible Actions (16 types)

Stage 3 decides which lemmas stay, which go, and which new ones join. These are **membership mutations**.

**Diacritization requirement:** Every approved lemma (existing or generated) must have full diacritics (tashkeel) in its final form. Stage 2 dictionary evidence (the `headword` column) is the primary reference for verifying correct diacritization. For existing lemmas missing diacritics → `update_lemma`. For generated candidates → the fully diacritized form from Stage 1 is verified and passed to `create_entry`.

#### A. Existing Lemmas (already in the synset)

**Decision: Keep** — no mutation needed (lemma is already linked).

**Decision: Remove**
| # | Action | Params | When |
|---|--------|--------|------|
| 1 | `remove_sense` | `sense_id` | Lemma rejected — remove its link to this synset (entry survives for other synsets) |

**Decision: Correct (keep but fix)**
| # | Action | Params | When |
|---|--------|--------|------|
| 2 | `update_lemma` | `entry_id`, `new_lemma` | Spelling error, wrong diacritics, wrong morphological form, **or missing/incomplete diacritics** |
| 3 | `update_entry` | `entry_id`, `pos` | Wrong POS on the entry (e.g., noun tagged as verb) |
| 4 | `add_form` | `entry_id`, `written_form` | Alternative spelling or variant form to add |
| 5 | `remove_form` | `entry_id`, `written_form` | Remove an incorrect variant form |

#### B. Generated Lemmas (Stage 1 candidates, not yet in the synset)

**Decision: Approve**
| # | Action | Params | When |
|---|--------|--------|------|
| 7 | `create_entry` | `lemma`, `pos` | Candidate doesn't exist in the lexicon yet |
| 8 | `add_sense` | `entry_id`, `synset_id` | Link the new (or existing) entry to this synset |

> Approving a generated lemma is a 2-step operation: create the entry if it doesn't already exist in the lexicon, then add a sense linking it to this synset.

**Decision: Reject** — no mutation needed (candidate was never linked to the synset).

#### Synset-level Correction
| # | Action | Params | When |
|---|--------|--------|------|
| 9 | `update_synset` | `synset_id`, `pos` | Wrong POS at synset level |

#### Sense-level Relations
| # | Action | Params | When |
|---|--------|--------|------|
| 10 | `add_sense_relation` | `source_id`, `relation_type`, `target_id` | Derivation link (e.g., broken plural ↔ singular), sense-level antonymy |
| 11 | `remove_sense_relation` | `source_id`, `relation_type`, `target_id` | Wrong sense-level relation |


---

### Stage 4: Definition & Examples — All Possible Actions (8 types)

Stage 4 assesses and enriches the descriptive content. These are **content mutations**.

#### Definition Mutations
| # | Action | Params | When |
|---|--------|--------|------|
| 1 | `update_definition` | `synset_id`, `definition_index`, `text` | Revise the existing Arabic definition |
| 2 | `add_definition` | `synset_id`, `text` | Add encyclopedic definition |
| 3 | `add_definition` | `synset_id`, `text` | Add linguistic definition |
| 4 | `remove_definition` | `synset_id`, `definition_index` | Remove a bad or duplicate definition |

#### Example Mutations
| # | Action | Params | When |
|---|--------|--------|------|
| 5 | `add_synset_example` | `synset_id`, `text` | Add usage example at synset level |
| 6 | `add_sense_example` | `sense_id`, `text` | Add usage example specific to one lemma's sense |
| 7 | `remove_synset_example` | `synset_id`, `example_index` | Remove a bad synset-level example |
| 8 | `remove_sense_example` | `sense_id`, `example_index` | Remove a bad sense-level example |

---

## stage 5: enrichment — populate entries, senses, and synset with structured metadata (root, Maqayis quotation, semantic nuance, cultural fit), packed into the WN-LMF `note` key for XML round-trip safety.
    - inputs:
        1. approved lemmas from Stage 3 (with full diacritics, MWE status known).
        2. dictionary evidence from Stage 2 (`root`, `root_source` columns in per_lemma step3_root_family).
        3. synset info in Arabic and English.
        4. Arabic dictionary DB (for Maqayis queries — dictionary_id = 151, hawramani_7).
        5. general instructions (prompt).

    - outputs:
        - for each approved entry: root + Maqayis al-Lugha quotation (packed into `note`).
        - for each approved sense: semantic nuance differentiation + MWE flag (packed into `note`).
        - for the synset: cultural fit classification (packed into `note`).

---

## Possible Actions for Stages 3, 4 & 5

Stages 3, 4, and 5 are the stages that produce decisions resulting in mutations against the synset. Below is the complete list of possible actions per stage, mapped to the `WordnetEditor` API (`spec/editing-actions.md`).

### Stage 3: Lemma Analysis — All Possible Actions (16 types)

Stage 3 decides which lemmas stay, which go, and which new ones join. These are **membership mutations**.

**Diacritization requirement:** Every approved lemma (existing or generated) must have full diacritics (tashkeel) in its final form. Stage 2 dictionary evidence (the `headword` column) is the primary reference for verifying correct diacritization. For existing lemmas missing diacritics → `update_lemma`. For generated candidates → the fully diacritized form from Stage 1 is verified and passed to `create_entry`.

#### A. Existing Lemmas (already in the synset)

**Decision: Keep** — no mutation needed (lemma is already linked).

**Decision: Remove**
| # | Action | Params | When |
|---|--------|--------|------|
| 1 | `remove_sense` | `sense_id` | Lemma rejected — remove its link to this synset (entry survives for other synsets) |

**Decision: Correct (keep but fix)**
| # | Action | Params | When |
|---|--------|--------|------|
| 2 | `update_lemma` | `entry_id`, `new_lemma` | Spelling error, wrong diacritics, wrong morphological form, **or missing/incomplete diacritics** |
| 3 | `update_entry` | `entry_id`, `pos` | Wrong POS on the entry (e.g., noun tagged as verb) |
| 4 | `add_form` | `entry_id`, `written_form` | Alternative spelling or variant form to add |
| 5 | `remove_form` | `entry_id`, `written_form` | Remove an incorrect variant form |

#### B. Generated Lemmas (Stage 1 candidates, not yet in the synset)

**Decision: Approve**
| # | Action | Params | When |
|---|--------|--------|------|
| 7 | `create_entry` | `lemma`, `pos` | Candidate doesn't exist in the lexicon yet |
| 8 | `add_sense` | `entry_id`, `synset_id` | Link the new (or existing) entry to this synset |

> Approving a generated lemma is a 2-step operation: create the entry if it doesn't already exist in the lexicon, then add a sense linking it to this synset.

**Decision: Reject** — no mutation needed (candidate was never linked to the synset).

#### Synset-level Correction
| # | Action | Params | When |
|---|--------|--------|------|
| 9 | `update_synset` | `synset_id`, `pos` | Wrong POS at synset level |

#### Sense-level Relations
| # | Action | Params | When |
|---|--------|--------|------|
| 10 | `add_sense_relation` | `source_id`, `relation_type`, `target_id` | Derivation link (e.g., broken plural ↔ singular), sense-level antonymy |
| 11 | `remove_sense_relation` | `source_id`, `relation_type`, `target_id` | Wrong sense-level relation |

#### Metadata & Confidence
| # | Action | Params | When |
|---|--------|--------|------|
| 16 | `set_metadata("sense", ...)` | `sense_id`, `key`, `value` | Nuance note, etymology (loanword), MWE flag, syntactic frame |
| 17 | `set_metadata("synset", ...)` | `synset_id`, `key`, `value` | Escalation reason, cultural fit classification |
| 18 | `set_metadata("entry", ...)` | `entry_id`, `key`, `value` | Root correction, etymology |
| 19 | `set_confidence("sense", ...)` | `sense_id`, `score` | Confidence score per approved/rejected sense |
| 20 | `set_confidence("synset", ...)` | `synset_id`, `score` | Overall synset confidence (0.0 for escalated) |


---

### Stage 4: Definition & Examples — All Possible Actions (8 types)

Stage 4 assesses and enriches the descriptive content. These are **content mutations**.

#### Definition Mutations
| # | Action | Params | When |
|---|--------|--------|------|
| 1 | `update_definition` | `synset_id`, `definition_index`, `text` | Revise the existing Arabic definition |
| 2 | `add_definition` | `synset_id`, `text` | Add encyclopedic definition |
| 3 | `add_definition` | `synset_id`, `text` | Add linguistic definition |
| 4 | `remove_definition` | `synset_id`, `definition_index` | Remove a bad or duplicate definition |

#### Example Mutations
| # | Action | Params | When |
|---|--------|--------|------|
| 5 | `add_synset_example` | `synset_id`, `text` | Add usage example at synset level |
| 6 | `add_sense_example` | `sense_id`, `text` | Add usage example specific to one lemma's sense |
| 7 | `remove_synset_example` | `synset_id`, `example_index` | Remove a bad synset-level example |
| 8 | `remove_sense_example` | `sense_id`, `example_index` | Remove a bad sense-level example |

---

### Stage 5: Enrichment — All Possible Actions (4 types)

Stage 5 populates structured metadata on entries, senses, and the synset. These are **metadata mutations**, all using `set_metadata` with data packed into the `note` key.

#### Why pack into `note`?

The base `wn` library is read-only for metadata (no `set_metadata` API). The editor (`wn-editor-extended`) adds mutation for 4 entity types: `"lexicon"`, `"synset"`, `"entry"`, `"sense"`. Keys are free-form — any JSON-serializable value.

**Problem:** Non-standard keys don't survive WN-LMF XML round-trip. `_meta_dict()` in `wn/lmf.py` only writes the 17 standard keys; custom keys like `root`, `cultural_fit`, `nuance` are silently dropped on export.

**Solution:** Pack all custom enrichment data into the standard `note` key as a JSON string. `note` is one of the 17 standard WN-LMF keys and survives export → reimport. `confidenceScore` stays as its own standard key (no packing needed).

#### Note-packing merge strategy

When writing to `note`, first read the existing value. If it contains plain text (not JSON), preserve it under `_original_note` inside the JSON dict. If it's already a JSON dict, merge keys.

```python
existing = entity.metadata().get("note", "")
try:
    base = json.loads(existing)  # already JSON — merge
except (json.JSONDecodeError, TypeError):
    base = {"_original_note": existing} if existing else {}
base.update(new_enrichment_fields)
set_metadata(entity_type, entity_id, "note", json.dumps(base, ensure_ascii=False))
```

Consumers read enrichment data via: `json.loads(entity.metadata().get("note", "{}"))`.

#### Entry Metadata (root + Maqayis quotation)

| # | Action | Params | When |
|---|--------|--------|------|
| 1 | `set_metadata("entry", ...)` | `entry_id`, `"note"`, `'{"root":"...","maqayis":"..."}'` | Every approved single-word lemma |
| 2 | `set_metadata("entry", ...)` | `entry_id`, `"note"`, `'{"roots":[{"word":"...","root":"...","maqayis":"..."},...]}'` | Every approved MWE lemma |

**Root source:** Stage 2 evidence (`root`, `root_source` columns in per_lemma step3_root_family) + LLM verification. Roots are not necessarily trilateral — can be bi/tri/quadrilateral.

**Maqayis source:** Direct DB query against مقاييس اللغة لابن فارس (Ibn Faris, d. 1004 CE). Hawramani version, dictionary_id = 151.

```sql
SELECT e.headword, e.definitions_text
FROM entries e
WHERE e.dictionary_id = 151
  AND e.headword_norm = '<root>'
LIMIT 1
```

The quote is purely documentary — `definitions_text` is stored as-is with no LLM interpretation. If no entry found for that root, omit `maqayis`.

**MWE handling:** Extract root for each component word separately. Each gets its own root + Maqayis quote.

Single-word example (`كِيَان`):
```json
{"root": "كون", "maqayis": "«الْكَافُ وَالْوَاوُ وَالنُّونُ أَصْلٌ صَحِيحٌ يَدُلُّ عَلَى...»"}
```

MWE example (`ذكاء اصطناعي`):
```json
{"roots": [
    {"word": "ذكاء", "root": "ذكو", "maqayis": "«الذَّالُ وَالْكَافُ وَالْحَرْفُ المُعْتَلُّ...»"},
    {"word": "اصطناعي", "root": "صنع", "maqayis": "«الصَّادُ وَالنُّونُ وَالْعَيْنُ أَصْلٌ وَاحِدٌ...»"}
]}
```

#### Sense Metadata (nuance + MWE flag)

| # | Action | Params | When |
|---|--------|--------|------|
| 3 | `set_metadata("sense", ...)` | `sense_id`, `"note"`, `'{"nuance":"...","mwe":true}'` | Every approved sense |

**Nuance** is mandatory for every approved sense — no absolute synonymy. Describes how this lemma differs semantically from its siblings in the same synset. `mwe` is `true` only if the sense is a multi-word expression (from Stage 3 decision).

#### Synset Metadata (cultural fit)

| # | Action | Params | When |
|---|--------|--------|------|
| 4 | `set_metadata("synset", ...)` | `synset_id`, `"note"`, `'{"cultural_fit":"..."}'` | Every synset |

**cultural_fit** values: `"native"` / `"lexical_gap"` / `"phraset"` / `"omission"`.

---

### Summary

| Stage | Scope | Action Types | Most Common |
|-------|-------|-------------|-------------|
| Stage 3 | Lemma membership | **16** | `remove_sense`, `create_entry` + `add_sense`, `set_metadata` |
| Stage 4 | Definitions + examples | **8** | `update_definition`, `add_definition`, `add_synset_example`, `add_sense_example` |
| Stage 5 | Enrichment metadata | **4** | `set_metadata("entry", ..., "note", ...)`, `set_metadata("sense", ..., "note", ...)` |
| **Total unique across all** | | **~24** (some overlap in metadata across stages) | |

### Updated Pipeline

```
Stage 1: Review + Generate       → assessment + 4 fully-diacritized candidates
Stage 2: Evidence Gathering       → dictionary quotations per lemma
Stage 3: Lemma Analysis           → include/exclude decisions + diacritization
Stage 4: Definition & Examples    → revised + 2 new definitions + examples
Stage 5: Enrichment               → metadata on entries/senses/synset (note-packed)
```