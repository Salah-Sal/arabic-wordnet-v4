# Fine-Tuning Jina Embeddings v5: A Complete Practical Guide

> **Version:** 2.0 (Verified & Corrected)
> **Date:** March 2026
> **Models covered:** `jina-embeddings-v5-text-small` · `jina-embeddings-v5-text-nano`
> **Paper:** [arXiv 2602.15547](https://arxiv.org/abs/2602.15547) — *jina-embeddings-v5-text: Task-Targeted Embedding Distillation*

---

## 1. Model Overview

Released February 18, 2026, the Jina Embeddings v5-text family delivers near-4B-parameter quality in sub-1B packages through **Task-Targeted Embedding Distillation** from a Qwen3-Embedding-4B teacher model. Both models ship with four task-specific LoRA adapters (retrieval, text-matching, classification, clustering) and support Matryoshka Representation Learning (MRL) for flexible dimension truncation.

### Architecture Specifications

| Specification | v5-text-small | v5-text-nano |
|---|---|---|
| **Base backbone** | Qwen3-0.6B-Base (decoder-only, 28 layers) | EuroBERT-210M (bidirectional encoder) |
| **Total parameters** | 677M | 239M |
| **Default embedding dim** | 1024 | 768 |
| **Max context length** | **32,768 tokens** | **8,192 tokens** |
| **Matryoshka dimensions** | 1024, 768, 512, 256, 128, 64, 32 | 768, 512, 256, 128, 64, 32 |
| **Pooling strategy** | Last-token | Last-token |
| **LoRA adapters** | 4 task-specific (~6.7M params each) | 4 task-specific (~6.7M params each) |
| **Languages** | 119+ tokenizer, 32 trained | 108 tokenizer, 32 trained |
| **MTEB English v2** | 71.7 | 71.0 |
| **MMTEB (multilingual)** | 67.0 | 65.5 |
| **License** | CC BY-NC 4.0 | CC BY-NC 4.0 |

> **⚠️ Context length warning:** Some official pages incorrectly state nano supports "32K tokens" in their overview paragraphs. This is a copy-paste error. Every structured data source — HuggingFace feature tables, blog comparisons, and the arXiv abstract — confirms **8,192 tokens for nano**. The 32K window applies only to v5-small, achieved through additional long-context training with adjusted RoPE base frequencies.

> **⚠️ Pooling note:** Despite nano using a bidirectional EuroBERT backbone, **both models use last-token pooling** — the embedding of the end-of-sequence token. This is confirmed in the arXiv paper and both HuggingFace model cards. Late chunking is therefore not supported in v5 models.

> **⚠️ License note:** CC BY-NC 4.0 is a **non-commercial** license. Commercial deployment requires a separate agreement with Jina AI (sales@jina.ai).

### Key Architectural Features

Both models employ Grouped Query Attention (GQA), RoPE positional encoding, RMSNorm, and SwiGLU/Swish-gated feed-forward layers. Binary quantization is nearly lossless thanks to Generalized Orthogonal Regularization (GOR) applied during training. The four LoRA adapters are trained independently on the frozen backbone:

- **Retrieval adapter:** InfoNCE + hard negatives
- **Text-matching adapter:** CoSENT ranking loss
- **Classification adapter:** Bidirectional InfoNCE + relational knowledge distillation
- **Clustering adapter:** Re-distillation

---

## 2. Choosing the Right Checkpoint

Jina v5 models use dynamic LoRA routing at inference (passing `task="retrieval"` selects the right adapter). However, managing dynamic adapter layers during a custom training loop is unnecessarily complex.

**Best practice:** Use Jina AI's **pre-merged checkpoints** where the task-specific adapter is already baked into the base model weights. These exist on HuggingFace with 13K+ downloads each.

### Pre-Merged Checkpoint Naming Convention

`jinaai/jina-embeddings-v5-text-{size}-{task}`

| Use Case | Small Checkpoint | Nano Checkpoint |
|---|---|---|
| **Asymmetric search (RAG/QA)** | `jinaai/jina-embeddings-v5-text-small-retrieval` | `jinaai/jina-embeddings-v5-text-nano-retrieval` |
| **Semantic similarity** | `jinaai/jina-embeddings-v5-text-small-text-matching` | `jinaai/jina-embeddings-v5-text-nano-text-matching` |
| **Classification** | `jinaai/jina-embeddings-v5-text-small-classification` | `jinaai/jina-embeddings-v5-text-nano-classification` |
| **Clustering** | `jinaai/jina-embeddings-v5-text-small-clustering` | `jinaai/jina-embeddings-v5-text-nano-clustering` |

Each contains full merged SafeTensors weights — no LoRA overhead at inference time.

---

## 3. Environment Setup

```bash
pip install -U "sentence-transformers[train]" datasets transformers peft accelerate

# Highly recommended for speed and VRAM efficiency:
pip install flash-attn --no-build-isolation
```

### Minimum Library Versions

- `transformers >= 4.57.0`
- `torch >= 2.8.0`
- `peft >= 0.15.2`
- `sentence-transformers >= 3.0`

---

## 4. The Prefix Rule — Critical for Accuracy

**⚠️ This is the single most important operational detail for fine-tuning Jina v5 models.**

Jina v5 models were trained with strict prompting formats. The arXiv paper states explicitly that the model distinguishes between query and document inputs by prepending a prefix. If you do not format your training data with these exact prefixes, performance will degrade significantly.

### Required Prefixes by Task

| Task | Input A prefix | Input B prefix |
|---|---|---|
| **Retrieval** | `"Query: "` | `"Document: "` |
| **Text-matching** | `"Document: "` | `"Document: "` |
| **Classification** | `"Document: "` | — |
| **Clustering** | `"Document: "` | — |

> **Note:** When using `sentence-transformers` or `transformers` with the `task` and `prompt_name` parameters, prefixes are applied automatically. Manual prepending is only needed when using raw tokenizers, vLLM, or llama.cpp.

### Applying Prefixes to Training Data

```python
from datasets import Dataset

# 1. Raw domain data
data = {
    "anchor": [
        "What is the context window of v5-nano?",
        "How do I fine-tune Jina v5?"
    ],
    "positive": [
        "The jina-embeddings-v5-text-nano model supports an 8,192 token context window.",
        "To fine-tune Jina v5, use the SentenceTransformerTrainer with pre-merged weights."
    ]
}

dataset = Dataset.from_dict(data)

# 2. Apply the mandatory Jina v5 prefixes
def apply_prefixes(example):
    return {
        "anchor": f"Query: {example['anchor']}",
        "positive": f"Document: {example['positive']}"
    }

train_dataset = dataset.map(apply_prefixes)
```

---

## 5. Data Preparation

Training data quality matters far more than quantity. As few as **1,000–5,000 high-quality pairs** can produce meaningful improvements for narrow domains, while complex multi-domain tasks benefit from 10,000+ samples.

### Data Formats by Task

**Retrieval (anchor-positive pairs)** — For `MultipleNegativesRankingLoss`, supply only positive pairs; the loss function generates negatives automatically from other pairs in the batch:

```python
train_data = Dataset.from_dict({
    "anchor": ["Query: What is retrieval augmented generation?",
               "Query: How does BERT work?"],
    "positive": ["Document: RAG combines retrieval with LLM generation...",
                 "Document: BERT is a bidirectional transformer..."],
})
```

**Semantic similarity (scored pairs)** — For `CoSENTLoss`:

```python
train_data = Dataset.from_dict({
    "sentence1": ["Document: The cat sat on the mat.",
                  "Document: Stock prices fell sharply."],
    "sentence2": ["Document: A cat is sitting on a mat.",
                  "Document: Markets experienced a downturn."],
    "score": [0.95, 0.82],
})
```

**Triplets (explicit hard negatives)** — For `TripletLoss` or enhanced MNRL:

```python
train_data = Dataset.from_dict({
    "anchor": ["Query: What is deep learning?"],
    "positive": ["Document: Deep learning uses neural networks with many layers..."],
    "negative": ["Document: Machine learning is a subset of AI that uses statistical methods..."],
})
```

### Generating Synthetic Training Data

The most practical recipe for domain-specific fine-tuning when labeled pairs don't exist:

1. Chunk your corpus into passages of 256–512 tokens
2. Use an LLM (GPT-4, Claude, Gemini) to generate 2–5 realistic questions per passage
3. Each `(generated_question, source_passage)` becomes a training pair
4. **Apply prefixes** — `"Query: "` for questions, `"Document: "` for passages
5. Split train/eval on **different source documents** to prevent data leakage

Published benchmarks show ~7% retrieval improvement with only 6,300 synthetic samples.

### Hard Negative Mining

Random negatives are too easy for powerful v5 models. Hard negatives — documents that are semantically similar but not relevant — force the model to learn fine-grained distinctions:

- **Embedding-based mining:** Use a strong model to find near-miss documents
- **BM25-based mining:** Lexically similar but irrelevant passages
- **Positive-aware threshold filtering:** Cap negative similarity at 95% of positive similarity (the NV-Retriever method)
- Mine **4–16 hard negatives per query** and filter for false negatives — studies show up to 70% of naively mined hard negatives may actually be relevant

---

## 6. The Fine-Tuning Script

### Full Fine-Tuning with Sentence Transformers

This is the recommended approach. We wrap `MultipleNegativesRankingLoss` in `MatryoshkaLoss` to preserve the model's native dimension truncation capability.

```python
import torch
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.losses import MultipleNegativesRankingLoss, MatryoshkaLoss
from sentence_transformers.training_args import BatchSamplers

# ──────────────────────────────────────────────
# 1. Load the pre-merged retrieval checkpoint
# ──────────────────────────────────────────────
# trust_remote_code=True is STRICTLY REQUIRED for all Jina v5 models.
# The official loading syntax uses `dtype` (not `torch_dtype`) in model_kwargs,
# and routes attention implementation through config_kwargs.

model_id = "jinaai/jina-embeddings-v5-text-small-retrieval"
# For nano: "jinaai/jina-embeddings-v5-text-nano-retrieval"

model = SentenceTransformer(
    model_id,
    trust_remote_code=True,
    model_kwargs={"dtype": torch.bfloat16},
    config_kwargs={"_attn_implementation": "flash_attention_2"},
)

# Limit sequence length during training to prevent OOM.
# While inference supports 32K (small) / 8K (nano), training batches at
# full length will crash most GPUs. 512 is a practical default.
model.max_seq_length = 512

# ──────────────────────────────────────────────
# 2. Define the loss function
# ──────────────────────────────────────────────
inner_loss = MultipleNegativesRankingLoss(model)

# Wrap in MatryoshkaLoss to preserve dimension truncation.
# For v5-small (max dim 1024):
matryoshka_dims = [1024, 768, 512, 256, 128, 64, 32]
# For v5-nano (max dim 768):
# matryoshka_dims = [768, 512, 256, 128, 64, 32]

loss = MatryoshkaLoss(
    model=model,
    loss=inner_loss,
    matryoshka_dims=matryoshka_dims,
    matryoshka_weights=[1.0] * len(matryoshka_dims),
)

# ──────────────────────────────────────────────
# 3. Configure training arguments
# ──────────────────────────────────────────────
args = SentenceTransformerTrainingArguments(
    output_dir="./jina-v5-finetuned",
    num_train_epochs=3,
    per_device_train_batch_size=32,       # As large as VRAM allows; critical for MNRL
    gradient_accumulation_steps=1,
    learning_rate=2e-5,                   # ~100x smaller than pre-training LR
    warmup_ratio=0.1,
    lr_scheduler_type="cosine",
    bf16=True,
    batch_sampler=BatchSamplers.NO_DUPLICATES,  # Prevents in-batch false negatives
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    load_best_model_at_end=True,
    logging_steps=10,
)

# ──────────────────────────────────────────────
# 4. Initialize trainer and train
# ──────────────────────────────────────────────
trainer = SentenceTransformerTrainer(
    model=model,
    args=args,
    train_dataset=train_dataset,      # Your prefixed dataset from Section 4
    loss=loss,
)

trainer.train()

# ──────────────────────────────────────────────
# 5. Save the fine-tuned model
# ──────────────────────────────────────────────
model.save_pretrained("./jina-v5-finetuned/final")
# model.push_to_hub("your-username/jina-v5-finetuned")
```

---

## 7. Parameter-Efficient Fine-Tuning (LoRA/PEFT)

If you're fine-tuning v5-nano (239M), a full fine-tune fits comfortably on consumer GPUs (12–16GB VRAM). For v5-small (677M) with large batch sizes, use LoRA to dramatically reduce VRAM requirements and protect against catastrophic forgetting.

### The Correct PEFT Integration Pattern

The officially recommended pattern in `sentence-transformers >= 3.3.0` uses `model.add_adapter()`:

```python
from peft import LoraConfig, TaskType

peft_config = LoraConfig(
    task_type=TaskType.FEATURE_EXTRACTION,
    inference_mode=False,
    r=16,
    lora_alpha=32,
    lora_dropout=0.1,
    # Target Qwen3 attention modules for v5-small:
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    bias="none",
)

# Official API — correctly handles attention masks and save/load
model.add_adapter(peft_config)

# Proceed with trainer.train() as normal...
```

> **⚠️ Avoid the legacy pattern:** Older tutorials show `model[0].auto_model = get_peft_model(model[0].auto_model, peft_config)`. This pre-v3.3.0 workaround can cause `RuntimeError` with attention mask mismatches and doesn't integrate properly with the save/load pipeline. Always use `model.add_adapter()`.

> **Note for nano:** Since nano uses a EuroBERT backbone (not Qwen3), the attention module names differ. Inspect with `print([n for n, _ in model.named_modules() if 'proj' in n])` and target the attention projection layers accordingly.

When using PEFT, `model.save_pretrained()` saves only the lightweight adapter weights (a few MB). At inference, load the base pre-merged model and merge your custom adapter on top.

---

## 8. Training Configuration Reference

### Recommended Hyperparameters

| Parameter | Recommended | Notes |
|---|---|---|
| **Learning rate** | `2e-5` (range: 1e-5 to 3e-5) | ~100× smaller than pre-training LR |
| **Batch size** | 32–64 (as large as GPU allows) | Larger = more in-batch negatives for MNRL |
| **Epochs** | 1–3 for large datasets (10K+), 3–10 for small (1K–5K) | Monitor eval loss for overfitting |
| **Warmup ratio** | 0.1 | 10% of total steps |
| **LR scheduler** | Cosine | Slightly better than linear decay |
| **Precision** | bf16 | Native support, significant speedup |
| **Batch sampler** | `NO_DUPLICATES` | Prevents false negatives from duplicate passages |
| **Optimizer** | AdamW (weight_decay=0.01) | Default in SentenceTransformerTrainer |
| **max_seq_length** | 512 (training) | Full context at inference; shorter during training to fit in VRAM |

### Loss Function Selection Guide

| Loss | Best for | Data format |
|---|---|---|
| **MultipleNegativesRankingLoss** | Retrieval, search | (anchor, positive) pairs |
| **CachedMultipleNegativesRankingLoss** | Retrieval with limited VRAM | Same; enables virtual batch sizes of 512–4096 |
| **CoSENTLoss** | Semantic similarity, STS | (sent_A, sent_B, score) |
| **TripletLoss** | Fine-grained with explicit negatives | (anchor, positive, negative) |
| **MatryoshkaLoss** | Preserving truncation robustness | Wraps any of the above |
| **GISTEmbedLoss** | Enhanced retrieval | (anchor, positive) + guide model |

The original v5 training used InfoNCE (equivalent to MNRL) for retrieval. MNRL is the single most important loss for retrieval fine-tuning — a batch of 64 gives 63 negative samples per query.

### Hardware Requirements

| Model | Full fine-tune VRAM | LoRA fine-tune VRAM | Time estimate (10K samples, 3 epochs) |
|---|---|---|---|
| v5-nano (239M) | 4–8 GB (batch=8) | 2–4 GB | ~10–20 min on A10G |
| v5-small (677M) | 10–20 GB (batch=8) | 4–8 GB | ~20–40 min on A10G |

The nano model fine-tunes on consumer GPUs (RTX 3090/4090). The small model works on 24GB cards with LoRA or small batch sizes; full fine-tuning with larger batches benefits from an A100 or H100.

---

## 9. Multi-Task Fine-Tuning

To fine-tune for both retrieval and similarity simultaneously:

```python
from sentence_transformers.losses import MultipleNegativesRankingLoss, CoSENTLoss

losses = {
    "retrieval_data": MultipleNegativesRankingLoss(model),
    "similarity_data": CoSENTLoss(model),
}

trainer = SentenceTransformerTrainer(
    model=model,
    train_dataset={
        "retrieval_data": retrieval_dataset,
        "similarity_data": similarity_dataset,
    },
    loss=losses,
    args=args,
)
```

---

## 10. Evaluation

Always establish a baseline on your evaluation set before training. The gap between pre-trained and fine-tuned on your specific data is what matters — not MTEB scores.

### Retrieval Evaluation

```python
from sentence_transformers.evaluation import InformationRetrievalEvaluator

evaluator = InformationRetrievalEvaluator(
    queries={"q1": "Query: What is deep learning?",
             "q2": "Query: Python web frameworks"},
    corpus={"d1": "Document: Deep learning is a subset of ML...",
            "d2": "Document: Flask and Django are popular..."},
    relevant_docs={"q1": {"d1"}, "q2": {"d2"}},
    name="my-domain-eval",
)

# Baseline (before training)
baseline = evaluator(model)

# ... fine-tune ...

# After training
finetuned = evaluator(model)
```

**Key metrics:** NDCG@10 (most informative for retrieval), MRR, MAP@100, Recall@k, Precision@k — all computed automatically.

### What to Expect

Published benchmarks show **5–15% improvement** in domain-specific retrieval metrics from fine-tuning on even modest amounts of quality data. Fine-tuned Matryoshka models at 128 dimensions can outperform the untuned model at full 768 dimensions by ~6.5%.

---

## 11. Critical Pitfalls

### ❌ Forgetting the prefix rule

The most common and damaging mistake. Without `"Query: "` and `"Document: "` prefixes, the model produces embeddings in the wrong space. The model was trained with these prefixes and expects them at both training and inference time.

### ❌ Skipping MatryoshkaLoss

Standard fine-tuning without `MatryoshkaLoss` will degrade performance at truncated dimensions. If you ever plan to use anything below the full 1024/768 dimensions, you **must** wrap your loss in `MatryoshkaLoss`.

### ❌ Binary quantization degradation

The original GOR regularization that makes binary quantization nearly lossless is **not preserved** by standard fine-tuning. If binary quantization is critical for your deployment, you need to add a custom GOR regularization term during training.

### ❌ Catastrophic forgetting

Training with too high a learning rate or too many epochs on narrow data degrades general capabilities. Mitigations: learning rates ≤ 2e-5, few epochs, and always validate on both domain-specific and general benchmarks. LoRA fine-tuning largely avoids this by keeping base weights frozen.

### ❌ Training at full context length

While inference supports 32K/8K tokens, passing full-length sequences in training batches will OOM most GPUs. Set `model.max_seq_length = 512` (or up to 2048 if VRAM allows) during training.

### ❌ Data leakage in evaluation

Split train and eval sets at the **document level** (not query level), so the model never sees eval passages during training. For synthetic data, generate train and eval queries from completely separate corpus chunks.

### ❌ Using the wrong PEFT pattern

Use `model.add_adapter(peft_config)`, not the legacy `model[0].auto_model = get_peft_model(...)` workaround. The latter causes attention mask issues and doesn't integrate with save/load.

---

## 12. Multilingual Fine-Tuning Considerations

The v5-small tokenizer covers 119+ languages, with 32 explicitly trained. For multilingual RAG:

- Include both **monolingual** and **cross-lingual** training pairs
- Cross-lingual retrieval (e.g., querying in English, retrieving in Arabic) typically underperforms monolingual and benefits most from fine-tuning
- The distillation from a multilingual 4B teacher provides strong multilingual foundations — particularly effective for languages where labeled data is scarce
- Evaluate using **MMTEB** (131 multilingual tasks) rather than English-only benchmarks
- Apply the same prefix rules (`"Query: "` / `"Document: "`) regardless of language

---

## 13. When to Fine-Tune vs. Use As-Is

### Fine-tune when:

- Your domain uses specialized terminology, abbreviations, or jargon not seen in general pre-training (legal, medical, internal docs, niche scientific)
- General-purpose retrieval quality plateaus despite pipeline optimizations
- Cross-lingual retrieval in under-resourced language pairs

### Try these first:

- **Hybrid search** (dense + BM25)
- Adding a **cross-encoder reranker** (e.g., Jina Reranker v2)
- Optimizing your **chunking strategy**
- Using a larger pre-trained model or different task adapter

Fine-tuning should be the last lever you pull, not the first.

---

## 14. Quick Reference Card

```
Model loading (official syntax):
  SentenceTransformer("jinaai/jina-embeddings-v5-text-small-retrieval",
      trust_remote_code=True,
      model_kwargs={"dtype": torch.bfloat16},
      config_kwargs={"_attn_implementation": "flash_attention_2"})

Prefixes:
  Retrieval queries  → "Query: {text}"
  Everything else    → "Document: {text}"

Loss stack:
  MatryoshkaLoss(MultipleNegativesRankingLoss(model))

Key hyperparameters:
  lr=2e-5, warmup_ratio=0.1, bf16=True, batch_sampler=NO_DUPLICATES

Matryoshka dims:
  small → [1024, 768, 512, 256, 128, 64, 32]
  nano  → [768, 512, 256, 128, 64, 32]

Context lengths:
  small → 32,768 tokens
  nano  → 8,192 tokens (NOT 32K despite some docs)

Pooling: Last-token (both models)

PEFT: model.add_adapter(LoraConfig(...))  # NOT get_peft_model
```

---

## Sources

| Source | URL |
|---|---|
| arXiv Paper | https://arxiv.org/abs/2602.15547 |
| HF Model Card (small) | https://huggingface.co/jinaai/jina-embeddings-v5-text-small |
| HF Model Card (nano) | https://huggingface.co/jinaai/jina-embeddings-v5-text-nano |
| Jina Blog Post | https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings/ |
| Jina Model Page (small) | https://jina.ai/models/jina-embeddings-v5-text-small/ |
| Jina Model Page (nano) | https://jina.ai/models/jina-embeddings-v5-text-nano/ |
| SBERT PEFT Training Guide | https://sbert.net/examples/sentence_transformer/training/peft/README.html |
| SBERT Matryoshka Guide | https://sbert.net/examples/sentence_transformer/training/matryoshka/README.html |
| SBERT Training Overview | https://sbert.net/docs/sentence_transformer/training_overview.html |