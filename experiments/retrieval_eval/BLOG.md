# Dense vs Sparse Retrieval on Classical Arabic Dictionaries: Evaluating Mixedbread Wholembed v3 for Lexicographic Search

## TL;DR

We evaluated Mixedbread's Wholembed v3 dense retrieval against a SQL baseline (exact match + BM25 FTS5) for finding classical Arabic dictionary entries relevant to Arabic WordNet synsets. On 76 queries across 1,906 uploaded headword documents:

| Query Type | N | Recall@10 | Recall@50 | MRR |
|------------|---|-----------|-----------|-----|
| Arabic lemma | 38 | 88.8% | 97.1% | 0.830 |
| Definition keyword | 38 | 39.0% | 58.6% | 0.459 |
| **Overall** | 76 | 63.9% | 77.9% | 0.645 |

**Verdict:** Dense retrieval is surprisingly strong for Arabic headword lookup (97% Recall@50) and handles morphological variation naturally, but falls short on semantic definition matching. It complements rather than replaces the SQL pipeline.

---

## 1. Introduction

### The Retrieval Problem

The Arabic WordNet v4 (AWN4) project maintains ~12,000 Arabic synsets, each requiring linguistic validation against a comprehensive dictionary database. Our database contains **760,660 entries across 107 dictionaries** — from al-Khalīl ibn Aḥmad's *Kitāb al-ʿAyn* (8th century, the oldest Arabic dictionary) to modern technical term banks.

Validating each synset requires finding all relevant dictionary entries for its Arabic lemmas. The standard approach uses SQL queries:

- **Exact headword matching:** Normalized headword lookup against an indexed column. Given the Arabic lemma وَقْت (*waqt*, "time"), find all dictionary entries with matching headwords. This is precise but fragile — it requires a handcrafted normalization pipeline (strip diacritics, unify hamza variants ء→أ→إ→آ, normalize ى→ي) and misses morphological variants.
- **Keyword search:** BM25-ranked full-text search using SQLite FTS5, with tuned weights `(5.0, 3.0, 1.0)`. This handles partial matches but struggles with Arabic's rich morphology.

Together, these queries reliably surface relevant dictionary entries, but they tightly couple the retrieval pipeline to SQL generation. Each synset validation requires 3–5 queries with carefully crafted parameters.

### The Dense Retrieval Hypothesis

Could a single dense retrieval call replace this multi-query pipeline? Embedding-based retrieval promises:

- **Morphological robustness:** Arabic's trilateral root system, broken plurals, and 15+ verb forms make exact-match fragile. Embeddings could capture semantic equivalence across morphological variants without a handcrafted normalization pipeline.
- **Semantic matching:** A query like "time" should surface not just وقت (*waqt*) but also زمن (*zaman*), أوان (*awān*), and other temporal concepts — something exact-match SQL cannot do.
- **Pipeline simplification:** One API call instead of multiple SQL queries.

But dense retrieval also has known weaknesses for our use case:

- **Exact match precision:** When the query *is* the headword, BM25/exact-match is trivially perfect. Can embeddings match this?
- **Classical Arabic representation:** Most multilingual models are trained predominantly on Modern Standard Arabic. Classical Arabic (with archaic vocabulary, different orthographic conventions, and encyclopedic definitions spanning centuries) is underrepresented.

### Why Mixedbread

Mixedbread's Wholembed v3 claims #1 on MTEB across 100+ languages, including Arabic. Their Store API handles document chunking, embedding, indexing, and retrieval as a managed service — no infrastructure to maintain. The free tier (2M tokens ingestion, 100 queries/month, 10K files/store) allows a meaningful evaluation pilot.

---

## 2. Experiment Design

### 2.1 Corpus Preparation

We selected **15 classical Arabic dictionaries** from our database, prioritized by linguistic importance:

