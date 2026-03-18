# Finetuning Jina v5 Embeddings for Arabic Dictionary Retrieval: 8 Mistakes, 3× Data, and a Clean Eval

> A 211M-parameter embedding model, finetuned twice on triplets curated from autonomous AI agent sessions and linguistic reviews, reaches 63% definition Recall@10 — beating its 3× larger sibling and closing the gap with Google's cloud API. The path from v1 to v2 reveals 8 training mistakes worth documenting.

## The Problem: Cross-Register Arabic Retrieval

Arabic WordNet v4 (AWN4) maps Arabic concepts to synsets — groups of synonymous lemmas sharing a definition. Building AWN4 requires matching each synset to relevant entries across a large collection of Arabic dictionaries. Our database holds **760,660 entries across 107 dictionaries**, spanning from 8th-century classical lexicons like *Kitāb al-ʿAyn* to modern 2024 technical glossaries like the *Data and AI Glossary*.

For the retrieval evaluation, we exported a curated subset: **1,937 headword files** consolidating **7,141 entries from 15 dictionaries** (averaging ~930 tokens per file). Each file aggregates all dictionary entries for a single headword into a structured markdown document with definitions, translations, and root information.

We evaluate retrieval with two primary query types:

- **`arabic_lemma`** — Direct Arabic term search (e.g., "كيان" for *entity*). Essentially lexical matching. Most models handle this well (95%+ Recall@10).
- **`definition_keyword`** — Full Arabic definition as query (e.g., "ما يُدرَك أو يُعرَف أو يُستدَلّ على وجوده المستقل" — *that which is perceived or known or inferred to have independent existence*). This requires genuine semantic understanding.

The bottleneck is `definition_keyword`. Definitions use modern standard Arabic, while dictionary entries span 1,200 years of the language — mixing Quranic vocabulary, classical roots, Sufi terminology, Ottoman-era neologisms, and contemporary technical jargon. No off-the-shelf embedding model handles this register gap well: all baselines plateau around 48–58% Recall@10.

## Baseline Evaluation: The Embedding Leaderboard

Before finetuning, we benchmarked 5 embedding backends on **126 queries** (63 `arabic_lemma` + 63 `definition_keyword`) drawn from 63 AWN4 synsets. All local models use FAISS `IndexFlatIP` on L2-normalized vectors (equivalent to cosine similarity), retrieving top-50 candidates.

| Backend | Parameters | arabic_lemma R@10 | def_keyword R@10 | Overall R@10 | MRR |
|---------|-----------|-------------------|-----------------|-------------|-----|
| Gemini embedding-001 | cloud API | 99.5% | 58.2% | 78.8% | 0.703 |
| Jina v5-small | 677M | 97.6% | 49.5% | 73.5% | 0.659 |
| **Jina v5-nano** | **211M** | **95.5%** | **48.3%** | **71.9%** | **0.670** |
| Jina v3 | 570M | 91.5% | 43.1% | 67.3% | 0.584 |
| Mixedbread Store | cloud | 88.8%* | 39.0%* | 63.9%* | 0.645* |

*\* Mixedbread evaluated on a different 38-synset subset (76 queries) due to free-tier rate limits.*

Two observations stand out:

1. **`definition_keyword` is the bottleneck everywhere.** Even Google's Gemini only reaches 58.2%. The gap between lemma matching (~95%) and definition matching (~48%) is roughly 47 percentage points.
2. **Size isn't everything.** Jina v5-nano (211M) and v5-small (677M) differ by 3× in parameters but only 1.2pp in definition_keyword R@10. The v3 model (570M) is even worse than nano. This suggests the representation space is undertrained for Arabic semantic matching, not capacity-limited.

This made v5-nano an attractive finetuning target: small enough for free-tier Colab, yet performing within striking distance of models 3x its size.

## The Data Pipeline: From Agent Trajectories to Training Triplets

The most novel aspect of this work is how we generated training data. Rather than manual annotation, we built a three-stage pipeline that extracts training signal from AI agent behavior and expert review.

### Stage 1: Claude Code Autonomous Sessions

