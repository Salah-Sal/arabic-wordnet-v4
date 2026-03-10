# Algorithm Diagrams — draft_api.md

Three Mermaid diagrams representing the linguistic review algorithm.
For the full pseudocode, see [draft_api.md](draft_api.md).

---

## Diagram 1: High-Level Pipeline

Steps 0–6 as a vertical pipeline. The `action_queue` accumulates decisions from Steps 0–5, then Step 6 executes them.

```mermaid
flowchart TD
    %% ── Inputs ──
    IN_SYN[/"Synset\n(synset_id, lemmas, definition, relations)"/]
    IN_RES[/"Research File\n(definitions, attestations, candidates, root family)"/]

    %% ── Steps ──
    S0["<b>Step 0: Evidence Extraction</b>\nClassify each dictionary text as\nconfirm / contradicts / expands\n<i>(non-exclusive categories)</i>"]

    S1["<b>Step 1: Lemma Validation</b>\n4 evidence cases → 6 checks:\nMWE · Dialectal · Substitution\nSpecificity · Calque · Final decision"]

    S2["<b>Step 2: Missing Lemmas</b>\nExtract evidence for candidates\nEvidence gate → Cross-ref → Substitution\n→ add / variant / propose_new_synset / reject"]

    S3["<b>Step 3: Definition Processing</b>\nCompare AWN def ↔ classical defs\nConditional authoring:\nterminological · linguistic · encyclopedic\n+ quality checks"]

    S4["<b>Step 4: Relations Check</b>\nHypernymy (bounded 3 levels)\nAntonymy (detect internal conflicts)\nVerb frames · Selectional restrictions"]

    S5["<b>Step 5: Enrichment & Culture</b>\nConsume expand data · Set metadata fields\nConflict resolution (multi-value)\nMorphology · POS guidelines · Cultural fit"]

    S6A["<b>Step 6a: YAML + Evaluation</b>\nCompile YAML output\nScore: semantic_accuracy · gloss_quality\nsynonym_coherence · completeness\ncultural_adequacy · overall"]

    S6B["<b>Step 6b: API Execution</b>\n6 phases in order:\n① Removals → ② Modifications\n③ Creations → ④ Relations\n⑤ Metadata → ⑥ Evaluation"]

    %% ── Action Queue (side) ──
    AQ[("action_queue\n(▸ actions)")]

    %% ── Output ──
    OUT[/"Output\nYAML review file\n+ executed API calls (⊕)"/]

    %% ── Flow ──
    IN_SYN --> S0
    IN_RES --> S0
    S0 --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> S6A
    S6A --> S6B
    S6B --> OUT

    %% ── Action Queue connections ──
    S0 -. "▸ record evidence" .-> AQ
    S1 -. "▸ reject / confirm / flag" .-> AQ
    S2 -. "▸ add / propose / reject" .-> AQ
    S3 -. "▸ revise / author def" .-> AQ
    S4 -. "▸ flag_relation / add_relation" .-> AQ
    S5 -. "▸ enrichment / cultural" .-> AQ
    AQ -. "consumed by" .-> S6B

    %% ── Styles ──
    classDef input fill:#e8f4fd,stroke:#2196F3,color:#000
    classDef step fill:#fff3e0,stroke:#FF9800,color:#000
    classDef exec fill:#e8f5e9,stroke:#4CAF50,color:#000
    classDef queue fill:#f3e5f5,stroke:#9C27B0,color:#000
    classDef output fill:#e8f4fd,stroke:#2196F3,color:#000

    class IN_SYN,IN_RES input
    class S0,S1,S2,S3,S4,S5 step
    class S6A,S6B exec
    class AQ queue
    class OUT output
```

---

## Diagram 2: Step 1 — Lemma Validation Decision Tree

The most complex step: evidence-based gating → sequential checks → final decision.