```python
PRIORITY_DICT_IDS = [
    103,  # Ibn Manẓūr, Lisān al-ʿArab (d. 1311) — THE classical Arabic dictionary
    120,  # Murtaḍa al-Zabīdī, Tāj al-ʿArūs (d. 1790) — most comprehensive
    113,  # Firuzabadi, al-Qāmūs al-Muḥīṭ (d. 1414)
    3,    # Kitab al-Ayn — oldest Arabic dictionary (~786 CE)
    145,  # Lane's Arabic-English Lexicon (d. 1876) — gold standard
    152,  # Ibn Sīda, al-Muḥkam (d. 1066)
    151,  # Ibn Fāris, Maqāyīs al-Lugha (d. 1004)
    150,  # al-Jawharī, al-Ṣiḥāḥ (d. 1003)
    153,  # al-Zamakhsharī, Asās al-Balāgha (d. 1143)
    # ... 6 more classical sources
]
```

These 15 dictionaries span approximately 1,100 years of Arabic lexicography (786–1883 CE), representing the canonical reference works that Arabic linguists consult.

**Grouping strategy:** Entries were grouped by normalized headword — one markdown file per unique headword, consolidating definitions from all available dictionaries. This mirrors how a human lexicographer works: looking up a word and seeing all available perspectives.

**Token budget management:** The free tier provides 2M tokens. We estimated Arabic text at ~3 characters/token — a rough heuristic, since Arabic tokenization varies significantly across models and tends toward fewer characters per token than English due to the script's complexity. To hedge against underestimation, we set a budget of 1.8M tokens, leaving a 200K safety buffer.

**Final export:** 1,906 files containing 7,141 entries (~3.7 entries per file on average), consuming approximately 1.8M tokens.

### 2.2 Document Format

Each uploaded file is structured markdown combining perspectives from multiple dictionaries on a single headword:

```markdown
# العَسْجَد (جذر: عسجد)

## Kitab Al-Ayn
*كتاب العين*
POS: noun

من الكلمات الرباعية الشاذة المعراة من حروف الذلق والشفوية

## Mujmal Al-Lugha
*مجمل اللغة*
POS: noun

الذهب

## Firuzabadi, al-Qāmūs al-Muḥīṭ (d. 1414 CE)
*القاموس المحيط للفيروزآبادي*

العَسْجَدُ: الذَّهَبُ، والجَوْهَرُ كُلُّه، كالدُّرِّ والياقوتِ...
```

This is العَسْجَد (*al-ʿasjad*, "gold/gemstones") — a rare quadrilateral noun. Three dictionaries weigh in: al-Khalīl's *Kitāb al-ʿAyn* notes its unusual morphological pattern, *Mujmal al-Lugha* gives a terse one-word definition (الذهب, "gold"), and al-Firuzabadi's *al-Qāmūs al-Muḥīṭ* elaborates with multiple senses including "gold," "all precious stones," and even "a large camel."

Rich entries consolidate up to 12 dictionary sources spanning 9+ lexicographic traditions. For example, the entry for أَرَث (to kindle / inheritance root) includes perspectives from al-Ṣiḥāḥ (d. 1003), Ibn Sīda (d. 1066), al-Zamakhsharī (d. 1143), Ibn al-Athīr (d. 1210), Lisān al-ʿArab (d. 1311), al-Qāmūs al-Muḥīṭ (d. 1414), Tāj al-ʿArūs (d. 1790), and Lane's Lexicon (d. 1876).

Definitions were truncated at 2,000 characters per entry, and examples capped at 5 per dictionary source, to control token usage while preserving the most salient content.

### 2.3 Upload and Indexing

Upload used the Mixedbread Python SDK's Store API:

```python
from mixedbread import Mixedbread

mxbai = Mixedbread(api_key=key)
store = mxbai.stores.create(name="awn4-classical-arabic-dict")

for filepath in sorted(entries_dir.glob("*.md")):
    mxbai.stores.files.upload(store_identifier=store.id, file=filepath)
```

All 1,906 files uploaded successfully (0 failures). The Store API handles chunking and indexing automatically — we had no control over chunk size, overlap, or embedding model configuration. This is a trade-off: less tuning surface but also less room for optimization.

### 2.4 Ground Truth Construction