We ran **280 Claude Code sessions**, each autonomously processing one AWN4 synset. Each session connected to our Arabic dictionary SQLite database and ran a series of queries — headword lookups, full-text keyword searches, English bridge queries, and enrichment searches — attempting to find all dictionary entries relevant to the synset.

Each session took about **11 minutes** and cost roughly **$1.08** ($182 total). The agent averaged 2.8 SQL queries per synset, producing raw retrieval results: which headwords it found, from which dictionaries, via which query strategy.

Of the 280 sessions, 169 produced usable trajectories (111 were rate-limited stubs). These were serialized as JSONL files and parsed by a trajectory extraction script that classified each SQL query by type and recovered any truncated results.

### Stage 2: Structured Linguistic Review

A linguistic reviewer produced a structured YAML review for each synset. Each review contains per-lemma decisions with detailed reasoning:

- **Evidence assessment** — Does the dictionary evidence *confirm*, *contradict*, *expand*, or remain *peripheral* to the lemma's candidacy?
- **Substitution tests** — Can this lemma replace others in example sentences without changing meaning?
- **Nuance differentiation** — How does this lemma differ from near-synonyms?
- **Decision** — `confirmed` (good match), `removed` (rejected with rationale), or `escalated`.

For example, for synset **awn4-00001740-n** (*entity*): **كِيَان** was confirmed with evidence from 7 dictionaries; **كَيْنُونَة** was rejected because dictionaries assign it to *existence* (German: *Sein*) rather than *entity* (*Seiendes*); candidates like **كائن**, **ذات**, and **مَوْجُود** were each rejected with specific substitution test failures.

### Stage 3: Triplet Assembly

The `build_finetuning_data.py` script cross-joins the trajectory results with the review decisions:

1. **Positive documents** = dictionary entries for `confirmed` lemmas.
2. **Hard negatives** (3.9% of negatives) = entries for `removed` lemmas — near-synonyms explicitly rejected with expert reasoning. These are the highest-value negatives.
3. **Soft negatives** (96.1%) = entries retrieved by the agent's FTS queries but never mentioned in the review — semantically adjacent but not relevant.

Each triplet follows the Jina v5 prefix convention:

```
Anchor:   "Query: كَيْنُونَة كِيَان — ما يُدرَك أو يُعرَف أو يُستدَلّ على وجوده المستقل"
Positive: "Document: # كيان (جذر: كن)\n\n## Data and AI Glossary\nEN: Entity\n..."
Negative: "Document: # كَيْنُونَة\n\n## Al-Mawrid Al-Hadeeth\nEN: existence\n..."
```

The train/eval split is done **at the synset level** (80/20, seed=42), ensuring no synset's documents appear in both splits.

| Statistic | Value |
|-----------|-------|
| Synsets processed | 137 |
| Total triplets | 6,172 |
| Train / Eval triplets | 4,660 / 1,512 |
| Avg triplets per synset | 45.1 |
| Positive source: original AWN4 lemmas | 73.5% |
| Positive source: AI-generated candidates (confirmed) | 26.5% |
| Negative source: soft (FTS-adjacent, unreviewed) | 96.1% |
| Negative source: hard (reviewer-rejected) | 3.9% |

Notably, **26.5% of positive training signal** comes from lemma candidates that the AI agent itself generated (step05) and that subsequently passed expert review — the system bootstraps its own training data.

## v1: First Attempt (Colab)

### Model

We use the **pre-merged retrieval checkpoint** `jinaai/jina-embeddings-v5-text-nano-retrieval` (211M parameters, 768-dimensional embeddings). This variant has the task-specific LoRA adapters already baked into the base EuroBERT weights — no dynamic LoRA routing needed at inference time. Critically, it uses **last-token pooling** (not mean pooling), matching how the model was pretrained.

### Training Configuration

