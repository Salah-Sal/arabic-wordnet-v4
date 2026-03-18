# External Review Validation Report

Validation of 23 review points against the actual codebase, notebook outputs, and data files.

**Blog post under review:** `experiments/retrieval_eval/blog_post.md`
**Date:** 2026-03-14

---

## Summary

| Category | Count |
|----------|-------|
| Confirmed errors (must fix) | 6 |
| Valid concerns (should address) | 11 |
| Correct as-is / minor style | 6 |
| Additional findings (not in review) | 3 |
| **Critical issue discovered** | **Train/test contamination (~70%)** |

---

## Part 1: Confirmed Errors

### #1 — Parameter Count: 239M vs 211M

**Reviewer:** "The abstract says 239M but Training Configuration says 211M. Which is correct?"

**Verdict: Blog is wrong. Actual count is 211,766,016 (~212M).**

The "239M" figure appears only in hand-written markdown (notebook cell 0, blog abstract). The actual runtime output from `sum(p.numel() for p in model.parameters())` in notebook cell 13 prints:

```
Parameters: 211,766,016
```

The 239M figure was never measured — it appears to have been taken from Jina's marketing materials for the base EuroBERT model (before LoRA merging or after including adapter parameters). The blog should use 212M throughout.

**Source:** `jina_finetune_colab.ipynb` cell 13 output.

---

### #3 — Eval Split: "32 Held-Out Synsets" Is Wrong

**Reviewer:** "If each synset generates both query types, 32 synsets should yield 64 queries, not 28."

**Verdict: The blog says "32 held-out synsets" but the actual number is 28.**

The split code in `build_finetuning_data.py` line 529:
```python
split_idx = int(len(processed_sids) * 0.8)  # int(137 * 0.8) = 109
```

This gives 109 train synsets and 137 − 109 = **28** eval synsets. The "32" was a typo in the notebook's markdown header (cell 0). The evaluator output confirms: `Evaluator 'jina-v5-nano-eval': 28 queries, 861 docs, 50 relevance judgments`.

The 28 queries = 28 unique anchors (one per eval synset). The evaluator deduplicates anchors by MD5 hash, collapsing all triplets from the same synset into a single query. Some synsets have multiple confirmed positives, giving 50 total relevance judgments across 28 queries.

**Source:** `build_finetuning_data.py` line 529; `jina_finetune_colab.ipynb` cell 12 output.

---

### #7 — Warmup Steps: 582 ≠ 10%

**Reviewer:** "582 warmup steps is ~80% of training, not 10%."

**Verdict: Reviewer is correct. This is a bug in the notebook.**

The notebook sets:
```python
per_device_train_batch_size=8
gradient_accumulation_steps=4
warmup_steps=582
```

The comment says `# Calculated from warmup_ratio=0.1 * Total steps (~5825)`, but:

- Gradient steps per epoch = 4,660 / 8 = 582.5 ≈ 582
- **Optimizer steps** per epoch = 4,660 / (8 × 4) = 145.6 ≈ 145
- Total optimizer steps (5 epochs) = **725**
- warmup_steps=582 / 725 total = **~80% of training**

The notebook's `print` output confirms `Steps/epoch: ~582`, but this counts raw gradient steps, not optimizer steps. HuggingFace Trainer's `warmup_steps` parameter operates on optimizer steps, so 582 warmup optimizer steps out of 725 total means the learning rate is warming up for nearly the entire training run.

The comment's "Total steps (~5825)" doesn't match the print output of "~2910" either. The 582 value appears to equal exactly one epoch of gradient steps, likely set by mistake instead of `warmup_steps=73` (which would be the actual 10%).

**Impact on results:** With 80% warmup, the effective learning rate ramp is much slower than intended. The model trains at near-zero LR for 4 of 5 epochs, only reaching full LR near the end. This may explain the sharp loss drop at epoch 2 and overfitting at epoch 3.

**Source:** `jina_finetune_colab.ipynb` cell 19.

---

### #10 — Best Model Selection: Not NDCG@10

**Reviewer:** "Is the selection metric actually NDCG@10, or is it validation loss?"

**Verdict: Blog is wrong. `metric_for_best_model` is not set; defaults to `eval_loss`.**

The `SentenceTransformerTrainingArguments` in cell 19 does not include `metric_for_best_model`. The HuggingFace Trainer default when this parameter is unspecified is `"eval_loss"`.

The blog states: "correctly selected the epoch 2 checkpoint based on evaluation NDCG@10." This should say "based on evaluation loss."

**Practical impact:** None. Epoch 2 has both the lowest validation loss (2.86 vs 3.39 and 4.83) AND the best NDCG@10/Recall@10. The same checkpoint would be selected either way.

**Source:** `jina_finetune_colab.ipynb` cell 19; HF Trainer documentation.

---

### #14 — Train/Test Contamination (~70%)

**Reviewer:** "No description of the 63 production test synsets. Were they randomly sampled? Do they overlap with the 137 training synsets?"

**Verdict: Confirmed — and far worse than the reviewer suspected.**

