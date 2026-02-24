# AWN4 Experiments — Index

Each experiment has its own `EXPERIMENT_LOG.md` inside its folder. This file provides the timeline and dependency map.

---

## Timeline

```
2026-01-22  AWN4 v4.0.0 released (109,823 AI-translated synsets)
     │
     ▼
2026-02-09  Phase 1 — Resource Exploration
     │      ├── qabas/                           Qabas lexicon exploration
     │      └── arabic_ontology_comparison/       Ontology vs AWN4 (lemmas + hierarchy)
     │              └── Side effect: fixed 78 missing upper-ontology synsets in AWN4
     ▼
2026-02-09  Phase 2 — Review Framework
–02-10      └── linguist_review/                  Human + LLM review framework
     │
     ▼
2026-02-23  Phase 3 — Automated Quality Pipeline
     │      ├── prefilter/                        Stage 1: dictionary pre-filter
     │      │       └── Key discovery: 5,378 polysemy groups (12,496 synsets)
     │      └── polysemy_reviews/                 Stage 2–3: evidence packages + LLM review
     │
     ▼
2026-02-24  Reorganization & documentation
     │
     ▼
2026-02-24  Phase 4 — Comprehensive Linguistic Audit
            └── synset_linguistic_audit/             Synset-level linguistic review framework
```

## Experiment Index

| Folder | Date | Description | Status |
|---|---|---|---|
| `qabas/` | 2026-02-09 | Qabas morphological lexicon exploration | Complete |
| `arabic_ontology_comparison/` | 2026-02-09 | Arabic Ontology vs AWN4 (lemma matching + hierarchy comparison) | Complete |
| `linguist_review/` | 2026-02-09–10 | Human + LLM linguist review framework | Superseded for polysemy |
| `prefilter/` | 2026-02-23 | Dictionary pre-filter (6 automated checks) | Complete |
| `polysemy_reviews/` | 2026-02-23–24 | Polysemy disambiguation pipeline (evidence packages + LLM review) | Pilot complete |
| `synset_linguistic_audit/` | 2026-02-24 | Comprehensive synset-level linguistic review (35 questions, 7 levels) | Design phase |

## Dependencies

```
qabas/                         ─── standalone
arabic_ontology_comparison/    ─── fixed AWN4 base resource
linguist_review/               ─── tone/style ──→ polysemy_reviews/ prompt
prefilter/                     ─── data ────────→ polysemy_reviews/
polysemy_reviews/              ─── active frontier
synset_linguistic_audit/       ─── extends all above; active frontier
```