| Parameter | Value |
|-----------|-------|
| Loss | MatryoshkaLoss(MultipleNegativesRankingLoss) |
| Matryoshka dims | [768, 512, 256, 128, 64, 32] |
| Epochs | 5 (best at epoch 2) |
| Batch size | 8 × 4 grad accum = 32 effective |
| Learning rate | 2e-5 (cosine) |
| Warmup | 582 steps |
| Precision | bf16 |
| GPU | Tesla T4 (Colab free tier) |
| Training triplets | 4,660 |

**Why MNRL over TripletLoss?** MNRL with triplet data gets the best of both worlds: each training row provides 1 explicit hard negative (the `negative` column), while all other positives in the batch serve as additional in-batch negatives. Standard TripletLoss only uses the 1 explicit negative. At least, that was the theory — as we'll see, we got the negative counting wrong.

### In-Notebook Results

The Colab notebook includes an `InformationRetrievalEvaluator` on the eval split (28 queries, 861 corpus documents):

| Metric | Baseline | Finetuned v1 | Delta |
|--------|----------|--------------|-------|
| NDCG@10 | 0.5021 | 0.6227 | +0.1207 |
| Recall@10 | 0.7155 | 0.8655 | **+0.1500** |
| MRR@10 | 0.5054 | 0.5900 | +0.0847 |
| MAP@100 | 0.4054 | 0.5188 | +0.1134 |

### Production Results

The real test is on the full corpus (1,937 documents, 126 queries from 63 synsets):

| Metric | Base v5-nano | Finetuned v1 | Delta |
|--------|-------------|--------------|-------|
| arabic_lemma R@10 | 95.5% | 95.9% | +0.4pp |
| definition_keyword R@10 | 48.3% | 54.0% | **+5.7pp** |
| Overall R@10 | 71.9% | 74.9% | +3.0pp |
| Overall MRR | 0.670 | 0.695 | +0.025 |

The finetuning preserved lemma performance while delivering a meaningful +5.7pp boost on definition retrieval. The finetuned 211M nano model now **outperforms the 677M v5-small** on definition_keyword (54.0% vs 49.5%).

Good result for a free-tier Colab run. But could we do better?

## Eight Things We Got Wrong

A careful post-mortem of the v1 training revealed 8 mistakes, ranging from showstoppers to cosmetic. The fixes became v2.

### P0-1: Gradient Accumulation ≠ Contrastive Batch Size (Critical)

**The bug:** v1 used `batch_size=8` with `gradient_accumulation_steps=4` for an "effective batch size of 32." We assumed this meant each query would see 31 in-batch negatives per MNRL step.

**The reality:** Gradient accumulation computes the loss on each micro-batch of 8 independently, accumulates gradients, then updates weights. MNRL's in-batch negatives are computed *within* each micro-batch. So each query only saw **15 negatives** (8 pairs × 2 - 1), not 31.

This is the single most impactful mistake in v1. Contrastive learning is fundamentally about the size of the negative pool — cutting it from 31 to 15 halves the effective difficulty of the task.

**The fix:** CachedMultipleNegativesRankingLoss (GradCache). This decouples the contrastive batch from the memory-constrained micro-batch. With `per_device_train_batch_size=32` and `mini_batch_size=16`, each query now sees **63 negatives** per GPU (2×32-1).

### P0-2: MNRL Negatives Math (Important)

**The bug:** We wrote "batch size 32 → 31 negatives per query." With triplet data, MNRL treats both the positive and negative columns as documents, giving a document pool of 2B. Each query sees 2B-1 negatives, not B-1.

**The fix:** Correctly: batch of 32 triplets → 2×32 = 64 documents → each query sees 63 negatives. (In v1, this was 2×8 - 1 = 15.)

### P0-3: Train/Test Distribution Shift (Important)

**The bug:** All training anchors used the combined format: `"Query: lemma1 lemma2 — definition text"`. But in production, queries are either lemma-only (`"كيان"`) or definition-only (`"ما يُدرَك أو يُعرَف..."`). The model never saw either query type in isolation during training.

**The fix:** Anchor decomposition. Each training anchor is split into 3 variants:
- **Combined:** `"Query: كِيَان — ما يُدرَك أو يُعرَف أو يُستدَلّ على وجوده المستقل"`
- **Lemma-only:** `"Query: كِيَان"`
- **Definition-only:** `"Query: ما يُدرَك أو يُعرَف أو يُستدَلّ على وجوده المستقل"`