The `select_test_synsets()` function in `queries.py` (lines 41–54):
```python
def select_test_synsets(prepared_dir, num, offset=0):
    candidates = [...]  # all synsets with valid evidence.json
    random.seed(42)
    random.shuffle(candidates)
    return candidates[offset:offset + num]
```

The function draws from `prepared/` (206 valid candidates). **137 of those 206 (66.5%) are the same synsets used for finetuning training.** There is no exclusion logic.

Simulated overlap at `random.seed(42)`:

| Test set size | Overlap with 137 training synsets | Contamination rate |
|--------------|----------------------------------|-------------------|
| 30 (default) | 20 | 66.7% |
| 63 (used in blog) | **44** | **69.8%** |

**What this means:** The reported +5.7pp definition_keyword improvement is measured on a test set where ~70% of synsets had their query-document relevance signal used in training. The model was trained on triplets containing the exact ground-truth dictionary entries for those test queries.

The relationship is:
```
finetuning synsets (137) ⊂ trajectory synsets (169) ⊂ prepared pool (206)
```

The +5.7pp improvement is likely a mix of genuine generalization (~30% clean synsets) and memorization (~70% contaminated synsets). **The reported metrics should be treated as an upper bound, not a reliable estimate of generalization.**

**Source:** `queries.py` lines 41–54; `build_finetuning_data.py` lines 529–539; `finetuning_data/stats.json`.

---

### #21 — "Bootstraps Its Own Training Data" Overstates

**Reviewer:** "The system generates candidates that require external expert review to become training data. It's semi-supervised, not fully autonomous."

**Verdict: Reviewer is correct.**

In `build_finetuning_data.py`, the `ReviewParser` class reads `.review.yaml` files. Every lemma — whether from `original` or `step05` (AI-generated) — must have `decision: confirmed` or `decision: removed` in the review YAML before entering the training set. There is no path where step05 candidates become training data without passing through expert review.

The blog's phrase "the system bootstraps its own training data" should be revised to something like "generates candidates that, after passing expert review, become training data."

**Source:** `build_finetuning_data.py` `ReviewParser.parse()` method.

---

## Part 2: Valid Concerns

### #2 — 169 → 137 Synsets Unexplained

**Verdict: Valid.** 32 synsets were dropped for 5 reasons: (1) no trajectory record, (2) no `.review.yaml` file, (3) YAML parse failure, (4) no SQL results in trajectory, (5) no confirmed lemma matched any retrieved headword. The blog should add one sentence explaining this drop.

**Source:** `build_finetuning_data.py` lines 338–426 (five failure modes in `process_synset()`).

---

### #4 — english_bridge Excluded Without Mention

**Verdict: Valid.** All 203 `english_bridge` queries were skipped (0 ground-truth overlap with the uploaded corpus). The blog mentions three query types but never explains that english_bridge produced no results.

**Source:** `runs/jina_v5_nano/retrieval_results.json` — 203/203 english_bridge entries have `"skipped": true`.

---

### #5 — Train/Eval Split Not Exactly 80/20

**Verdict: Valid.** `int(137 × 0.8) = 109` train / 28 eval = 79.6% / 20.4%. The blog should say "approximately 80/20 (109 train / 28 eval synsets)."

---

### #6 — "Equivalent to Cosine" Needs Qualification

**Verdict: Implementation is correct — both sides normalize.** Both query encoding (`jina_v5_nano_finetuned.py` line 205) and document encoding (line 144) use `normalize_embeddings=True`. The blog should add "with both query and document vectors L2-normalized" for precision.

---

### #8 — "5.8x Faster" Unsubstantiated

**Verdict: Data exists and confirms the claim.** From `runs/*/config.json`:
- `jina_v5_nano`: 63.6s
- `jina_v5_nano_finetuned`: 63.0s
- `jina_v5_small`: 365.0s
- 365.0 / 63.0 = **5.79x ≈ 5.8x**

All measured on the same 1,937-file corpus. The blog should cite these numbers.

---

### #9 — MatryoshkaLoss Phrasing Imprecise

**Verdict: Valid.** "Preserves this property" should be "maintains training signal at truncated dimensions." Without MatryoshkaLoss, finetuning could degrade lower-dimensional performance even if the base model was Matryoshka-trained.

---

### #11 — Sequence Length Truncation Not Discussed

**Verdict: Valid and important.**

The corpus token distribution (estimated at 3 chars/token via `export_entries.py`):

| Stat | Tokens |
|------|--------|
| Mean | 944 |
| **Median** | **185** |
| Stdev | 1,604 |
| P90 | ~2,500 |
| Max | 8,047 |

The distribution is **severely right-skewed** — the top 20% of files contain 79.5% of all tokens. With `max_seq_length=512`, the longest ~20% of documents are truncated. For last-token pooling, the [EOS] token is always the last token in the *truncated* sequence, so the representation captures the first 512 tokens but loses all content beyond that.

The blog's "~930 tokens per file" claim uses the mean of a distribution where the median is 5x lower. This is technically correct but misleading.

---

### #12 — No Confidence Intervals

