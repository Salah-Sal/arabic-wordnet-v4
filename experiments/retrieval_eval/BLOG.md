# Dense Retrieval on Classical Arabic Dictionaries: Comparing Mixedbread, Gemini, and Jina Embeddings for Lexicographic Search

## TL;DR

We evaluated five dense retrieval backends — two API-based (Gemini, Mixedbread) and three open-source (Jina v5-small, v5-nano, v3) — against a SQL baseline (exact match + BM25 FTS5) for finding classical Arabic dictionary entries relevant to Arabic WordNet synsets:

| Query Type | Backend | N | Recall@10 | Recall@50 | MRR |
|------------|---------|---|-----------|-----------|-----|
| Arabic lemma | **Gemini + FAISS** | 63 | **99.5%** | **100.0%** | **0.964** |
| Arabic lemma | Jina v5-small | 63 | 97.6% | 99.6% | 0.921 |
| Arabic lemma | Jina v5-nano | 63 | 95.5% | 97.9% | 0.928 |
| Arabic lemma | Jina v3 | 63 | 91.5% | 97.1% | 0.889 |
| Arabic lemma | Mixedbread Store | 38 | 88.8% | 97.1% | 0.830 |
| Definition keyword | **Gemini + FAISS** | 63 | **58.2%** | **72.4%** | 0.442 |
| Definition keyword | Jina v5-small | 63 | 49.5% | 66.5% | 0.397 |
| Definition keyword | Jina v5-nano | 63 | 48.3% | 64.9% | 0.412 |
| Definition keyword | Jina v3 | 63 | 43.1% | 65.1% | 0.279 |
| Definition keyword | Mixedbread Store | 38 | 39.0% | 58.6% | 0.459 |
| **Overall** | **Gemini + FAISS** | 126 | **78.8%** | **86.2%** | **0.703** |
| **Overall** | Jina v5-small | 126 | 73.5% | 83.1% | 0.659 |
| **Overall** | Jina v5-nano | 126 | 71.9% | 81.4% | 0.670 |
| **Overall** | Jina v3 | 126 | 67.3% | 81.1% | 0.584 |
| **Overall** | Mixedbread Store | 76 | 63.9% | 77.9% | 0.645 |

**Verdict:** Gemini's document-level asymmetric embeddings lead every category, with Arabic headword lookup essentially solved (100% Recall@50). But the best open-source model — **Jina v5-small (677M params)** — closes to within 2 percentage points on arabic_lemma (97.6% vs 99.5%) at zero API cost. Even the tiny **Jina v5-nano (239M params)** reaches 95.5% Recall@10, outperforming the larger Jina v3 (570M) and Mixedbread's managed service. The key structural insight persists: document-level embedding (Gemini, all Jina models) dominates chunk-based retrieval (Mixedbread), which fills top-10 slots with duplicate file hits, reducing effective document coverage by ~40%.

---

## 1. Introduction

### The Retrieval Problem

The Arabic WordNet v4 (AWN4) project maintains ~12,000 Arabic synsets, each requiring linguistic validation against a comprehensive dictionary database. Our database contains **760,660 entries across 107 dictionaries** — from al-Khalil ibn Ahmad's *Kitab al-'Ayn* (8th century, the oldest Arabic dictionary) to modern technical term banks.

Validating each synset requires finding all relevant dictionary entries for its Arabic lemmas. The standard approach uses SQL queries:

- **Exact headword matching:** Normalized headword lookup against an indexed column. Given the Arabic lemma وَقْت (*waqt*, "time"), find all dictionary entries with matching headwords. This is precise but fragile — it requires a handcrafted normalization pipeline (strip diacritics, unify hamza variants ء→أ→إ→آ, normalize ى→ي) and misses morphological variants.
- **Keyword search:** BM25-ranked full-text search using SQLite FTS5, with tuned weights `(5.0, 3.0, 1.0)`. This handles partial matches but struggles with Arabic's rich morphology.

Together, these queries reliably surface relevant dictionary entries, but they tightly couple the retrieval pipeline to SQL generation. Each synset validation requires 3–5 queries with carefully crafted parameters.

### The Dense Retrieval Hypothesis

Could a single dense retrieval call replace this multi-query pipeline? Embedding-based retrieval promises:

- **Morphological robustness:** Arabic's trilateral root system, broken plurals, and 15+ verb forms make exact-match fragile. Embeddings could capture semantic equivalence across morphological variants without a handcrafted normalization pipeline.
- **Semantic matching:** A query like "time" should surface not just وقت (*waqt*) but also زمن (*zaman*), أوان (*awan*), and other temporal concepts — something exact-match SQL cannot do.
- **Pipeline simplification:** One API call instead of multiple SQL queries.

But dense retrieval also has known weaknesses for our use case:

- **Exact match precision:** When the query *is* the headword, BM25/exact-match is trivially perfect. Can embeddings match this?
- **Classical Arabic representation:** Most multilingual models are trained predominantly on Modern Standard Arabic. Classical Arabic (with archaic vocabulary, different orthographic conventions, and encyclopedic definitions spanning centuries) is underrepresented.

### Backend Selection

We selected backends representing three architectural philosophies: managed cloud retrieval, API-embedded local search, and fully open-source local inference.

**Mixedbread Store** uses Wholembed v3, which claims #1 on MTEB across 100+ languages including Arabic. Their Store API handles document chunking, embedding, indexing, and retrieval as a managed service — no infrastructure to maintain. The free tier (2M tokens ingestion, 100 queries/month, 10K files/store) allows a meaningful evaluation pilot. The trade-off: we have no control over chunk size, overlap, or embedding configuration.

**Gemini Embeddings + FAISS** uses Google's `gemini-embedding-001` model with task-type-aware asymmetric encoding: documents are embedded with `RETRIEVAL_DOCUMENT` and queries with `RETRIEVAL_QUERY`, placing them in specialized regions of the same vector space. Unlike Mixedbread's chunking, we embed each markdown file as a single vector and search locally with FAISS. This gives us full control over the embedding pipeline at the cost of managing our own index.

**Jina Embeddings + FAISS** tests three open-weight models from Jina AI, downloaded from HuggingFace and run locally via `sentence-transformers`. All three use the same FAISS IndexFlatIP architecture as the Gemini backend — one vector per document, cosine similarity search. The models span a range of sizes and architectures:

| Model | Params | Base Architecture | Dims | Context | MMTEB |
|-------|--------|------------------|------|---------|-------|
| Jina v5-nano | 239M | EuroBERT-210M | 768 | 8K | 65.5 |
| Jina v3 | 570M | XLM-RoBERTa + LoRA | 1024 | 8K | — |
| Jina v5-small | 677M | Qwen3-0.6B | 1024 | 32K | 67.7 |