This tripled the training set from 4,660 to **13,980 triplets** while matching the production query distribution.

### P1-4: Warmup Was 80%, Not 10%

**The bug:** `warmup_steps=582` with 728 total steps means 80% of training was warmup — the learning rate barely reached its peak before decay kicked in.

**The fix:** `warmup_ratio=0.1`.

### P1-5: bf16 on T4 = Software Emulation

**The bug:** `bf16=True` on a T4 GPU. T4s don't have native bf16 support; PyTorch falls back to software emulation, giving no speedup and potentially worse numerics.

**The fix:** `fp16=True` (native T4 tensor core support via Kaggle 2×T4).

### P1-6: Best Model Selection Was Random

**The bug:** `metric_for_best_model` was never set. HuggingFace Trainer defaults to `eval_loss`, which for contrastive loss doesn't correspond well to retrieval quality.

**The fix:** `metric_for_best_model="eval_ndcg@10"` with `greater_is_better=True`.

### P1-7: Parameter Count Included LoRA Adapters

**The bug:** We reported 239M parameters throughout the blog. That count includes the task-specific LoRA adapters. The pre-merged model is 211M.

**The fix:** Corrected to 211M throughout.

### P2-8: "32 Eval Synsets" Was Actually 28

**The bug:** We wrote "32 held-out eval synsets" but the 80/20 synset split with 137 total synsets gives 28 eval synsets, not 32.

**The fix:** Corrected.

## v2: Corrected Training (Kaggle)

### Updated Configuration

| Parameter | v1 (Colab) | v2 (Kaggle) |
|-----------|-----------|-------------|
| Loss | MatryoshkaLoss(MNRL) | MatryoshkaLoss(**CachedMNRL**) |
| Negatives per query | 15 | **63** |
| Training triplets | 4,660 | **13,980** (3× via decomposition) |
| Eval triplets | 1,512 | **4,536** (3×) |
| Batch size | 8 × 4 grad accum | **32** per device |
| Mini-batch size | — | **16** |
| Warmup | 582 steps (80%) | **10%** of steps |
| Precision | bf16 (emulated) | **fp16** (native) |
| Best model metric | eval_loss (default) | **NDCG@10** |
| GPU | 1× T4 (Colab) | **2× T4 (Kaggle)** |
| Best epoch | 2 | **1** (step 219) |

### In-Notebook Results

The v2 in-notebook evaluator uses the decomposed eval set (84 queries = 28 synsets × 3 variants, 861 corpus documents). Note the v2 baseline is lower than v1's because the decomposed eval includes harder definition-only and lemma-only queries:

| Metric | Baseline | Finetuned v2 | Delta |
|--------|----------|--------------|-------|
| NDCG@10 | 0.4604 | 0.6036 | +0.1432 |
| Recall@10 | 0.6500 | 0.7524 | +0.1024 |
| MRR@10 | 0.4604 | 0.6492 | **+0.1887** |
| MAP@100 | 0.3798 | 0.5183 | +0.1385 |

The MRR improvement (+0.189) is the standout — the model doesn't just find the right documents, it ranks them higher.

### Production Results

On the full production benchmark (1,937 documents, 126 queries, 63 synsets):

| Metric | Base v5-nano | v1 | **v2** | v2 Delta vs Base |
|--------|-------------|-----|-------|-----------------|
| arabic_lemma R@10 | 95.5% | 95.9% | 91.8% | −3.7pp |
| arabic_lemma MRR | 0.928 | 0.943 | 0.913 | −0.015 |
| **def_keyword R@10** | **48.3%** | **54.0%** | **63.0%** | **+14.7pp** |
| def_keyword MRR | 0.412 | 0.447 | 0.617 | +0.205 |
| **Overall R@10** | **71.9%** | **74.9%** | **77.4%** | **+5.5pp** |
| Overall MRR | 0.670 | 0.695 | 0.765 | +0.095 |