To evaluate retrieval quality, we need to know which dictionary entries are relevant for each synset. We pre-computed this ground truth by running structured SQL queries against the full 760K-entry database:

1. **Headword batch lookup:** For each synset's Arabic lemmas, find all dictionary entries whose normalized headword matches any lemma term. For example, a synset with lemmas وقت and زمن ("time") returns all entries from all dictionaries that define these headwords.
2. **Enrichment:** Fetch the full definitions, usage examples, and morphological data (plurals, verbal forms) for each matched entry.

This gives us the exhaustive set of dictionary entries that SQL retrieval would return for each synset. An important caveat: since the ground truth is *derived from* SQL queries, the SQL baseline achieves 100% recall by definition — it is not an independent evaluation, but rather the ceiling against which we measure dense retrieval. We then mapped this ground truth to our uploaded corpus: since the SQL baseline searches all 107 dictionaries but we only uploaded entries from 15, we filtered ground truth to only include entries present in the Store.

We selected **38 synsets** for evaluation, spanning a range of Arabic WordNet categories (abstract concepts, physical objects, actions, properties). Each synset was evaluated with two query types, giving us **76 total queries**.

### 2.5 Query Types

We constructed two query types per synset, representing different retrieval scenarios:

| Query Type | Query Construction | What It Tests |
|------------|-------------------|---------------|
| `arabic_lemma` | Space-joined Arabic lemma terms from the synset | Can dense retrieval match exact headword lookup? |
| `definition_keyword` | Full Arabic definition of the synset, sent verbatim | Can dense retrieval bridge from a definition to relevant headwords? |

Example queries for synset `awn4-00028468-n` (time — الوقت/الزمن):
- **Arabic lemma:** `"زمن وقت"` — the two Arabic terms for "time"
- **Definition keyword:** `"تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر الحاضر إلى الماضي"` — "the continuum of experience in which events pass from the future through the present to the past"

Each query was run against the Store API with top-K set to 50:

```python
response = mxbai.stores.search(
    query=qinfo["query"],
    store_identifiers=[store_id],
    top_k=50,
)
```

---

## 3. Results

### 3.1 Overall Metrics

| Query Type | N | Recall@10 | Recall@25 | Recall@50 | P@10 | MRR | Avg GT (headwords) |
|------------|---|-----------|-----------|-----------|------|-----|-------------------|
| arabic_lemma | 38 | 88.8% | 93.6% | 97.1% | 17.1% | 0.830 | 2.1 |
| definition_keyword | 38 | 39.0% | 52.9% | 58.6% | 7.6% | 0.459 | 2.1 |
| **Overall** | 76 | 63.9% | 73.2% | 77.9% | 12.4% | 0.645 | — |

*Avg GT counts unique headword files (not individual dictionary entries). A headword file may consolidate entries from multiple dictionaries.*

**Baseline comparison:** As noted in Section 2.4, the SQL baseline achieves 100% recall by definition — the ground truth was derived from those same SQL queries. Dense retrieval's Recall@50 of 97.1% on lemma queries, measured against this ceiling, comes remarkably close.

### 3.2 Arabic Lemma Queries: Near-Perfect Retrieval

The headline result: **dense retrieval achieves 97.1% Recall@50 on Arabic headword lookup**, approaching the SQL exact-match baseline.

- **MRR = 0.830:** The first relevant result lands at rank 1 in 76% of queries, rank 2 in 5%, and rank 3+ in the remaining 18%. While the correct headword is *usually* the top result, the 18% tail where it drops to rank 3 or beyond is non-trivial.
- The 88.8% Recall@10 shows that even a shallow retrieval window captures most ground truth.
- The Recall@10→Recall@50 gain (+8.3 percentage points) indicates a small tail of queries where the correct entry ranks between 11th and 50th.

This is a strong result considering Wholembed v3 has no Arabic-specific normalization. Our SQL baseline requires a handcrafted pipeline (strip diacritics, unify hamza variants ء→أ→إ→آ, normalize ى→ي) before matching. Dense retrieval handles this implicitly in the embedding space.

### 3.3 Definition Keyword Queries: Semantic Gap