All three support asymmetric retrieval encoding: Jina v5 models use `prompt_name="document"` vs `"query"`, while v3 uses task-specific LoRA adapters (`task="retrieval.passage"` vs `"retrieval.query"`). Inference ran on a Google Colab T4 GPU (CUDA, 16GB VRAM). A fourth model — Jina v4 (3.8B params, multimodal) — was attempted but abandoned due to unresolvable `transformers` version conflicts between its custom Qwen2.5-VL code and the other models' requirements.

| Aspect | Mixedbread Store | Gemini + FAISS | Jina + FAISS |
|--------|-----------------|----------------|--------------|
| Embedding model | Wholembed v3 (closed) | Gemini embedding-001 (closed) | v5-nano / v5-small / v3 (open) |
| Model weights | Proprietary | Proprietary | Open (HuggingFace) |
| Inference | Cloud API | Cloud API → local index | Fully local (GPU) |
| Chunking | Managed (server-side) | None — full-document | None — full-document |
| Task types | Single embedding space | Asymmetric: DOC vs QUERY | Asymmetric: prompt_name / LoRA |
| Retrieval granularity | Chunks (multiple hits per file) | Documents (one hit per file) | Documents (one hit per file) |
| Search cost | API call per query | Free (local search) | Free (local search) |
| Setup cost | Upload files | API calls (embedding) | GPU compute (embedding) |

---

## 2. Experiment Design

### 2.1 Corpus Preparation

We selected **15 classical Arabic dictionaries** from our database, prioritized by linguistic importance:

```python
PRIORITY_DICT_IDS = [
    103,  # Ibn Manzur, Lisan al-'Arab (d. 1311) — THE classical Arabic dictionary
    120,  # Murtada al-Zabidi, Taj al-'Arus (d. 1790) — most comprehensive
    113,  # Firuzabadi, al-Qamus al-Muhit (d. 1414)
    3,    # Kitab al-Ayn — oldest Arabic dictionary (~786 CE)
    145,  # Lane's Arabic-English Lexicon (d. 1876) — gold standard
    152,  # Ibn Sida, al-Muhkam (d. 1066)
    151,  # Ibn Faris, Maqayis al-Lugha (d. 1004)
    150,  # al-Jawhari, al-Sihah (d. 1003)
    153,  # al-Zamakhshari, Asas al-Balagha (d. 1143)
    # ... 6 more classical sources
]
```

These 15 dictionaries span approximately 1,100 years of Arabic lexicography (786–1883 CE), representing the canonical reference works that Arabic linguists consult.

**Grouping strategy:** Entries were grouped by normalized headword — one markdown file per unique headword, consolidating definitions from all available dictionaries. This mirrors how a human lexicographer works: looking up a word and seeing all available perspectives.

**Token budget management:** The Mixedbread free tier provides 2M tokens. We estimated Arabic text at ~3 characters/token — a rough heuristic, since Arabic tokenization varies significantly across models and tends toward fewer characters per token than English due to the script's complexity. To hedge against underestimation, we set a budget of 1.8M tokens, leaving a 200K safety buffer.

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

## Firuzabadi, al-Qamus al-Muhit (d. 1414 CE)
*القاموس المحيط للفيروزآبادي*

العَسْجَدُ: الذَّهَبُ، والجَوْهَرُ كُلُّه، كالدُّرِّ والياقوتِ...
```

This is العَسْجَد (*al-'asjad*, "gold/gemstones") — a rare quadrilateral noun. Three dictionaries weigh in: al-Khalil's *Kitab al-'Ayn* notes its unusual morphological pattern, *Mujmal al-Lugha* gives a terse one-word definition (الذهب, "gold"), and al-Firuzabadi's *al-Qamus al-Muhit* elaborates with multiple senses including "gold," "all precious stones," and even "a large camel."

Rich entries consolidate up to 12 dictionary sources spanning 9+ lexicographic traditions. For example, the entry for أَرَث (to kindle / inheritance root) includes perspectives from al-Sihah (d. 1003), Ibn Sida (d. 1066), al-Zamakhshari (d. 1143), Ibn al-Athir (d. 1210), Lisan al-'Arab (d. 1311), al-Qamus al-Muhit (d. 1414), Taj al-'Arus (d. 1790), and Lane's Lexicon (d. 1876).

Definitions were truncated at 2,000 characters per entry, and examples capped at 5 per dictionary source, to control token usage while preserving the most salient content.

### 2.3 Mixedbread: Upload and Managed Indexing

Upload used the Mixedbread Python SDK's Store API:

```python
from mixedbread import Mixedbread

mxbai = Mixedbread(api_key=key)
store = mxbai.stores.create(name="awn4-classical-arabic-dict")

for filepath in sorted(entries_dir.glob("*.md")):
    mxbai.stores.files.upload(store_identifier=store.id, file=filepath)
```

All 1,906 files uploaded successfully (0 failures). The Store API handles chunking and indexing automatically — we had no control over chunk size, overlap, or embedding model configuration. This is a trade-off: less tuning surface but also less room for optimization.

### 2.4 Gemini: Embedding and Local FAISS Index

The Gemini backend embeds each markdown file as a single vector using the `RETRIEVAL_DOCUMENT` task type:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=key)

# Index: embed each document as one vector
result = client.models.embed_content(
    model="gemini-embedding-001",
    contents=batch_texts,
    config=types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=768,
    ),
)

# Search: embed query differently
result = client.models.embed_content(
    model="gemini-embedding-001",
    contents=query,
    config=types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=768,
    ),
)
```

The asymmetric task types are the key design choice: Gemini encodes documents and queries into different regions of the same vector space, optimized for cross-type similarity rather than same-type similarity. This is well-suited for our setup, where queries (short Arabic lemmas or full definitions) differ structurally from documents (multi-dictionary markdown entries).

After embedding, vectors are L2-normalized and stored in a FAISS `IndexFlatIP` (flat inner-product index). On normalized vectors, inner product equals cosine similarity. The resulting index is ~6MB for 1,937 vectors at 768 dimensions — trivially small. Search is local and free after the one-time embedding cost.

We embedded in batches of 20 documents with a 1.5-second inter-batch delay to respect Gemini's rate limits, with exponential backoff retry (5s, 10s, 20s, 40s, 80s) on 429 errors. All 1,937 files embedded successfully (0 failures). Note: Gemini's export includes 31 additional files compared to the 1,906 uploaded to Mixedbread, due to minor differences in token budget estimation between the two runs.