The results tell a clear story:

1. **Definition retrieval leaps forward.** `def_keyword` R@10 goes from 48.3% → 63.0%, a **+14.7pp** improvement over the base model. This is the task we cared most about, and v2 gains +9.0pp over v1's already-improved 54.0%.

2. **MRR improvement is massive.** Definition MRR jumps from 0.412 to 0.617 (+0.205). The relevant documents now typically appear in the top 2 results instead of outside the top 5.

3. **Lemma retrieval trades off slightly.** `arabic_lemma` R@10 drops from 95.5% to 91.8% (−3.7pp). The anchor decomposition meant the model saw more definition-style queries during training, which biased the embedding space toward semantic matching at the expense of pure lexical matching. This is an acceptable tradeoff for our use case — lemma queries are already solved at 91%+, while definition queries were the bottleneck.

### Updated Leaderboard

| Rank | Backend | Parameters | def_keyword R@10 | Overall R@10 | MRR |
|------|---------|-----------|-----------------|-------------|-----|
| 1 | Gemini embedding-001 | cloud API | 58.2% | 78.8% | 0.703 |
| **2** | **Jina v5-nano finetuned v2** | **211M** | **63.0%** | **77.4%** | **0.765** |
| 3 | Jina v5-nano finetuned v1 | 211M | 54.0% | 74.9% | 0.695 |
| 4 | Jina v5-small | 677M | 49.5% | 73.5% | 0.659 |
| 5 | Jina v5-nano (baseline) | 211M | 48.3% | 71.9% | 0.670 |
| 6 | Jina v3 | 570M | 43.1% | 67.3% | 0.584 |

The finetuned v2 nano model now **beats Gemini's cloud API** on definition retrieval (63.0% vs 58.2%) while being a local 211M model. It trails Gemini only on Overall R@10 (77.4% vs 78.8%) due to the lemma regression — Gemini achieves 99.5% on lemma queries.

## Independent Validation: The Gemini Eval Dataset

### Why We Needed It

The production evaluation (63 synsets) overlaps with the training data pipeline: the same linguistic reviews that generated training triplets also defined the ground truth for evaluation. While the synset-level split prevents direct leakage, there's a concern about distributional similarity — the eval synsets come from the same review process.

### How We Built It

We constructed a **fully independent evaluation dataset** using `build_finetuning_data.py --eval-only --evidence-only`:

1. Selected the 79 synsets whose reviews were done **exclusively by Gemini** (no overlap with the Claude-reviewed synsets used in training).
2. Used only **evidence-based** positives/negatives — dictionary entries explicitly cited in the reviewer's evidence, not FTS-adjacent soft negatives.
3. Generated 166 triplets and 130 anchor-positive pairs with zero training overlap.

| Statistic | Value |
|-----------|-------|
| Synsets | 79 |
| Triplets | 166 |
| Positive pairs | 130 |
| Training overlap | 0 |

### Triplet Accuracy Results

We evaluated v2 against the base model using cosine similarity on the clean eval triplets (is the positive closer to the anchor than the negative?):

| Metric | Base v5-nano | Finetuned v2 | Delta |
|--------|-------------|--------------|-------|
| Triplet accuracy | 46.4% | 67.5% | **+21.1pp** |
| Mean cosine margin | −0.011 | +0.057 | +0.068 |
| Per-synset: improved | — | 27/58 (47%) | — |
| Per-synset: unchanged | — | 24/58 (41%) | — |
| Per-synset: degraded | — | 7/58 (12%) | — |

Note that the base model's triplet accuracy is *below 50%* — it literally does worse than a coin flip at distinguishing confirmed from rejected near-synonyms. The finetuned model reaches 67.5%, improving on 47% of synsets while degrading on only 12%.

The per-synset breakdown is encouraging: improvement is broad (nearly half of all synsets) while degradation is concentrated in a small minority, suggesting the training generalizes rather than memorizing.

## The v5-small LoRA Experiment (Failed)