Sending the full Arabic definition as a query yields significantly weaker results:

- **Recall@50 = 58.6%** — roughly 3 in 5 ground-truth entries are found
- **MRR = 0.459** — the first relevant result is typically around rank 2–3
- **Recall@10 = 39.0%** — most relevant entries are *not* in the first page of results

This is expected. The task here is fundamentally different: given a synset definition like `"تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر الحاضر إلى الماضي"` (the continuum of experience in which events pass from the future through the present to the past), find dictionary entries whose headword is semantically related. This requires the embedding model to bridge from a definition to the lexicographic entries defining the corresponding word — a harder semantic similarity task than matching headwords.

Interestingly, many of the "false positives" are semantically relevant. For the time synset, the dense retrieval surfaces entries like حَدَث (*ḥadath*, "event/occurrence") and إِذْ (*idh*, a temporal conjunction) — words conceptually related to time even though they aren't in the ground truth. This is a property unique to dense retrieval: it finds semantically adjacent entries that BM25 keyword search would miss entirely.

A fairer comparison would require extracting specific keywords from the definition before querying, rather than sending the full text verbatim. We discuss this as a future improvement in Section 6.

---

## 4. Worked Example: وقت / زمن (Time)

To make the evaluation concrete, let's trace one query end-to-end. We deliberately chose a synset with richer-than-average ground truth (4 headword files vs. the 2.1 average) to illustrate multi-headword retrieval dynamics. Typical queries with 1–2 ground truth headwords exhibit the same patterns but with less to show.

**Synset:** `awn4-00028468-n` — time: *"the continuum of experience in which events pass from the future through the present to the past"*
**Arabic lemmas:** زمن (*zaman*), وقت (*waqt*)

### Ground Truth

SQL headword lookup against the full database finds 29 dictionary entries across 4 headword forms:
- **وقت** (*waqt*) — 14 entries from Kitāb al-ʿAyn, Lisān al-ʿArab, Tāj al-ʿArūs, Lane's Lexicon, and 10 other classical sources → uploaded as `hw_0097592.md`
- **الوقت** (*al-waqt*, with definite article) — 1 entry from al-Qāmūs al-Muḥīṭ → uploaded as `hw_0802304.md`
- **زمن** (*zaman*) — 13 entries across the same major dictionaries → uploaded as `hw_0099249.md`
- **الزمن** (*al-zaman*, with definite article) — 1 entry from al-Qāmūs al-Muḥīṭ → uploaded as `hw_0798577.md`

These 29 entries map to 4 uploaded files — our ground truth for this query.

### Arabic Lemma Retrieval

Query: `"زمن وقت"` → Mixedbread returns 50 ranked chunks. Here are the top 12:

| Rank | File | Headword | Score | Notes |
|------|------|----------|-------|-------|
| 1 | `hw_0097592.md` | وقت | **0.802** | Kitāb al-ʿAyn section |
| 2 | `hw_0097592.md` | وقت | 0.797 | Lane's Lexicon section |
| 3 | `hw_0097592.md` | وقت | 0.779 | Tāj al-ʿArūs section |
| 4 | `hw_0802304.md` | **الوقت** | **0.769** | al-Qāmūs al-Muḥīṭ (with ال prefix) |
| 5 | `hw_0099249.md` | **زمن** | **0.757** | Kitāb al-ʿAyn section |
| 6 | `hw_0097592.md` | وقت | 0.744 | Another dictionary section |
| 7 | `hw_0100081.md` | أوان | 0.730 | *"time/season"* — semantically related! |
| 8 | `hw_0099249.md` | زمن | 0.715 | Lane's Lexicon section |
| 9 | `hw_0099249.md` | زمن | 0.711 | Another dictionary section |
| 10 | `hw_0099249.md` | زمن | 0.677 | Another dictionary section |
| 11 | `hw_0798577.md` | **الزمن** | **0.673** | Last GT headword found |
| 12 | `hw_0099759.md` | إذ | 0.649 | Temporal conjunction — semantically related |

### Analysis

**All 4 ground truth headwords are found by rank 11.** Three of four appear in the top 10:

- **Ranks 1–3, 6:** Four chunks from `hw_0097592.md` (وقت), each from a different dictionary section within the consolidated document. The top score of 0.802 is the highest we observed across all evaluated queries.
- **Rank 4:** The definite-article variant الوقت (*al-waqt*) appears as a separate file. Despite being a different surface form, the embedding space correctly identifies it as highly relevant — a capability exact-match SQL would only achieve with explicit normalization.
- **Rank 5, 8–10:** Four chunks from `hw_0099249.md` (زمن), the second key lemma.
- **Rank 7:** أوان (*awān*, "time/season") — this is *not* in our ground truth, but is a genuine near-synonym. Dense retrieval surfaces this semantic neighbor that SQL exact-match would never find.
- **Rank 11:** الزمن (*al-zaman*), the last ground truth headword. The definite-article form with its single dictionary entry ranks slightly lower, likely because the document has fewer chunks to contribute.

**Metrics for this query:** Recall@10 = 75% (3 of 4 headwords), Recall@50 = 100% (all 4 found), MRR = 1.0 (first relevant at rank 1).

### Definition Keyword Retrieval (Same Synset)

Query: `"تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر الحاضر إلى الماضي"` → a much harder task.

| Rank | File | Headword | Score | Relevant? |
|------|------|----------|-------|-----------|
| 1 | `hw_0099249.md` | زمن | 0.506 | **GT** |
| 2 | `hw_0099249.md` | زمن | 0.504 | GT (different chunk) |
| 3 | `hw_0099759.md` | إذ | 0.490 | Temporal conjunction |
| 4 | `hw_0099249.md` | زمن | 0.489 | GT (different chunk) |
| 5 | `hw_0099249.md` | زمن | 0.475 | GT (different chunk) |
| 6 | `hw_0095718.md` | حدث | 0.475 | "event" — semantic neighbor |
| 7 | `hw_0099088.md` | نسا | 0.471 | "to delay/forget" |
| 8 | `hw_0099759.md` | إذ | 0.464 | Temporal conjunction |
| 9 | `hw_0100081.md` | أوان | 0.463 | "time/season" |
| 10 | `hw_0096496.md` | قهقر | 0.462 | "to go backwards" |

Only 1 of 4 ground truth headwords (زمن) appears in the top 10. Extending the window: الزمن surfaces at rank 18 and وقت at rank 20, bringing Recall@25 to 75%. But الوقت never appears in the top 50 — **Recall@50 = 75% (3/4)**. The scores are uniformly low (0.46–0.51) with no clear separation between relevant and irrelevant results. Notice, however, that the "false positives" are semantically coherent: إذ (temporal conjunction), حدث (event/occurrence), أوان (time/season), and قهقر (to go backwards) all relate to the concept of time. The embedding model captures the semantic field, but can't reliably distinguish the *defining* headwords from the *related* ones.

This contrast between the two query types — 100% Recall@50 for the lemma query vs 25% Recall@10 (75% Recall@50) for the definition — illustrates why dense retrieval excels at headword matching but struggles with definition-to-headword bridging.

---

## 5. Technical Insights

### 5.1 Auto-Chunking and Document-Level Deduplication

The Mixedbread Store API returns ranked *chunks*, not documents. A single uploaded file may appear multiple times in results with different scores — as we saw with وقت appearing at ranks 1, 2, 3, and 6 with scores ranging from 0.802 to 0.744. Our evaluation pipeline deduplicates at the headword level:

```python
# Map chunk filenames back to headwords via the export manifest
filename_to_hw = {}
for hw, info in manifest.items():
    filename_to_hw[info["filename"]] = hw

# Build the ordered list of retrieved headwords (preserving rank order)
retrieved_hws = []
for chunk in result["retrieved"]:
    basename = Path(chunk["filename"]).name
    hw = filename_to_hw.get(basename)
    if hw:
        retrieved_hws.append(hw)

# Recall@K compares set intersection
found = set(retrieved_hws[:k]) & gt_headwords
recall = len(found) / len(gt_headwords)
```