**Verdict: Valid.** With n=63 definition_keyword queries:
- SE(R@10) ≈ √(0.54 × 0.46 / 63) ≈ 0.063 (6.3pp)
- The +5.7pp improvement is within one standard error
- A 95% CI would be approximately [−6.6pp, +18.0pp]

The improvement is **not statistically significant** at conventional thresholds. The blog should acknowledge this.

---

### #13 — Gemini Context Advantage Not Discussed

**Verdict: Valid.** From the locally saved Gemini docs (`docs/gemini embeddings/Embeddings gemini.md`):
- Gemini embedding-001: **2,048 token input limit**
- Our Jina models: 512 token max_seq_length

Gemini can encode 4x more content per document. Given the right-skewed token distribution, this matters for the ~20% of large documents. The blog should note this when comparing to Gemini.

---

### #15 — Subtitle Ambiguity

**Verdict: Valid.** "+5.7pp Recall" in the subtitle is only for `definition_keyword`. Overall R@10 gain is +3.0pp. Should specify "definition-keyword Recall."

---

### #17 — Inconsistent Units

**Verdict: Valid.** The blog uses "+5.7pp", "+0.1500" (absolute), and "+15pp" in different places. Should standardize to "pp" throughout.

---

## Part 3: Correct As-Is / Minor Style

### #16 — "Beats Sibling" Holds Overall Too

The finetuned nano beats v5-small on **both** definition_keyword (54.0% vs 49.5%) **and** overall R@10 (74.9% vs 73.5%). The claim holds. Worth noting explicitly that the win is across the board.

### #18 — Duplicate كَيْنُونَة Example

Valid style point. Adding a forward reference ("as discussed above") in the triplet example would connect the two mentions.

### #19 — Section Ordering

Stylistic preference. Moving Technical Gotchas after Lessons Learned is reasonable but not necessary.

### #20 — Mixedbread Caveat

The asterisk footnote is somewhat buried. A parenthetical "(evaluated on a different 38-synset subset; not directly comparable)" would be more prominent.

### #22 — "Pre-merged" Needs Explanation

First use of "pre-merged retrieval checkpoint" should include "(LoRA adapters baked into base weights)" for readers unfamiliar with Jina's model distribution.

### #23 — SIGSEGV Heading Clarity

Adding "(Python fork-safety on macOS)" to the heading would help readers unfamiliar with Unix process model details.

---

## Part 4: Additional Findings

### A. "~930 Tokens Average" Is Misleading

The 944-token mean is technically correct but deeply misleading for a distribution with:
- Median: 185 tokens (5x below mean)
- Stdev: 1,604 (larger than the mean)
- Top 20% of files hold 79.5% of all tokens

This should report the median or note the severe skew.

### B. 1,937 vs 1,906 Files

The blog says "1,937 headword files" but the manifest tracks only 1,906 headwords. The 31 extra files are macOS-created duplicates with space-suffixed names (e.g., `hw_0099607 2.md`). They exist on disk but are not in the manifest and were not used in evaluation. The actual corpus is 1,906 unique headwords.

### C. Train/Test Contamination Is the Most Serious Finding

See #14 above. This is the critical issue: ~70% of production test synsets overlap with training synsets. The +5.7pp improvement is measured on a contaminated test set and should be treated as an upper bound.

**Recommended resolution:** Re-run evaluation with `select_test_synsets` modified to exclude the 137 training synsets. The remaining pool has 206 − 137 = 69 clean synsets. A clean evaluation on these 69 synsets (or however many have GT overlap) would give a reliable estimate of the model's generalization ability.

---

## Severity-Ranked Action Items

| Priority | Item | Section | Type |
|----------|------|---------|------|
| **P0** | Fix train/test contamination (re-evaluate or add caveat) | Results | Methodological |
| **P0** | Fix parameter count 239M → 212M | Throughout | Factual error |
| **P1** | Fix warmup steps claim (582 ≠ 10%) | Training | Factual error |
| **P1** | Fix metric_for_best_model (eval_loss, not NDCG@10) | Training | Factual error |
| **P1** | Fix "32 synsets" → 28 | Results | Factual error |
| **P1** | Add statistical significance caveat | Results | Missing information |
| **P2** | Explain 169 → 137 synset drop | Data Pipeline | Missing information |
| **P2** | Fix "bootstraps" → "generates candidates with expert review" | Data Pipeline | Overstatement |
| **P2** | Add english_bridge exclusion note | Problem | Missing information |
| **P2** | Add Gemini context length note | Baselines | Missing context |
| **P2** | Add seq_len truncation discussion | Training | Missing limitation |
| **P2** | Cite 5.8x timing data | Results | Unsubstantiated claim |
| **P3** | Fix ~930 tokens → note skew (median 185) | Problem | Misleading |
| **P3** | Standardize units to pp | Throughout | Inconsistency |
| **P3** | Clarify cosine similarity qualification | Baselines | Precision |
| **P3** | Fix subtitle to specify def_keyword | Title | Ambiguity |
| **P3** | Style fixes (forward refs, parentheticals) | Various | Polish |