Emboldened by nano's success, we attempted LoRA finetuning of Jina v5-small (601M parameters) in the v2 Kaggle notebook. The configuration:

| Parameter | Value |
|-----------|-------|
| LoRA rank | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.1 |
| Target modules | q_proj, k_proj, v_proj, o_proj |
| Trainable params | 4.6M / 601M (0.76%) |

Training completed nominally, but `load_best_model_at_end` failed silently. The root cause: **PEFT + DataParallel checkpoint key mismatch.** When training on 2× T4 GPUs with DataParallel, PEFT saves adapter weights with the prefix `base_model.model.layers.*`. When reloading at training end, it expects `layers.*`. All LoRA adapter weights were reported as "MISSING" — the reloaded model was effectively the base model with fresh random LoRA initialization.

This is a known issue in the PEFT + multi-GPU ecosystem. The workaround would be to use DistributedDataParallel (DDP) instead, or to manually reload the best checkpoint from disk after training. We didn't pursue this further since nano v2 already exceeded our performance target for a local model.

## Technical Gotchas

Six non-obvious pitfalls encountered during development and deployment:

### 1. Pooling Mode Mismatch (Catastrophic)

Jina v5 uses **last-token pooling** (`pooling_mode_lasttoken: true`), not the more common mean pooling. However, `SentenceTransformerTrainer.push_to_hub()` only uploads raw transformer weights — it omits the full sentence-transformers pipeline files (`modules.json`, `1_Pooling/config.json`, `config_sentence_transformers.json`).

Without these files, sentence-transformers creates a model with **default mean pooling**. The resulting embeddings are garbage: definition_keyword R@10 dropped to **7.7%** (from 48.3% baseline).

**Fix:** Copy the pipeline configuration files from the base model repository (`jinaai/jina-embeddings-v5-text-nano-retrieval`) into the finetuned model directory.

### 2. macOS Fork-After-Thread SIGSEGV

`faiss-cpu` links OpenMP, which spawns threads on import. If `torch` or `sentence-transformers` is imported *after* faiss (and `trust_remote_code=True` triggers subprocess forking during model loading), the process receives SIGSEGV on macOS.

**Fix:** Import `torch` and `sentence_transformers` at module level, before faiss is ever imported (faiss can be imported lazily inside functions).

### 3. TokenizersBackend Incompatibility

The model was trained with sentence-transformers 5.2.3, which introduced a new `TokenizersBackend` tokenizer class. Loading the model with older ST versions fails with `ValueError: Tokenizer class TokenizersBackend does not exist`.

**Fix:** Patch `tokenizer_config.json` to use `"tokenizer_class": "PreTrainedTokenizer"` (the class used by the base model).

### 4. Missing Custom Architecture Code

The finetuned HuggingFace repo contains weights and tokenizer but not the custom EuroBERT architecture code (`configuration_eurobert.py`, `modeling_eurobert.py`). These files are required for `trust_remote_code=True` to work.

**Fix:** Download the custom code from the base Jina repository and copy it into the finetuned model directory. We implemented a `_prepare_model_dir()` function that merges files from both repos into a single directory.

### 5. CachedMNRL Requires Explicit mini_batch_size

When switching from MNRL to CachedMultipleNegativesRankingLoss, you must set `mini_batch_size` to control memory usage per gradient computation. Without it, GradCache defaults to processing the full batch in one pass, negating the memory savings.

### 6. PEFT + DataParallel Checkpoint Key Mismatch

As described in the v5-small section: when training with PEFT LoRA on multiple GPUs via DataParallel, checkpoint saves use a different key prefix than checkpoint loads expect. All adapter weights silently load as random initialization. Use DDP or manually reload checkpoints.

## Lessons Learned

### What Worked

- **Agent trajectories as training signal.** The 280 autonomous Claude Code sessions, at $182 total, produced high-quality positive/negative labels. The key insight is that the agent's *retrieval behavior* — which entries it found via which queries — naturally generates the relevance judgments needed for embedding training.