This chunk→document→headword deduplication is standard in passage retrieval evaluation (similar to MS MARCO's document-level metrics), but it has an important implication: **larger documents with more dictionary entries get proportionally more chunks and more chances to match**. The وقت file (14 entries from 14 dictionaries) produces 4 chunks in the top 10, while الوقت (1 entry from 1 dictionary) produces only 1. This could bias retrieval toward common headwords that appear in many dictionaries — arguably a desirable property for lexicographic search, where well-attested words are more useful than rare hapax legomena.

### 5.2 Arabic Morphological Handling Without Preprocessing

One of the most interesting findings is that Wholembed v3 handles Arabic morphological variation implicitly:

- **Definite article:** Both وقت and الوقت (with prefix ال) are retrieved for the query `"زمن وقت"`, despite being stored as separate files. Our SQL baseline requires explicit normalization to search for both forms.
- **Diacritics:** Fully diacriticized text in the dictionary entries (e.g., الذَّهَبُ with *shadda* and *ḍamma*) matches undiacriticized queries seamlessly. This is significant because classical Arabic texts use heavy diacritization while modern queries typically omit diacritics.
- **Semantic bridging:** The query `"زمن وقت"` surfaces أوان (*awān*, "time/season") at rank 7 — a genuine near-synonym that shares no morphological root with either query term. BM25 would completely miss this connection without synonym expansion.

This suggests the embedding space effectively collapses Arabic morphological variants, a valuable property for lexicographic search where users may query with any form of a word.

### 5.3 Score Distribution and Relevance Cutoff

Examining the score distributions reveals a clear pattern across query types:

- **Lemma queries produce high scores:** The وقت example tops out at 0.802, with relevant results clustering in the 0.67–0.80 range. Semantically related but non-GT entries (أوان at 0.730) fall within this range too, making score-based thresholding unreliable.
- **Definition queries produce low scores:** The same synset's definition query tops out at only 0.506, with relevant and irrelevant results nearly indistinguishable (0.46–0.51 range).
- **The gap between relevant and irrelevant is narrow** in both cases (~0.03–0.05), consistent with findings in other dense retrieval evaluations.

This confirms that cosine similarity scores from neural models don't have a universal "relevance threshold." Rank-based cutoffs (top-K) are more robust than score-based cutoffs for this kind of retrieval.

### 5.4 Why Precision@10 Is Low (And Why That's OK)

Our Precision@10 of 17.1% for lemma queries looks concerning at first glance. But consider the denominator: with an average of only 2.1 ground-truth headwords per query and 10 retrieved results, the maximum achievable P@10 is ~21%. Our 17.1% is actually **81% of this theoretical maximum**.

This is a classic issue with sparse ground truth in retrieval evaluation. When evaluating against a small set of known-relevant documents, many "false positives" may actually be relevant documents that aren't in the ground truth. A dictionary entry about a semantically related concept (e.g., أوان "time/season" appearing when searching for وقت "time") might be genuinely useful even though it's not in our reference set.

### 5.5 Token Economics

Our free-tier evaluation covers only a **sample** of the 15 priority dictionaries — 1,906 of 28,722 unique headwords (6.6%), or 7,141 of 97,014 total entries (7.4%). The token scaling for broader coverage:

| Scope | Entries | Est. Tokens | Notes |
|-------|---------|-------------|-------|
| This evaluation (sample) | 7,141 | ~1.8M | 6.6% of 15-dict headwords |
| Full 15 priority dicts | 97,014 | ~24M | All entries from our selected sources |
| All non-ARABTERM dicts (56) | 343,234 | ~87M | OCR + Hawramani classical sources |
| Full DB (107 dicts) | 760,660 | ~192M | Including ARABTERM modern terms |

Estimates use ~252 tokens/entry, the average from our exported sample. Actual token usage may vary — the 15 priority dictionaries include the most comprehensive classical sources (Lisān al-ʿArab, Tāj al-ʿArūs), whose entries tend to be longer than average.

For a production deployment, the relevant comparison is: what does this cost vs. running a local SQLite instance (essentially free, with unlimited queries)?

---

## 6. Conclusion

### What We Found

1. **Arabic lemma retrieval works remarkably well** (97% Recall@50, MRR 0.830). Wholembed v3 can find classical Arabic dictionary entries from headword queries with near-perfect recall, handling morphological variation that would require explicit normalization in a SQL pipeline.

2. **Semantic definition matching is moderate** (59% Recall@50, MRR 0.459). Sending a full Arabic synset definition as a query finds relevant entries about 60% of the time — useful as a complement but insufficient as a primary retrieval method. However, the "false positives" are often semantically relevant entries that enrich the search results.

3. **Arabic morphological robustness is a standout feature.** Dense retrieval naturally handles definite article prefixes (وقت/الوقت), diacritization differences, and surfaces genuine synonyms (أوان for وقت) — capabilities that would each require dedicated engineering in a SQL pipeline.

**Important caveat on the 97% headline:** Our 38 evaluated synsets are biased toward common, high-frequency Arabic words — those most likely to appear in the 15 priority classical dictionaries. The 97% Recall@50 may not generalize to rare terms, domain-specific vocabulary, or headwords attested only in minor lexicographic sources. Evaluating on a broader, more representative sample (requiring a larger uploaded corpus) is needed to establish generalizability.

### Could Dense Retrieval Replace SQL?

| Retrieval Task | Dense Retrieval Performance | Verdict |
|----------------|---------------------------|---------|
| Headword exact match | 97% Recall@50, MRR 0.83 | Augment, not replace — 3% miss rate matters for comprehensive lexicographic review |
| Definition → headword | 59% Recall@50, MRR 0.46 | No — too much recall loss for a primary method |

**Our recommendation:** Use dense retrieval as an **augmentation layer**, not a replacement. The strongest use case is for queries where the exact headword form is unknown — embedding search can bridge morphological and semantic gaps that exact-match SQL cannot.

A hybrid architecture — SQL for exact-match reliability, dense retrieval for fuzzy/semantic search — would combine the strengths of both approaches. In practice, this means running SQL first for guaranteed exact matches, then using dense retrieval to discover related headwords that SQL would miss.

### What We'd Do Differently

1. **Extract keywords from definitions** before querying, rather than sending the full definition verbatim. The low definition-keyword scores (0.46–0.51) suggest the model struggles with long, complex Arabic sentences as queries.
2. **Test with a larger corpus** on the paid tier for broader coverage and more statistically robust evaluation across rare and domain-specific terms.
3. **Compare against local embeddings** (mxbai-embed-large-v1 via HuggingFace) for cost analysis — the same model family may be available for self-hosting, eliminating per-query costs.
4. **Add per-dictionary breakdown** to detect retrieval quality differences between data sources (e.g., do entries from Lane's Lexicon, which contains English translations, retrieve differently than purely Arabic sources?).
5. **Test cross-lingual retrieval** (English query → Arabic dictionary results) by including bilingual dictionary entries, to evaluate whether the multilingual embedding space can bridge the language gap for lexicographic search.

---

## Appendix: Experiment Configuration

| Parameter | Value |
|-----------|-------|
| **Store ID** | `de176737-c05d-4364-9d14-2f2860c552a0` |
| **Store name** | `awn4-classical-arabic-dict` |
| **Created** | 2026-03-13 |
| **Files uploaded** | 1,906 (0 failures) |
| **Total entries** | 7,141 across 15 classical dictionaries |
| **Estimated tokens** | ~1.8M of 2M free tier |
| **Synsets evaluated** | 38 (76 queries: 38 lemma + 38 definition) |
| **Errors** | 0 |

**Source code:** All evaluation scripts are in `experiments/mixedbread_retrieval_eval/`:
- `export_entries.py` — Export pipeline (SQLite → markdown, 15 priority dictionaries, token budget)
- `upload_store.py` — Store creation and file upload via Mixedbread SDK
- `evaluate_retrieval.py` — Query execution and result recording
- `analysis.py` — Metrics computation (Recall@K, MRR, P@10)