```mermaid
flowchart TD
    START(["For each lemma"])

    %% ══════ Evidence Cases ══════
    START --> EV{"Evidence\nstatus?"}

    %% Case 1: No material
    EV -->|"no_material_found"| C1{"Linguist sees\nsemantic link?"}
    C1 -->|Yes| C1A["nuance_note:\nno evidence — accepted\nby linguist"]
    C1 -->|No| C1R["reject_lemma\n+ nuance_note"]
    C1R --> EXIT_R([Next lemma])

    %% Case 2: Contradicts
    EV -->|"contradicts\nnon-empty"| C2{"Source of\ncontradiction?"}
    C2 -->|"Lemma has\ndifferent meaning"| C2A["nuance_note:\nmeaning differs"]
    C2 -->|"Definition\ntoo narrow"| C2B["flag_definition_review\n→ Step 3"]
    C2 -->|"Polysemy"| C2C["flag_split_needed\n+ nuance_note"]

    %% Case 3: Expands
    EV -->|"expands\nnon-empty"| C3{"Independent\nmeaning?"}
    C3 -->|Yes| C3A["flag_split_needed\n+ nuance_note"]
    C3 -->|No| C3B["nuance_note:\nadditional dimension"]

    %% Case 4: Confirm only
    EV -->|"confirm only"| C4["Fast path\n(evidence supports)"]

    %% ══════ Merge to checks ══════
    C1A --> CHK_MWE
    C2A --> CHK_MWE
    C2B --> CHK_MWE
    C2C --> CHK_MWE
    C3A --> CHK_MWE
    C3B --> CHK_MWE
    C4 --> CHK_MWE

    %% ══════ Sequential Checks ══════

    %% أ٠ MWE
    CHK_MWE{"أ٠: Multi-Word\nExpression?"}
    CHK_MWE -->|No| CHK_DIAL
    CHK_MWE -->|Yes| MWE_ID{"Idiomatic &\nstable?"}
    MWE_ID -->|Yes| MWE_OK["accept_mwe\n(test as unit)"]
    MWE_ID -->|No| MWE_REJ["reject_lemma\nnot a lexical unit"]
    MWE_REJ --> EXIT_R2([Next lemma])
    MWE_OK --> CHK_DIAL

    %% أ٫١ Dialectal
    CHK_DIAL{"أ٫١: Dialectal\nform?"}
    CHK_DIAL -->|No| CHK_SUB
    CHK_DIAL -->|Yes| DIAL_R["remove_dialectal"]
    DIAL_R --> EXIT_R3([Next lemma])

    %% أ Substitution test
    CHK_SUB{"أ: Substitution\nTest\nاختبار_الإبدال()"}
    CHK_SUB -->|Pass| CHK_NU
    CHK_SUB -->|Fail| SUB_REJ["reject_lemma"]
    SUB_REJ --> EXIT_R4([Next lemma])

    %% ب Nuance note
    CHK_NU["ب: add_nuance_note\n(mandatory for every lemma)"]
    CHK_NU --> CHK_SPEC

    %% ج Specificity
    CHK_SPEC{"ج: More specific\nterm exists?"}
    CHK_SPEC -->|No| CHK_CAL
    CHK_SPEC -->|Yes| SPEC_SWAP["remove_lemma\n+ add_lemma(specific)"]
    SPEC_SWAP --> CHK_CAL

    %% د Calque / Loanword
    CHK_CAL{"د: Calque or\nLoanword?"}
    CHK_CAL -->|"Calque"| CAL_R["remove_calque\n+ add Arabic equiv\n(if not exists)"]
    CAL_R --> EXIT_R5([Next lemma])
    CHK_CAL -->|"Loanword\n(accepted)"| LOAN_OK["accept_loanword\n+ enrichment"]
    CHK_CAL -->|"Neither"| FINAL
    LOAN_OK --> FINAL

    %% ══════ Final Decision (ز) ══════
    FINAL{"ز: Final\nDecision"}

    FINAL -->|"Semantic shift\ndetected"| F_SHIFT["confirm\n+ period restriction\n+ usage note"]
    FINAL -->|"Modern word\nno classical root"| F_MOD["confirm\n+ usage=modern"]
    FINAL -->|"confirm ≠∅\ncontradicts =∅"| F_CONF["confirm"]
    FINAL -->|"confirm ≠∅\ncontradicts ≠∅"| F_MIXED{"Confirmation\nstronger?"}
    F_MIXED -->|Yes| F_CONF_CAV["confirm\nwith caveat"]
    F_MIXED -->|No| F_ESC1["escalate"]
    FINAL -->|"expands only"| F_EXP["confirm\n+ scope note"]
    FINAL -->|"no_material\n(linguist OK)"| F_NOM["confirm\nby linguist"]
    FINAL -->|"contradicts only\n(passed subst.)"| F_ESC2["escalate"]
    FINAL -->|"none match"| F_REJ["reject_lemma"]

    %% ══════ Styles ══════
    classDef accept fill:#c8e6c9,stroke:#2E7D32,color:#000
    classDef reject fill:#ffcdd2,stroke:#C62828,color:#000
    classDef escalate fill:#fff9c4,stroke:#F9A825,color:#000
    classDef check fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef mandatory fill:#e8eaf6,stroke:#283593,color:#000
    classDef exitNode fill:#ffcdd2,stroke:#C62828,color:#000

    class C1A,MWE_OK,LOAN_OK,SPEC_SWAP,F_SHIFT,F_MOD,F_CONF,F_CONF_CAV,F_EXP,F_NOM accept
    class C1R,MWE_REJ,SUB_REJ,DIAL_R,CAL_R,F_REJ reject
    class F_ESC1,F_ESC2 escalate
    class CHK_MWE,CHK_DIAL,CHK_SUB,CHK_SPEC,CHK_CAL,FINAL check
    class CHK_NU mandatory
    class EXIT_R,EXIT_R2,EXIT_R3,EXIT_R4,EXIT_R5 exitNode
```