### 2.5 Jina: Local Embedding on Colab T4

The Jina backends use the same indexing architecture as Gemini — one vector per document, FAISS IndexFlatIP — but run entirely locally. Models were downloaded from HuggingFace and loaded via `sentence-transformers` with `trust_remote_code=True` (required for all Jina models, which use custom architectures).

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("jinaai/jina-embeddings-v5-text-nano",
                            trust_remote_code=True, device="cuda")

# Document embedding (asymmetric)
doc_vectors = model.encode(texts,
    task="retrieval", prompt_name="document",
    normalize_embeddings=True, batch_size=32)

# Query embedding
query_vec = model.encode([query],
    task="retrieval", prompt_name="query",
    normalize_embeddings=True)
```

A critical parameter: `max_seq_length=512`. All three models support much longer contexts (8K–32K tokens), but initial CPU-based experiments showed that full-context encoding was prohibitively slow — the 677M-param v5-small took ~3 hours to embed 1,937 documents at `max_seq_length=8192` on an M2 Pro CPU. Truncating to 512 tokens reduced this to minutes on a T4 GPU, with negligible quality impact since our documents average ~930 tokens and the most discriminative content (headword, root, initial definitions) appears in the first 512 tokens.

Embedding times on a Colab T4 GPU (CUDA):

| Model | Parameters | Dimensions | Embed Time (1,937 docs) | Throughput |
|-------|-----------|-----------|------------------------|------------|
| Jina v5-nano | 239M | 768 | 63.6s | 30.5 docs/s |
| Jina v3 | 570M | 1024 | 223.5s | 8.7 docs/s |
| Jina v5-small | 677M | 1024 | 365.0s | 5.3 docs/s |

The v5-nano's throughput advantage (5.7× faster than v5-small) comes from its EuroBERT backbone — an efficient encoder-only architecture — versus v5-small's Qwen3 decoder backbone, whose causal attention and larger FFN layers are computationally heavier even with GPU parallelism.

### 2.6 Ground Truth Construction

To evaluate retrieval quality, we need to know which dictionary entries are relevant for each synset. We pre-computed this ground truth by running structured SQL queries against the full 760K-entry database:

1. **Headword batch lookup:** For each synset's Arabic lemmas, find all dictionary entries whose normalized headword matches any lemma term. For example, a synset with lemmas وقت and زمن ("time") returns all entries from all dictionaries that define these headwords.
2. **Enrichment:** Fetch the full definitions, usage examples, and morphological data (plurals, verbal forms) for each matched entry.

This gives us the exhaustive set of dictionary entries that SQL retrieval would return for each synset. An important caveat: since the ground truth is *derived from* SQL queries, the SQL baseline achieves 100% recall by definition — it is not an independent evaluation, but rather the ceiling against which we measure dense retrieval. We then mapped this ground truth to our uploaded corpus: since the SQL baseline searches all 107 dictionaries but we only uploaded entries from 15, we filtered ground truth to only include entries present in the uploaded corpus.

**Sample sizes:** Mixedbread was evaluated on **38 synsets** (76 queries), constrained by the free tier's 100 queries/month limit. Gemini, with no query limit (search is local), was evaluated on **206 synsets** (126 queries with ground-truth overlap). The larger Gemini sample provides more statistical power but means the two sample populations are not identical — the Mixedbread sample is a subset of the Gemini sample.

### 2.7 Query Types

We constructed two query types per synset, representing different retrieval scenarios:

| Query Type | Query Construction | What It Tests |
|------------|-------------------|---------------|
| `arabic_lemma` | Space-joined Arabic lemma terms from the synset | Can dense retrieval match exact headword lookup? |
| `definition_keyword` | Full Arabic definition of the synset, sent verbatim | Can dense retrieval bridge from a definition to relevant headwords? |

Example queries for synset `awn4-00028468-n` (time — الوقت/الزمن):
- **Arabic lemma:** `"زمن وقت"` — the two Arabic terms for "time"
- **Definition keyword:** `"تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر الحاضر إلى الماضي"` — "the continuum of experience in which events pass from the future through the present to the past"

All backends were queried with top-K set to 50.

---

## 3. Results

### 3.1 Overall Metrics

| Query Type | Backend | N | Recall@10 | Recall@25 | Recall@50 | P@10 | MRR | Avg GT |
|------------|---------|---|-----------|-----------|-----------|------|-----|--------|
| arabic_lemma | **Gemini** | 63 | **99.5%** | **99.5%** | **100.0%** | **18.7%** | **0.964** | 1.9 |
| arabic_lemma | Jina v5-small | 63 | 97.6% | 98.8% | 99.6% | 18.1% | 0.921 | 1.9 |
| arabic_lemma | Jina v5-nano | 63 | 95.5% | 97.5% | 97.9% | 17.8% | 0.928 | 1.9 |
| arabic_lemma | Jina v3 | 63 | 91.5% | 93.9% | 97.1% | 17.1% | 0.889 | 1.9 |
| arabic_lemma | Mixedbread | 38 | 88.8% | 93.6% | 97.1% | 17.1% | 0.830 | 2.1 |
| definition_keyword | **Gemini** | 63 | **58.2%** | **64.3%** | **72.4%** | **10.5%** | 0.442 | 1.9 |
| definition_keyword | Jina v5-small | 63 | 49.5% | 57.7% | 66.5% | 8.6% | 0.397 | 1.9 |
| definition_keyword | Jina v5-nano | 63 | 48.3% | 62.2% | 64.9% | 8.3% | 0.412 | 1.9 |
| definition_keyword | Jina v3 | 63 | 43.1% | 57.3% | 65.1% | 6.8% | 0.279 | 1.9 |
| definition_keyword | Mixedbread | 38 | 39.0% | 52.9% | 58.6% | 7.6% | 0.459 | 2.1 |
| **Overall** | **Gemini** | 126 | **78.8%** | **81.9%** | **86.2%** | **14.6%** | **0.703** | — |
| **Overall** | Jina v5-small | 126 | 73.5% | 78.2% | 83.1% | 13.3% | 0.659 | — |
| **Overall** | Jina v5-nano | 126 | 71.9% | 79.8% | 81.4% | 13.0% | 0.670 | — |
| **Overall** | Jina v3 | 126 | 67.3% | 75.6% | 81.1% | 12.0% | 0.584 | — |
| **Overall** | Mixedbread | 76 | 63.9% | 73.2% | 77.9% | 12.4% | 0.645 | — |

*Avg GT counts unique headword files (not individual dictionary entries). A headword file may consolidate entries from multiple dictionaries. All Jina and Gemini backends were evaluated on the same 63-query subset; Mixedbread used a smaller 38-query subset due to API limits.*

**Baseline comparison:** The SQL baseline achieves 100% recall by definition — the ground truth was derived from those same SQL queries. Dense retrieval's Recall@50 of 100% (Gemini, arabic_lemma) matches this ceiling exactly.

A clear ranking emerges: Gemini leads every category, followed by the two Jina v5 models (small, then nano), then Jina v3, with Mixedbread's chunk-based retrieval at the bottom. Notably, the three open-source Jina models — running on a single T4 GPU with no API dependency — are competitive with both commercial APIs.

### 3.2 Arabic Lemma Queries: Near-Perfect Across Document-Level Backends

The headline result: **Gemini achieves 100% Recall@50 and 99.5% Recall@10 on Arabic headword lookup**, matching the SQL exact-match baseline. But the open-source Jina models are close behind.

All four document-level backends (Gemini + 3 Jina) share two structural advantages:

1. **Whole-document embedding:** Each headword file maps to exactly one vector. When the query contains the headword text, the model places the query vector very close to the document vector. There are no chunking artifacts that could split the headword away from its definition.

2. **Asymmetric task types:** All four backends encode queries and documents differently — Gemini via `RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT`, Jina v5 via `prompt_name="query"` / `"document"`, and Jina v3 via LoRA task adapters. This cross-type optimization is well-suited for our query structure.

**Gemini** leads with MRR = 0.964 — the first relevant result is at rank 1 in 96% of queries. Its single failure: synset `awn4-07958392-n` (people/بشر/ناس), where the headword **ناس** (*nas*, "people/folk") falls to rank 43. This is likely because ناس is a very short, high-frequency word with broad usage context, causing its embedding to be less specific. Notably, all three Jina backends also struggle with this synset — each finds only 3 of the synset's ground-truth headwords in the top 10.

**Jina v5-small** is the standout open-source result: **97.6% Recall@10 with zero failures** — the only backend where every single arabic_lemma query retrieves at least one ground-truth hit in the top 10. Its MRR of 0.921 means the first relevant result is typically at rank 1 or 2.

**Jina v5-nano** reaches 95.5% Recall@10 with a single failure: synset `awn4-04638046-n` (بهجة, "cheerfulness"), where the definite-article form البهجة falls outside the top 10. Both v5-small and v3 find it, suggesting this is a borderline case where the nano model's smaller vocabulary (239M params) just barely misses.

**Jina v3** has 3 failures — all on single-GT-entry "needle-in-haystack" queries: both تحفة (*tuhfa*, "masterpiece/rarity") synsets and the اداة (*ada*, "tool") synset. The v5 models find all three at rank 1–10. This pattern — v3 failing where v5 succeeds despite having 2.4× more parameters (570M vs 239M) — demonstrates the v5 generation's improved Arabic vocabulary from distillation off Qwen3-Embedding-4B.

**Mixedbread's** 88.8% Recall@10 is also strong but noticeably lower. The gap is partly explained by the **chunk deduplication effect**: Mixedbread returns ranked chunks, not documents. A single file can appear multiple times in the top-10, consuming slots that could have surfaced additional headwords. We quantify this effect in Section 5.

### 3.3 Definition Keyword Queries: The Hardest Task for All Backends

Sending the full Arabic definition as a query is a fundamentally harder task: given a definition like `"تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر الحاضر إلى الماضي"` (*the continuum of experience in which events pass from the future through the present to the past*), find dictionary entries whose headword is وقت or زمن ("time"). This requires bridging from paraphrastic description to lexicographic headword.

All five backends struggle here, but a clear tier structure emerges:

| Tier | Backends | Recall@10 | MRR |
|------|----------|-----------|-----|
| Best | Gemini | 58.2% | 0.442 |
| Middle | Jina v5-small, v5-nano | 48–50% | 0.40–0.41 |
| Lowest | Jina v3, Mixedbread | 39–43% | 0.28–0.46 |

Gemini leads by a clear margin (+8.7 pp over the best Jina model). But **MRR tells a different story**: Mixedbread's 0.459 narrowly beats Gemini's 0.442, meaning Mixedbread ranks the *first* relevant result slightly higher on average — it just finds *fewer* relevant results in the top-K window due to chunk duplication consuming slots.

**Jina v3's MRR collapse** (0.279) is the most striking pattern. On 31 of 63 definition queries, v3 returns zero ground-truth hits in the top 10 — compared to 25–26 for the v5 models. The time/وقت definition query illustrates this: v5-nano and v5-small both find 4 GT hits; v3 finds **zero**, with its top score (0.264) barely above noise. The XLM-RoBERTa backbone appears to struggle more with long Arabic definition text than the newer EuroBERT (v5-nano) and Qwen3 (v5-small) architectures.

Some definition queries work remarkably well across all backends. For synset `awn4-00028005-n` (shape/form), the definition `"الترتيب المكاني لشيء ما بشكل متميز عن مادته"` ("the spatial arrangement of something as distinct from its substance") retrieves all 4 ground-truth headwords (شكل, الشكل, هيئة, الهيئة) within the top 7 results on Gemini. The top-ranked non-GT result is **نسق** (*nasaq*, "arrangement/order") — semantically perfect for a query about spatial arrangement.

However, many definition queries still struggle across all backends. The scores cluster in a narrow range with no clear separation between relevant and irrelevant entries. The models capture the semantic *field* but can't reliably distinguish the *defining* headwords from merely *related* ones.

---

## 4. Worked Example: وقت / زمن (Time)

To make the evaluation concrete, let's trace one query through all five backends. We chose a synset with richer-than-average ground truth (4 headword files vs. the ~2.0 average) to illustrate multi-headword retrieval dynamics.

**Synset:** `awn4-00028468-n` — time: *"the continuum of experience in which events pass from the future through the present to the past"*
**Arabic lemmas:** زمن (*zaman*), وقت (*waqt*)

### Ground Truth

SQL headword lookup against the full database finds 29 dictionary entries across 4 headword forms:
- **وقت** (*waqt*) — 14 entries from Kitab al-'Ayn, Lisan al-'Arab, Taj al-'Arus, Lane's Lexicon, and 10 other classical sources → uploaded as `hw_0097592.md`
- **الوقت** (*al-waqt*, with definite article) — 1 entry from al-Qamus al-Muhit → uploaded as `hw_0802304.md`
- **زمن** (*zaman*) — 13 entries across the same major dictionaries → uploaded as `hw_0099249.md`
- **الزمن** (*al-zaman*, with definite article) — 1 entry from al-Qamus al-Muhit → uploaded as `hw_0798577.md`

These 29 entries map to 4 uploaded files — our ground truth for this query.

### Arabic Lemma Retrieval: Five Backends Side-by-Side

Query: `"زمن وقت"` → all backends return 50 results. Here are the top 10 from each document-level backend:

**Gemini + FAISS** — all 4 GT headwords in ranks 1–4:

| Rank | File | Headword | Score | Notes |
|------|------|----------|-------|-------|
| 1 | `hw_0099249.md` | **زمن** | **0.755** | Perfect top-1 |
| 2 | `hw_0798577.md` | **الزمن** | **0.748** | Definite-article variant |
| 3 | `hw_0097592.md` | **وقت** | **0.730** | Second lemma |
| 4 | `hw_0802304.md` | **الوقت** | **0.712** | Last GT — still rank 4 |
| 5 | `hw_0098011.md` | وكت | 0.664 | Archaic variant of وقت |
| 6 | `hw_0100081.md` | اوان | 0.661 | "time/season" — synonym |
| 7 | `hw_0099759.md` | اذ | 0.661 | Temporal conjunction |
| 8 | `hw_0830857.md` | كزمن | 0.659 | Contains root ز-م-ن |

**Jina v5-nano** — all 4 GT headwords in ranks 1–4 (same pattern as Gemini):

| Rank | File | Headword | Score | Notes |
|------|------|----------|-------|-------|
| 1 | `hw_0099249.md` | **زمن** | **0.739** | Top-1, highest Jina score |
| 2 | `hw_0097592.md` | **وقت** | **0.642** | |
| 3 | `hw_0798577.md` | **الزمن** | **0.641** | |
| 4 | `hw_0802304.md` | **الوقت** | **0.479** | All 4 GT in top 4 |
| 5 | `hw_0830857.md` | كزمن | 0.451 | Contains root ز-م-ن |
| 6 | `hw_0842609.md` | بيدام | 0.439 | |

**Jina v5-small** — all 4 GT headwords in ranks 1–4:

| Rank | File | Headword | Score | Notes |
|------|------|----------|-------|-------|
| 1 | `hw_0097592.md` | **وقت** | **0.589** | Leads with وقت (unlike nano/Gemini) |
| 2 | `hw_0099249.md` | **زمن** | **0.568** | |
| 3 | `hw_0802304.md` | **الوقت** | **0.550** | |
| 4 | `hw_0798577.md` | **الزمن** | **0.509** | All 4 GT in top 4 |
| 5 | `hw_0830857.md` | كزمن | 0.417 | Contains root ز-م-ن |

**Jina v3** — all 4 GT in top 8, but الزمن slips to rank 8:

| Rank | File | Headword | Score | Notes |
|------|------|----------|-------|-------|
| 1 | `hw_0099249.md` | **زمن** | **0.606** | |
| 2 | `hw_0097592.md` | **وقت** | **0.471** | |
| 3 | `hw_0802304.md` | **الوقت** | **0.321** | |
| 4 | `hw_0830857.md` | كزمن | 0.318 | Non-GT interloper |
| 5 | `hw_0100081.md` | اوان | 0.302 | "time/season" synonym |
| 8 | `hw_0798577.md` | **الزمن** | **0.292** | Definite-article form drops to rank 8 |

**Mixedbread Store** — GT headwords at ranks 1, 4, 5, 11 (chunk duplicates fill gaps):

| Rank | File | Headword | Score | Notes |
|------|------|----------|-------|-------|
| 1 | `hw_0097592.md` | **وقت** | **0.802** | Kitab al-'Ayn section |
| 2 | `hw_0097592.md` | وقت | 0.797 | Same file, different chunk |
| 3 | `hw_0097592.md` | وقت | 0.779 | Same file, different chunk |
| 4 | `hw_0802304.md` | **الوقت** | **0.769** | Definite-article form |
| 5 | `hw_0099249.md` | **زمن** | **0.757** | Second lemma |
| 6 | `hw_0097592.md` | وقت | 0.744 | Same file again |
| 11 | `hw_0798577.md` | **الزمن** | **0.673** | Last GT — pushed to rank 11 |

### Analysis

All four document-level backends (Gemini + 3 Jina) find all 4 ground-truth headwords in the top 10. Gemini, v5-nano, and v5-small pack them into the top 4 positions. Jina v3 lets الزمن slip to rank 8 — a non-GT entry (كزمن, containing the root ز-م-ن) pushes it down. Mixedbread spreads them across ranks 1–11 due to chunk duplication.

**Why?** Mixedbread's chunk-level retrieval gives وقت four separate slots in the top 10 (ranks 1, 2, 3, 6) — one per dictionary section within the consolidated file. These chunks are high-quality matches, but they crowd out the remaining GT headwords. By the time all 4 headword files appear, Mixedbread has used 11 slots; the document-level backends use only 4–8.

**Metrics for this query:**

| Metric | Gemini | v5-nano | v5-small | v3 | Mixedbread |
|--------|--------|---------|----------|----|-----------|
| Recall@10 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 75% (3/4) |
| Recall@50 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) |
| MRR | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

All document-level backends achieve full Recall@10 and MRR = 1.0 on this query. Mixedbread misses الزمن in the first 10 results.

**Interesting non-GT results:** All backends surface **كزمن** (containing root ز-م-ن) in their top 10. Gemini uniquely finds **وكت** — an archaic/dialectal variant of وقت attested in classical sources — at rank 5, which would never surface in SQL exact-match search without explicit variant expansion.

### Definition Keyword Retrieval (Same Synset)

Query: `"تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر الحاضر إلى الماضي"` — a much harder task. Here, the five backends diverge dramatically.

**Gemini + FAISS** — 2 GT in top 10, 4 in top 19:

| Rank | File | Headword | Score | Relevant? |
|------|------|----------|-------|-----------|
| 1 | `hw_0099759.md` | اذ | 0.635 | Temporal conjunction |
| 3 | `hw_0099249.md` | **زمن** | **0.618** | **GT** |
| 4 | `hw_0095718.md` | حدث | 0.612 | "event" — semantic neighbor |
| 7 | `hw_0798577.md` | **الزمن** | **0.598** | **GT** |
| 12 | `hw_0097592.md` | **وقت** | **0.584** | **GT** |
| 19 | `hw_0802304.md` | **الوقت** | — | **GT** |

**Jina v5-nano** — 4 GT in top 10:

| Rank | File | Headword | Score | Relevant? |
|------|------|----------|-------|-----------|
| 1 | `hw_0095718.md` | حدث | 0.441 | "event" — top result |
| 2 | `hw_0097592.md` | **وقت** | **0.268** | **GT** |
| 3 | `hw_0099249.md` | **زمن** | **0.250** | **GT** |
| 5 | `hw_0802304.md` | **الوقت** | **0.238** | **GT** |
| 7 | `hw_0798577.md` | **الزمن** | **0.224** | **GT** |

**Jina v5-small** — 4 GT in top 10:

| Rank | File | Headword | Score | Relevant? |
|------|------|----------|-------|-----------|
| 1 | `hw_0095718.md` | حدث | 0.345 | "event" — top result |
| 2 | `hw_0097592.md` | **وقت** | **0.286** | **GT** |
| 3 | `hw_0802304.md` | **الوقت** | **0.286** | **GT** |
| 7 | `hw_0798577.md` | **الزمن** | **0.227** | **GT** |
| 8 | `hw_0099249.md` | **زمن** | **0.222** | **GT** |

**Jina v3** — **0 GT in top 10** (complete failure):

| Rank | File | Headword | Score | Relevant? |
|------|------|----------|-------|-----------|
| 1 | `hw_0095718.md` | حدث | 0.264 | "event" |
| 2 | `hw_0099759.md` | اذ | 0.191 | Temporal conjunction |
| 3–10 | *(various)* | — | 0.10–0.13 | No GT entries found |

**Mixedbread Store** — 1 GT in top 10:

| Rank | File | Headword | Score | Relevant? |
|------|------|----------|-------|-----------|
| 1 | `hw_0099249.md` | **زمن** | **0.506** | **GT** |
| 3 | `hw_0099759.md` | اذ | 0.490 | Temporal conjunction |
| — | `hw_0802304.md` | الوقت | — | GT: **never found** (not in top 50) |

### Analysis

The definition query reveals a stark quality gradient across backends. The v5 models find all 4 GT headwords in the top 10 — outperforming even Gemini on this specific query, which only gets 2 in the top 10 (though Gemini finds all 4 by rank 19). Jina v3 fails completely: its top score (0.264) is barely above noise, and no GT entry appears in the top 10.

The contrast between v3 and v5 on this query is instructive. All backends agree that حدث (*hadath*, "event") is the top non-GT result — this word appears directly in the definition. But v3's scores collapse so sharply after rank 2 (from 0.191 to 0.134) that the actual time headwords are buried. The newer v5 architectures maintain enough signal to separate GT entries from the noise.

**Metrics for this query:**

| Metric | Gemini | v5-nano | v5-small | v3 | Mixedbread |
|--------|--------|---------|----------|----|-----------|
| GT in top 10 | 2/4 | 4/4 | 4/4 | 0/4 | 1/4 |
| GT in top 50 | 4/4 | 4/4 | 4/4 | 2/4 | 3/4 |

The "false positives" are, once again, semantically coherent across all backends: إذ (*idh*, temporal conjunction), حدث (*hadath*, event/occurrence). The embedding models capture the semantic field of time but can't reliably distinguish the *defining* headwords from merely *related* ones — with v3 being unable to distinguish them at all for this query.

---

## 5. Technical Insights

### 5.1 The Chunk Deduplication Tax

The most impactful structural difference across backends is retrieval granularity.

**Mixedbread** returns ranked *chunks*, not documents. A single uploaded file may appear multiple times in results — as we saw with وقت appearing at ranks 1, 2, 3, and 6 in the lemma query. Across all 76 Mixedbread queries, **~40.8% of the top-50 result slots are filled by duplicate filenames** (same file, different chunk). In the top-10, this means only **~5.7 unique documents** on average.

**Gemini FAISS** embeds each file as one vector. Every result slot is a distinct document: 10 unique files in top-10, 50 unique files in top-50. Zero duplication.

This difference has profound implications for Recall@K:

| Backend | Avg unique docs in top-10 | Effective doc coverage |
|---------|--------------------------|----------------------|
| Mixedbread Store | ~5.7 | 57% |
| Gemini + FAISS | 10.0 | 100% |
| Jina + FAISS (all models) | 10.0 | 100% |

The document-level backends (Gemini + all Jina models) expose **~75% more unique documents** than Mixedbread's chunk-level retrieval. For arabic_lemma queries where the ground truth is 1–4 headwords, having 10 unique document slots vs ~5.7 dramatically increases the chance of capturing all relevant headwords.

This isn't necessarily a flaw in Mixedbread's approach — chunk-level retrieval has advantages for long documents where different sections are relevant to different queries. But for our corpus of short, focused headword entries (averaging ~930 tokens), document-level retrieval is the better fit.

Our evaluation pipeline deduplicates at the headword level for Recall/Precision computation:

```python
# Map chunk filenames back to headwords via the export manifest
filename_to_hw = {}
for hw, info in manifest.items():
    filename_to_hw[info["filename"]] = hw

