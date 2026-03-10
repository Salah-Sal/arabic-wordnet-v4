# دليل المرحلة الثانية — Stage 2 Analysis Guide (v2)

## نظرة عامة — Overview

Stage 2 is the **manual linguistic analysis** phase. An LLM (or human linguist)
receives a filled prompt with dictionary evidence and produces a structured
review in YAML format.

**Goal:** For each synset, answer three evidence-based questions, then enrich.

---

## سير العمل — Workflow

```
┌──────────────┐     ┌────────────────┐     ┌────────────────┐     ┌─────────────┐
│ fill_prompt  │ ──▸ │ send to LLM    │ ──▸ │ save as        │ ──▸ │ validate    │
│ .py          │     │ or linguist    │     │ review.yaml    │     │ review      │
└──────────────┘     └────────────────┘     └────────────────┘     └─────────────┘
```

### 1. Generate prompt

```bash
python3 tools/fill_prompt.py awn4-XXXXXXXX-X --output-dir output/
```

Creates `output/<synset_id>/prompt.md` — a self-contained prompt with all
dictionary evidence embedded.

### 2. Run analysis

Send `prompt.md` to an LLM or have a linguist read and respond.
The prompt asks three core questions per lemma, then enrichment.

### 3. Save and validate

Save the YAML output as `output/<synset_id>/review.yaml`, then:

```bash
python3 tools/validate_review.py output/<synset_id>/review.yaml
```

---

## الأسئلة الثلاثة — Three Core Questions

### ❶ هل المعنى مدعوم معجمياً؟ — Is the meaning attested?

For each lemma: find a dictionary definition or example that confirms this
word carries the synset's meaning. **Cite the dictionary and quote the text.**

- Found explicit text → `confirmed`
- Close but not exact → `confirmed` + flag `WEAK_EVIDENCE`
- No supporting text → `rejected` + flag `MEANING_MISMATCH`
- Word not in any dictionary → `rejected` + flag `LEMMA_NOT_FOUND`

**Examples (quran, hadith, poetry) are the strongest evidence.**

### ❷ هل اللمّة مرادف حقيقي؟ — Is it a true synonym?

Take a sentence from the evidence. Replace this lemma with each sibling.
Does the core meaning survive? Record the distinguishing nuance.

The `nuance` field is **mandatory** for every lemma — even true synonyms
have subtle differences (semantic focus, register, connotation).

### ❸ مرادفات مفقودة؟ — Missing synonyms?

Check three sources:
1. Reverse lookup candidates (synonym tables in per-lemma evidence)
2. Root family headwords
3. English bridge / ARABTERM results

For each candidate, apply the substitution test:
- True synonym → `add`
- More specific/general → `new_synset`
- Not synonymous → `reject`

---

## الإثراء — Enrichment

After the three questions, for each confirmed lemma:

| Field | Values |
|-------|--------|
| `usage` | `archaic` · `modern` · `common` |
| `eloquence` | `eloquent` · `neologism` · `colloquial` |
| `connotation` | `positive` · `negative` · `neutral` |
| `register` | `literal` or `figurative (type)` |
| `frame` | Verbs: `لازم` · `متعدٍ بنفسه` · `متعدٍ بـ(حرف)` |
| `collocate` | Typical collocate |

Also:
- Audit the AWN definition: `retain` / `revise` / `reject`
- Check the hypernym relation: `ok` / `flag`
- Assign overall verdict: `excellent` / `good` / `acceptable` / `poor`

---

## نصائح عملية — Practical Tips

1. **Evidence field is key** — every decision needs a dictionary citation.
2. **Nuance is mandatory** — even for obvious synonyms, note the distinction.
3. **Prefer Quranic/classical examples** — they settle disputes about core meaning.
4. **When unsure, flag** — better to escalate than to approve without evidence.
5. **ARABTERM bridge is useful** — shows technical/specialized usage.

---

## أمثلة — Examples

See [EXAMPLE_REVIEW.yaml](EXAMPLE_REVIEW.yaml) for a complete worked example
(`awn4-01572394-v` — ثبّت / ركّب — install).

Key decisions in that example:
- Both lemmas **confirmed** with evidence citations from الوسيط and الكبير
- Definition **retained** with source noted
- نَصَبَ proposed as a **new synset** (adjacent meaning, not synonym)
- Overall verdict: `good`