---

## Diagram 3: API Execution Phases (Step 6b)

The action_queue is executed in 6 sequential phases. Each phase must complete before the next begins.

```mermaid
flowchart LR
    AQ[("action_queue\n(collected from\nSteps 0–5)")]

    subgraph P1["Phase 1: Removals"]
        P1_IN["reject_lemma\nremove_lemma\nremove_calque\nremove_dialectal"]
        P1_API["⊕ remove_sense()"]
        P1_IN --> P1_API
    end

    subgraph P2["Phase 2: Modifications"]
        P2A["modify_lemma_form\n→ ⊕ update_lemma()"]
        P2B["revise_definition\n→ ⊕ update_definition()"]
        P2C["flag_pos_mismatch\n→ ⊕ update_entry()\n   / update_synset()"]
    end

    subgraph P3["Phase 3: Creations"]
        P3A["add_lemma\n→ ⊕ create_entry()\n   + add_sense()"]
        P3B["add_variant_form\n→ ⊕ add_form()"]
        P3C["propose_new_synset\n→ ⊕ create_synset()\n   + create_entry()\n   + add_sense()\n   + add_synset_relation()\n   + add_definition()\n   + link_ili()"]
        P3D["flag_split_needed\n→ ⊕ create_synset()\n   + move_sense()\n   + add_synset_relation()"]
        P3E["author_definition\n→ ⊕ add_definition()"]
        P3F["add_phraset\n→ ⊕ create_entry()\n   + add_sense()"]
        P3G["add_example\n→ ⊕ add_synset_example()\n   / add_sense_example()"]
    end

    subgraph P4["Phase 4: Relations"]
        P4A["flag_relation\n→ ⊕ remove_synset_relation()\n   + add_synset_relation()"]
        P4B["link_broken_plural\n→ ⊕ add_sense_relation()"]
    end

    subgraph P5["Phase 5: Metadata"]
        P5A["add_enrichment\n→ ⊕ set_metadata(sense)"]
        P5B["add_nuance_note\n→ ⊕ set_metadata(sense, nuance)"]
        P5C["add_syntactic_frame\n→ ⊕ set_metadata(sense, frame)"]
        P5D["add_collocation\n→ ⊕ set_metadata(sense, colloc)"]
        P5E["correct_root\n→ ⊕ set_metadata(entry, root)"]
        P5F["accept_loanword\n→ ⊕ set_metadata(entry, etymology)"]
        P5G["cultural_fit\n→ ⊕ set_metadata(synset, cultural)"]
        P5H["escalate\n→ ⊕ set_metadata(synset, escalation)\n   + set_confidence(0.0)"]
    end

    subgraph P6["Phase 6: Evaluation"]
        P6A["Scores\n→ ⊕ set_metadata(synset)\nfor: semantic_accuracy\ngloss_quality\nsynonym_coherence\ncompleteness\ncultural_adequacy\noverall"]
        P6B["confirm\n→ ⊕ set_confidence(sense, 1.0)"]
        P6C["Overall confidence\n→ ⊕ set_confidence(synset)"]
    end

    OUT[/"YAML + API calls\ncompleted"/]

    AQ --> P1
    P1 -->|"removals done"| P2
    P2 -->|"modifications done"| P3
    P3 -->|"creations done"| P4
    P4 -->|"relations done"| P5
    P5 -->|"metadata done"| P6
    P6 --> OUT

    %% ── Styles ──
    classDef removal fill:#ffcdd2,stroke:#C62828,color:#000
    classDef modify fill:#fff9c4,stroke:#F9A825,color:#000
    classDef create fill:#c8e6c9,stroke:#2E7D32,color:#000
    classDef relation fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef meta fill:#f3e5f5,stroke:#7B1FA2,color:#000
    classDef eval fill:#e0f2f1,stroke:#00695C,color:#000

    class P1 removal
    class P2 modify
    class P3 create
    class P4 relation
    class P5 meta
    class P6 eval
```
