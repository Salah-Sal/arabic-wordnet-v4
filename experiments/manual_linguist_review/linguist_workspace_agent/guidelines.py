"""
guidelines.py — Structured prompt for the RLM evidence collection agent.

The guidelines instruct the RLM on the evidence collection methodology,
available tools, strategy, and output format.
"""


def get_evidence_guidelines() -> str:
    return """
YOU MUST RUN THE FOLLOWING CODE BLOCKS IN ORDER. DO NOT WRITE YOUR OWN CODE.
COPY EACH BLOCK EXACTLY. Only modify variable values if needed.

IMPORTANT: Tool return keys are "entries" (NOT "results"), "entries_with_senses", "examples".
IMPORTANT: SUBMIT takes a JSON STRING: SUBMIT(evidence_json=json.dumps(...))

## BLOCK 1: Initialize

```python
import json
data = json.loads(synset_data)
lemmas = data.get("lemmas", [])
artifact = {
    "_meta": {"schema_version": "1.0.0", "generator": "rlm_agent", "db_stats": get_db_stats()},
    "synset": data,
    "per_lemma": {},
    "per_synset": {},
}
seen_ids = set()
print(f"Synset: {synset_id}, Lemmas: {lemmas}")
```

## BLOCK 2: Per-lemma evidence (run this block once — it loops over all lemmas)

```python
import json
for lemma in lemmas:
    norm = normalize_lemma(lemma)
    step1 = lookup_headword(lemma)
    for e in step1.get("entries", []):
        seen_ids.add(e["entry_id"])
    step2 = lookup_definitions(lemma)
    for e in step2.get("entries_with_senses", []):
        seen_ids.add(e["entry_id"])
    step3 = lookup_root_family(lemma, json.dumps(list(seen_ids)))
    for rk, rv in step3.get("by_root", {}).items():
        for e in rv.get("entries", []):
            seen_ids.add(e["entry_id"])
    step6 = lookup_examples(lemma)
    step7 = {"result_count": step1["result_count"], "entries": sorted(step1.get("entries", []), key=lambda e: e.get("dict_death_year") or 9999)}
    step8 = reverse_lookup(lemma)
    for e in step8.get("entries", []):
        seen_ids.add(e["entry_id"])
    artifact["per_lemma"][lemma] = {
        "identity": {"lemma": lemma, "lemma_bare": norm["bare"], "lemma_norm": norm["norm"], "is_multiword": norm["is_multiword"], "components": norm["components"]},
        "step1_headword": step1,
        "step2_definitions": step2,
        "step3_root_family": step3,
        "step6_examples": step6,
        "step7_chronological": step7,
        "step8_reverse_lookup": step8,
    }
    print(f"[{lemma}] hw={step1['result_count']} defs={step2['result_count']} roots={len(step3.get('roots_found',[]))} ex={step6['result_count']} rev={step8['result_count']}")
print(f"Total seen_ids: {len(seen_ids)}")
```

## BLOCK 3: Per-synset FTS evidence

```python
import json
keywords = extract_arabic_keywords(data.get("definition_ar", ""))
excl = json.dumps(list(seen_ids))
fts4 = fts_search(" OR ".join(keywords), "arabic", excl) if keywords else {"result_count": 0, "entries": []}
for e in fts4.get("entries", []):
    seen_ids.add(e["entry_id"])
artifact["per_synset"]["step4_fts_keyword"] = {"keywords_extracted": keywords, "excluded_entry_ids": list(seen_ids), "result_count": fts4["result_count"], "entries": fts4.get("entries", [])}
en_lemmas = data.get("oewn", {}).get("lemmas_en", [])
en_entries = []
excl = json.dumps(list(seen_ids))
for term in en_lemmas:
    res = fts_search(term, "english", excl)
    en_entries.extend(res.get("entries", []))
    for e in res.get("entries", []):
        seen_ids.add(e["entry_id"])
artifact["per_synset"]["step5_english_bridge"] = {"english_terms_used": en_lemmas, "excluded_entry_ids": list(seen_ids), "result_count": len(en_entries), "entries": en_entries}
artifact["per_synset"]["step9_specialized"] = {"filters_applied": []}
print(f"FTS arabic={fts4['result_count']} english={len(en_entries)}")
```

## BLOCK 4: Submit

```python
import json
SUBMIT(evidence_json=json.dumps(artifact, ensure_ascii=False))
```

DO NOT deviate from this structure. DO NOT add your own fields.
DO NOT use llm_query(). DO NOT filter or summarize results.
Store ALL raw tool results as-is.
""".strip()