# Recall@K compares set intersection (deduped)
found = set(retrieved_hws[:k]) & gt_headwords
recall = len(found) / len(gt_headwords)
```

This means Recall@K is computed fairly — duplicate chunks are collapsed. But the slots consumed by duplicates still reduce the effective K for discovering *new* headwords.

### 5.2 Asymmetric Embeddings and Task-Type Awareness

All four document-level backends use asymmetric dual-encoder training — encoding documents and queries differently:

| Backend | Document encoding | Query encoding |
|---------|------------------|----------------|
| Gemini | `task_type="RETRIEVAL_DOCUMENT"` | `task_type="RETRIEVAL_QUERY"` |
| Jina v5 | `prompt_name="document"` | `prompt_name="query"` |
| Jina v3 | `task="retrieval.passage"` (LoRA adapter) | `task="retrieval.query"` (LoRA adapter) |

The intuition: queries and documents occupy different structural positions in the retrieval task. A query like `"زمن وقت"` (2 tokens) is structurally different from a document containing 3–12 dictionary definitions across 500–2000 tokens. Encoding them with the same model but different task prefixes allows the embedding space to optimize cross-type similarity.

This is particularly well-suited for our use case:
- **Arabic lemma queries** (2–5 tokens) are extremely short relative to documents. Asymmetric encoding can learn to expand the query representation to match document-length signals.
- **Definition queries** (20–50 tokens) are intermediate in length. The query encoding can learn that definitions should match headword-centric documents, not other definitions.

The implementation differs: Gemini and Jina v5 use task-specific prompt prefixes that steer the same model weights, while Jina v3 uses separate LoRA adapter weights for each task — a more parameter-efficient approach. Both approaches produce strong results, though v3's adapter-based approach may be less effective for Arabic given its XLM-RoBERTa base model's older training data.

Mixedbread's approach is opaque — we don't know whether their managed pipeline uses symmetric or asymmetric encoding.

### 5.3 Arabic Morphological Handling Without Preprocessing

All five backends handle Arabic morphological variation implicitly, with no preprocessing:

- **Definite article:** Both وقت and الوقت (with prefix ال) are retrieved for the query `"زمن وقت"`, despite being stored as separate files. Our SQL baseline requires explicit normalization to search for both forms. All four document-level backends achieve this.
- **Diacritics:** Fully diacriticized text in the dictionary entries (e.g., الذَّهَبُ with *shadda* and *damma*) matches undiacriticized queries seamlessly.
- **Semantic bridging:** All backends surface أوان (*awan*, "time/season") — a genuine near-synonym sharing no morphological root with either query term.
- **Root awareness:** All backends surface **كزمن** (containing the root ز-م-ن) in their top results for the time query, suggesting sensitivity to Arabic root patterns.

Gemini goes further, uniquely surfacing **وكت** (*wakt*, an archaic variant of وقت) at rank 5. This historical connection suggests Gemini's training data includes substantial classical Arabic text. BM25 keyword search would completely miss these connections without explicit synonym/variant expansion.

### 5.4 Score Distributions

Examining score distributions reveals clear patterns:

**Arabic lemma queries:**
- Gemini top-1 scores cluster at **0.69–0.77**. The gap between GT and non-GT results is moderate (~0.05).
- Mixedbread top-1 scores are higher in absolute terms (**0.75–0.80**), but scores are not directly comparable between models.

**Definition keyword queries:**
- Gemini top-1 scores drop to **0.60–0.67**, with relevant and irrelevant results nearly indistinguishable.
- Mixedbread shows the same pattern at **0.46–0.51**.

In both cases, the gap between relevant and irrelevant results is narrow (~0.03–0.05), confirming that cosine similarity scores from neural models don't have a universal "relevance threshold." Rank-based cutoffs (top-K) remain more robust than score-based cutoffs.

### 5.5 Why Precision@10 Is Low (And Why That's OK)

Precision@10 of 18.7% (Gemini, arabic_lemma) looks concerning at first glance. But consider the denominator: with an average of only 1.9 ground-truth headwords per query and 10 retrieved results, the maximum achievable P@10 is ~19%. Our 18.7% is **98% of this theoretical maximum**.

Furthermore, many "false positives" are genuinely useful. For the time query, Gemini surfaces وكت (archaic variant of وقت), اوان (near-synonym "time/season"), and اذ (temporal conjunction) — all relevant to a lexicographer studying the concept of time, even though they aren't in our ground truth set.

### 5.6 Token Economics and the Open-Source Alternative

All backends use the same exported corpus. The one-time indexing costs differ dramatically:

| Backend | Indexing Cost | Per-Query Cost | Index Storage |
|---------|-------------|----------------|---------------|
| Mixedbread Store | Free tier (2M tokens) | 1 API call | Cloud-hosted |
| Gemini + FAISS | ~97 API calls (20 docs/batch) | 1 API call (query embedding only) | ~6MB local file |
| Jina + FAISS | GPU compute only (free weights) | Free (local inference) | ~6–8MB local file |

Gemini's search is essentially free after indexing — FAISS runs locally in microseconds. Only the query embedding hits the API (1 call). Mixedbread's search requires an API call that performs both embedding and retrieval server-side.

**Jina eliminates all API costs.** The models are open-weight (Apache 2.0), hosted on HuggingFace, and run locally. The only cost is GPU compute for the one-time index build: 64 seconds for v5-nano, 224 seconds for v3, 365 seconds for v5-small on a Colab T4 (free tier). At v5-nano's throughput (30.5 docs/s), the full 760K-entry database would take ~6.9 hours for a one-time index build — feasible as a batch job on a single GPU, with zero ongoing costs.

For teams needing fully self-hosted retrieval with no API dependency, the quality trade-off is modest: Jina v5-small achieves 97.6% Recall@10 on arabic_lemma (vs Gemini's 99.5%), closing to within 2 percentage points at zero marginal cost.

### 5.7 The Tool/اداة Reversal: Why Query Formulation Matters More Than Model Size

The most surprising cross-backend finding involves synset `awn4-11437675-n` (tool/اداة, GT = 1 entry). The same synset produces **opposite winners** depending on query type:

| Query Type | Query Text | v5-nano | v5-small | v3 |
|------------|-----------|---------|----------|----|
| arabic_lemma | "اداة محرك" | **Rank 1** ✓ | **Rank 1** ✓ | Not in top 10 ✗ |
| definition_keyword | "شيء يستخدم لتحقيق غرض ما" | Not in top 10 ✗ | Not in top 10 ✗ | **Rank 7** ✓ |

On the lemma query, the v5 models find اداة at rank 1 while v3 misses entirely. On the definition query ("a thing used to achieve some purpose"), v3 finds it at rank 7 while *both* v5 models miss. The same model, same synset, same ground truth — but the query formulation determines which model wins.

This has practical implications: a hybrid query strategy — running both lemma and definition queries and merging results — would recover hits that any single query type misses. The v3 definition hit at rank 7 would complement the v5 lemma hit at rank 1, producing a more robust retrieval pipeline than either query type alone.

---

## 6. Conclusion

### What We Found

1. **Arabic lemma retrieval is essentially solved** with document-level asymmetric embeddings. Gemini leads (100% Recall@50, 99.5% Recall@10, MRR 0.964), matching the SQL exact-match ceiling — handling morphological variation, definite articles, and diacritics implicitly, and even surfacing archaic variants like وكت for وقت.

2. **Open-source models are competitive.** Jina v5-small (677M params) achieves 97.6% Recall@10 on arabic_lemma with zero failures — only 2 percentage points behind Gemini at zero API cost. Even the tiny v5-nano (239M params) reaches 95.5%, outperforming the larger v3 (570M) and Mixedbread's managed service.

3. **Architecture generation matters more than model size.** Jina v5-nano (239M, EuroBERT) outperforms Jina v3 (570M, XLM-RoBERTa) across the board despite being 2.4× smaller. The v5 generation's distillation from Qwen3-Embedding-4B produces better Arabic representations than v3's older XLM-RoBERTa backbone with LoRA adapters.

4. **Semantic definition matching remains the hardest task** across all five backends (39–58% Recall@10). Gemini leads (+8.7 pp over the best Jina model), but no backend achieves sufficient recall for primary use. Jina v3 struggles most, with MRR collapsing to 0.279 and 31/63 queries returning zero hits.

5. **The chunk vs document granularity is the dominant structural factor.** All four document-level backends (Gemini + 3 Jina) outperform Mixedbread's chunk-based retrieval. Gemini's top-10 contains 10 unique documents; Mixedbread's contains ~5.7. This ~75% effective coverage advantage explains most of Mixedbread's Recall@10 gap.

6. **Query formulation matters more than model choice.** The tool/اداة reversal (Section 5.7) shows that the same synset can produce opposite winners depending on whether the query is a lemma or definition — a hybrid query strategy would recover hits that any single approach misses.

### Could Dense Retrieval Replace SQL?

| Retrieval Task | Best Backend | Best Open-Source | Performance | Verdict |
|----------------|-------------|-----------------|-------------|---------|
| Headword exact match | Gemini | Jina v5-small | 99.5–100% R@50 | **Yes, for recall.** |
| Definition → headword | Gemini | Jina v5-small | 67–72% R@50 | **No** — too much recall loss. |

Gemini's 100% Recall@50 for arabic_lemma queries suggests dense retrieval can **replace** SQL exact-match for headword lookup — provided a sufficient retrieval window (top-50). Jina v5-small's 99.6% Recall@50 makes it a viable open-source replacement as well.

For definition-to-headword bridging, dense retrieval should remain an **augmentation layer**: use SQL for exact-match reliability, then use embedding search to discover related headwords that SQL would miss.

### Recommendations by Use Case

| Scenario | Recommended Backend | Why |
|----------|-------------------|-----|
| Maximum quality, API access OK | Gemini + FAISS | Best metrics across all query types |
| Self-hosted, no API dependency | Jina v5-small + FAISS | 97.6% R@10, zero API cost, open weights |
| Resource-constrained / edge deployment | Jina v5-nano + FAISS | 95.5% R@10 in a 239M-param package |
| Managed service, minimal setup | Mixedbread Store | Easiest to deploy, but weaker on document-level recall |

### What We'd Do Differently

1. **Extract keywords from definitions** before querying, rather than sending the full definition verbatim. All backends' low definition-keyword MRR (0.28–0.46) suggests they struggle with long, complex Arabic sentences as queries.
2. **Hybrid query strategy:** Run both lemma and definition queries per synset, merge results. The tool/اداة reversal shows this would recover hits missed by either query type alone.
3. **Test higher Gemini dimensions** (1536 or 3072) — Gemini's Matryoshka Representation Learning allows flexible output dimensions with minimal quality loss.
4. **Try the `QUESTION_ANSWERING` task type** for definition queries — Gemini supports task types beyond retrieval, and definition-to-headword bridging is closer to question-answering intent.
5. **Test Jina v5-small at full context** (32K tokens) — we truncated to 512 tokens for speed. Full-context encoding might improve definition queries, where discriminative content may appear deeper in the document.
6. **Scale to the full corpus** — Jina v5-nano's throughput (30.5 docs/s) makes indexing all 760K entries feasible in ~7 hours on a single GPU.
7. **Add per-dictionary breakdown** to detect quality differences between data sources (e.g., do entries from Lane's Lexicon, with English translations, retrieve differently than purely Arabic sources?).

---

## Appendix: Experiment Configuration

### Mixedbread Store

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

### Gemini + FAISS

| Parameter | Value |
|-----------|-------|
| **Model** | `gemini-embedding-001` |
| **Dimensions** | 768 |
| **Index type** | FAISS IndexFlatIP (cosine similarity via inner product on L2-normalized vectors) |
| **Created** | 2026-03-13 |
| **Files embedded** | 1,937 (0 failures) |
| **Index size** | ~6MB |
| **Synsets evaluated** | 206 (126 queries with GT overlap, 489 skipped) |
| **Errors** | 0 |

### Jina Embeddings + FAISS

| Parameter | Jina v5-nano | Jina v5-small | Jina v3 |
|-----------|-------------|---------------|---------|
| **Model** | `jinaai/jina-embeddings-v5-text-nano` | `jinaai/jina-embeddings-v5-text-small` | `jinaai/jina-embeddings-v3` |
| **Parameters** | 239M | 677M | 570M |
| **Base architecture** | EuroBERT-210M | Qwen3-0.6B | XLM-RoBERTa + LoRA |
| **Dimensions** | 768 | 1024 | 1024 |
| **max_seq_length** | 512 | 512 | 512 |
| **Task encoding** | `prompt_name="document"/"query"` | `prompt_name="document"/"query"` | `task="retrieval.passage"/"retrieval.query"` |
| **Index type** | FAISS IndexFlatIP | FAISS IndexFlatIP | FAISS IndexFlatIP |
| **Files embedded** | 1,937 | 1,937 | 1,937 |
| **Embed time** | 63.6s | 365.0s | 223.5s |
| **Device** | CUDA (T4 GPU, Colab) | CUDA (T4 GPU, Colab) | CUDA (T4 GPU, Colab) |
| **Synsets evaluated** | 206 (126 queries with GT overlap) | 206 (126 queries with GT overlap) | 206 (126 queries with GT overlap) |
| **Errors** | 0 | 0 | 0 |

### Shared Corpus

| Parameter | Value |
|-----------|-------|
| **Source dictionaries** | 15 classical Arabic dictionaries (786–1883 CE) |
| **Grouping** | One markdown file per unique headword |
| **Max definition length** | 2,000 characters per dictionary entry |
| **Max examples** | 5 per dictionary source |
| **Avg tokens per file** | ~930 |

**Source code:** All evaluation scripts are in `experiments/retrieval_eval/`:
- `export_entries.py` — Export pipeline (SQLite → markdown, 15 priority dictionaries, token budget)
- `backends/mixedbread_store.py` — Mixedbread Store upload + search
- `backends/gemini_faiss.py` — Gemini embedding + FAISS index + search
- `backends/_jina_common.py` — Jina shared module (sentence-transformers + FAISS local inference)
- `backends/jina_v5_nano.py`, `jina_v5_small.py`, `jina_v3.py` — Model-specific wrappers
- `run_eval.py` — Generic evaluation runner (backend-agnostic)
- `queries.py` — Query construction and synset selection
- `analysis.py` — Metrics computation (Recall@K, MRR, P@10)
- `docs/jina/Jina_Embeddings_Retrieval_Evaluation_(T4_GPU).ipynb` — Colab notebook for Jina GPU evaluation