- **Linguistic reviews as hard negatives.** Reviewer-rejected near-synonyms (كَيْنُونَة rejected for *entity* because it means *existence*) are far more informative than random negatives. Even at only 3.9% of total negatives, they likely contribute disproportionately to the model's improved semantic discrimination.

- **Anchor decomposition as domain-specific augmentation.** Splitting `"Query: lemmas — definition"` into three variants (combined, lemma-only, definition-only) tripled the training data while solving the train/production distribution mismatch. This is more principled than generic augmentation techniques because it mirrors the actual query types the model will face.

- **Independent evaluation.** The Gemini eval dataset (zero training overlap) confirmed the model genuinely generalizes: +21.1pp triplet accuracy improvement is not explained by memorization.

- **Gradient accumulation ≠ contrastive batch size.** This is the single most important lesson. If you're using MNRL or any in-batch negative contrastive loss, gradient accumulation does *not* increase your effective negative pool. Use CachedMNRL (GradCache) instead.

### The v1→v2 Improvement Breakdown

What contributed most to v2's +9.0pp definition R@10 gain over v1?

1. **CachedMNRL (P0-1/P0-2):** 4× more negatives per query (15→63). This is likely the largest single contributor — contrastive learning quality scales directly with negative pool size.
2. **Anchor decomposition (P0-3):** 3× more training data, better query distribution match. Hard to separate from the CachedMNRL effect since both changed simultaneously.
3. **Warmup fix (P1-4):** Going from 80% warmup to 10% means the model actually trains at full learning rate for most of the run.
4. **fp16 fix (P1-5):** Proper hardware utilization. Unlikely to affect quality directly, but training was faster and more stable.

We didn't ablate these individually — a limitation worth noting. A controlled experiment varying only the loss function (MNRL vs CachedMNRL) with identical data would isolate the most important factor.

### The Lemma-Definition Tradeoff

v2 gained +14.7pp on definition retrieval but lost −3.7pp on lemma retrieval compared to the base model. This tradeoff makes sense: anchor decomposition tripled the number of definition-style queries in training, biasing the model toward semantic over lexical matching.

For our use case (AWN4 construction), this is the right tradeoff — lemma queries at 91.8% are already effective enough, while definition queries were the critical bottleneck. But if your application requires lexical retrieval above all else, v1 (which preserved lemma performance at 95.9%) may be preferable.

### What Fell Short

We originally targeted 80%+ definition_keyword R@10. v2 achieved 63.0% — a massive improvement over the 48.3% baseline, but still below target. The remaining gap likely requires:

- **More training synsets.** Only 137 of 280+ available synsets were used. Recovering rate-limited trajectories would roughly double the training set.
- **Hard negative mining.** Mining additional hard negatives from v2's own retrieval failures would target the specific cases where the model still struggles.
- **Longer documents need chunking.** At ~930 tokens average, dictionary entry files exceed the 512-token training window. Sentence-level chunking before embedding would allow finer-grained matching.

## Reproducibility

| Resource | Location |
|----------|----------|
| v1 model | [`SalahAbdoNLP/jina-v5-nano-arabic-dict`](https://huggingface.co/SalahAbdoNLP/jina-v5-nano-arabic-dict) |
| v2 model | [`SalahAbdoNLP/jina-v5-nano-arabic-dict-v2`](https://huggingface.co/SalahAbdoNLP/jina-v5-nano-arabic-dict-v2) |
| v1 notebook | `experiments/retrieval_eval/jina_finetune_colab.ipynb` (Colab T4) |
| v2 notebook | `experiments/retrieval_eval/jina_finetune_kaggle.ipynb` (Kaggle 2×T4) |
| Training data | `experiments/retrieval_eval/finetuning_data/` (6,172 triplets JSONL) |
| Clean eval data | `experiments/retrieval_eval/finetuning_data/eval_gemini/` (166 triplets) |
| Eval code | `experiments/retrieval_eval/run_eval.py` + `analysis.py` |
| v1 backend | `experiments/retrieval_eval/backends/jina_v5_nano_finetuned.py` |
| v2 backend | `experiments/retrieval_eval/backends/jina_v5_nano_finetuned_v2.py` |
