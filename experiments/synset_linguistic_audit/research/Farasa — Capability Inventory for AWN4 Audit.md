# Farasa — Capability Inventory for AWN4 Linguistic Audit

| | |
|---|---|
| **Developer** | QCRI (Qatar Computing Research Institute) |
| **Papers** | Abdelali et al. 2016 (segmenter), Darwish & Mubarak 2016 (POS), Darwish 2017 (diacritizer) |
| **License** | Research-only (Java toolkit); MIT (Python wrapper `farasapy`) |
| **Java repo** | `repos/FarasaSegmenter` (segmenter core only) |
| **Python repo** | `repos/farasapy` (wrapper for full toolkit) |
| **Architecture** | Java JARs invoked via Python `subprocess`; no JVM bridge |
| **Java requirement** | >= 1.7 (Java 7) |
| **Python requirement** | >= 3.10 |

---

## 1. Module Inventory

### 1.1 Available Tasks via `farasapy`

| Task | Class | Method | JAR | Auto-download | Interactive Mode |
|------|-------|--------|-----|:---:|:---:|
| Segmentation | `FarasaSegmenter` | `segment(text)` | `FarasaSegmenterJar.jar` | Yes | Yes |
| Desegmentation | `FarasaSegmenter` | `desegment(text)` | (Python-only post-processing) | — | — |
| Stemming | `FarasaStemmer` | `stem(text)` | `FarasaSegmenterJar.jar -l true` | Yes | Yes |
| POS Tagging | `FarasaPOSTagger` | `tag(text)` / `tag_segments(text)` | `FarasaPOSJar.jar` | Yes | Yes |
| Named Entity Recognition | `FarasaNamedEntityRecognizer` | `recognize(text)` | `FarasaNERJar.jar` | Yes | Yes |
| Diacritization | `FarasaDiacritizer` | `diacritize(text)` | `FarasaDiacritizeJar.jar` | Yes | Yes (slow) |
| Lemmatization | `FarasaLemmatizer` | `lemmatize(text)` | Manual download required | No | Yes |
| Spell Checking | `FarasaSpellChecker` | `spell_check(text)` | Manual download required | No | No |

### 1.2 Segmentation Details

The segmenter is a **log-linear scoring model** with 18 features (no neural network). For each candidate prefix/stem/suffix split, it computes a weighted sum of:

- Prefix/suffix n-gram probabilities
- Stem word count (frequency)
- Arabic morphological template (wazn) fit score — **a strong discriminator (weight 0.53)**
- Presence in morphological lexicon, gazetteer, Buckwalter lexicon
- Location/person name recognition
- Stop word indicator

Data footprint: ~30 MB of serialized Java `HashMap` objects in `FarasaData/`.

**Internal resources** (not directly exposed as API outputs):
- 10,406 Arabic roots in Buckwalter transliteration with log-probability weights (`roots.txt`)
- 125 Arabic morphological templates with probability scores (`template-count.txt`)
- Named entity gazetteers: locations (~259 KB), persons (~245 KB)
- Morphological analysis lexicon (3.5 MB) and Buckwalter-form lexicon (801 KB)
- Word frequency model (18 MB)

**Output formats:**
- Default: `و+كتاب+هم` (`+`-separated morpheme boundaries)
- ATB mode (`-c atb`): `و+ كتاب +هم` (spaced, al-attached to stem)

### 1.3 POS Tagging Details

Uses a CRF-based sequence model (separate from segmenter). Tagset is **ATB-derived** with subtag decomposition:

**Output format:** `token/TAG` pairs, where TAG can be compound: `VBP_IV3MS+ها/PVSUFF_DO:3MS`

The `tag_segments()` method returns structured `TaggedToken` objects with:
- `tokens: list[str]` — morpheme parts
- `tags: list[str]` — corresponding POS tags
- `as_tuple()` — structured output with tag decomposition

**POS tag categories:** NN (noun), VBP/VBD (verb forms), JJ (adjective), RB (adverb), IN (preposition), DT (determiner), plus ATB subtags encoding person, gender, number, voice.

### 1.4 NER Details

BIO tagging with entity types: `B-PER`, `B-LOC`, `B-ORG`, `B-MISC`, `I-*`, `O`.

### 1.5 Diacritization Details

Full harakat restoration. Computationally heavy — the README warns about high startup cost. Best used in standalone mode with batched input.

### 1.6 What Farasa Does NOT Provide

Unlike CAMeL Tools, Farasa does **not** expose:
- Full morphological analysis dictionaries (root, pattern, gloss per analysis)
- Morphological feature decomposition (case, state, voice, mood, aspect, rationality)
- Morphological generation (lemma + features → surface form)
- Reinflection (surface form + target features → new surface form)
- Dialect identification
- Sentiment analysis
- Character-level utilities (normalization, dediacritization, transliteration)
- Disambiguator with confidence scores

---

## 2. Mapping to AWN4 Audit Questions

### Level 1: Lemma Quality

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| **Q1.1** Citation form | Lemmatizer | **Cross-validator** | If Farasa's lemmatizer produces a different citation form than what AWN4 stores, it signals a potential non-citation entry. Requires manual JAR download. |
| **Q1.2** Diacritization | Diacritizer | **Cross-validator** | Run undiacritized lemma through Farasa diacritizer; compare output to AWN4's diacritics. Disagreement with both CALIMA and Farasa = high-confidence error. |
| **Q1.3** MSA check | (none directly) | — | Farasa has no dialect ID. |
| **Q1.7** Calque detection | Segmenter | **Preprocessor** | Segment MWE lemmas to identify clitic boundaries; helps distinguish genuine MWEs from glued-together translations. |
| **Q1.8** Verb binyan | Stemmer + POS tagger | **Partial** | Farasa's stemmer strips to root/stem, and the POS tagger produces ATB tags that encode verb form information (VBP/VBD subtags), but doesn't directly output binyan labels. |
| **Q1.9** Duplicates | Stemmer | **Preprocessor** | Stem all lemmas; compare stems to detect near-duplicates that differ only in inflection. |

### Level 2: Definition Quality

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| **Q2.1** Grammar check | POS tagger | **Partial** | Tag definition sentences; POS sequences can detect gross agreement violations (e.g., verb followed by another verb where noun expected). Not a full grammar checker. |
| **Q2.2** Circularity | Lemmatizer + Segmenter | **Preprocessor** | Lemmatize definition words to compare against lemma forms — catches morphological variants (e.g., definition uses كاتب while lemma is كتب). |
| **Q2.4** Calque detection | Segmenter + POS tagger | **Partial** | Segment and tag definition; un-Arabic POS sequences (e.g., "من أو ينتمي إلى" will have a distinctive tag pattern) could be calque indicators. |

### Level 3: Example Quality

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| **Q3.1** Lemma in example | Lemmatizer | **Key tool** | Lemmatize each word in the example; check if the target lemma appears — handles inflectional variation. |
| **Q3.2** Grammar check | POS tagger + Diacritizer | **Partial** | Same as Q2.1. Diacritization can additionally flag words that are unrecognizable (the diacritizer may produce garbage for non-MSA text). |
| **Q3.6** Syntactic patterns | POS tagger | **Useful** | Tag examples to extract syntactic frames (e.g., verb + preposition patterns for Q6.2 transitivity). |

### Level 4: POS Validation

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| **Q4.1** POS correctness | POS tagger | **Cross-validator** | Tag the lemma in a minimal context; compare Farasa's POS against AWN4's POS and CALIMA's POS. Three-way agreement = high confidence. |
| **Q4.3** Masdar categorization | POS tagger + Stemmer | **Partial** | Farasa's POS tags encode verb/noun distinction; combined with stem analysis, can help classify verbal nouns. |

### Level 5: Semantic Relations

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| All Q5.x | (none) | — | Farasa provides no semantic analysis. Level 5 requires LLM or ontology-based methods. |

### Level 6: Arabic-Specific Properties

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| **Q6.1** Root | Stemmer (+ internal root lexicon) | **Partial** | Farasa's stemmer reduces to stem, not root. The FarasaSegmenter Java code internally uses a 10,406-root lexicon, but this is NOT exposed via the Python API. Would require custom Java integration to extract roots. |
| **Q6.2** Transitivity/preposition frame | POS tagger | **Partial** | Tag examples to extract verb + preposition sequences. |
| **Q6.3** Morphological pattern | (internal only) | **Not exposed** | The segmenter internally fits 125 Arabic templates, but pattern data is not in the output. |
| **Q6.5** Register/era | (none) | — | No register classification capability. |

### Level 7: Cross-Synset Consistency

| Question | Farasa Capability | Role | Notes |
|----------|-------------------|------|-------|
| All Q7.x | (none directly) | — | Cross-synset comparisons require semantic analysis, not morphological tools. |

---

## 3. Farasa vs CAMeL Tools — Head-to-Head Comparison

### 3.1 Feature Matrix

| Capability | CAMeL Tools | Farasa | Winner for Audit |
|------------|:-----------:|:------:|:----------------:|
| **Morphological analysis** (full feature decomposition) | 40+ features per analysis, multiple readings | Not available | **CAMeL** |
| **Morphological database** (CALIMA Star) | Authoritative MSA database, 37K+ lemmas | Internal lexicons, not exposed | **CAMeL** |
| **Root extraction** | Directly in analysis output (`root` field) | 10,406 roots used internally, not exposed | **CAMeL** |
| **Pattern extraction** | Directly in analysis output (`pattern` field) | 125 templates used internally, not exposed | **CAMeL** |
| **Segmentation** | `MorphologicalTokenizer` (disambiguator-based) | Dedicated log-linear segmenter | **Farasa** (purpose-built, faster) |
| **POS tagging** | `DefaultTagger` wrapping disambiguator | CRF-based sequence model with ATB tags | **Tie** (different tagsets, both useful) |
| **Lemmatization** | `Analyzer.analyze()` → `lex` field | Dedicated `FarasaLemmatizer` | **Farasa** (context-aware sentence-level) |
| **Stemming** | Not directly available | `FarasaStemmer` | **Farasa** (unique capability) |
| **Diacritization** | MLE-based (`camel_diac` CLI) | Neural/statistical `FarasaDiacritizer` | **Cross-validate** (use both) |
| **NER** | BERT-based (B-LOC, B-ORG, B-PERS, B-MISC) | CRF-based (same entity types) | **CAMeL** (BERT > CRF for NER) |
| **Dialect ID** | DIDModel6/DIDModel26 | Not available | **CAMeL** (unique) |
| **Sentiment** | BERT-based | Not available | **CAMeL** (unique) |
| **Spell checking** | Not available | `FarasaSpellChecker` (manual download) | **Farasa** (unique) |
| **Morphological generation** | `Generator`: lemma + features → surface forms | Not available | **CAMeL** (unique) |
| **Reinflection** | `Reinflector`: surface + target features → new form | Not available | **CAMeL** (unique) |
| **Utilities** (normalization, dediac, transliteration) | Comprehensive (21 charmaps, etc.) | Basic (in Java, not exposed) | **CAMeL** |

### 3.2 Architectural Differences

| Dimension | CAMeL Tools | Farasa |
|-----------|-------------|--------|
| **Language** | Pure Python + data files | Java JARs via Python subprocess |
| **Installation** | `pip install camel-tools` + `camel_data` | `pip install farasapy` (auto-downloads JARs) |
| **Startup cost** | Moderate (load morphology DB into memory) | High (JVM startup per standalone call) |
| **Batch efficiency** | Good (in-process Python) | Good in interactive mode, poor in standalone |
| **Dependency** | Python ecosystem only | Requires Java runtime on PATH |
| **License** | MIT (code) + GPL v2 (CALIMA data) | Research-only (JARs) + MIT (wrapper) |

### 3.3 Key Insight: Complementary, Not Competing

CAMeL Tools and Farasa serve fundamentally different roles in the audit:

- **CAMeL Tools** is the **analytical engine** — it provides the deep morphological decomposition (root, pattern, 40+ features) that powers most audit checks. It's the database we query.
- **Farasa** is a **cross-validation oracle** — an independent system trained on different data. When Farasa agrees with CALIMA, confidence is high. When they disagree, the lemma needs manual review.

The strongest use of Farasa is **not to replace CAMeL Tools** but to provide **independent second opinions** on the ~42K flagged lemmas from Level 1.

---

## 4. Concrete Usage Plan for the AWN4 Audit

### 4.1 Highest-Value Applications

#### Application 1: Cross-validate CALIMA_NOT_RECOGNIZED (29,985 lemmas)

**Problem:** 29,985 lemmas are unrecognized by CALIMA. We estimated ~5-10% are genuine CALIMA coverage gaps (real Arabic words not in the DB), and ~90-95% are foreign transliterations.

**Farasa contribution:** Run all 29,985 through Farasa's stemmer and POS tagger:
- If Farasa also fails to stem/tag → **high confidence foreign transliteration**
- If Farasa successfully stems/tags → **likely CALIMA coverage gap** (real Arabic word)

```python
from farasa.stemmer import FarasaStemmer
from farasa.pos import FarasaPOSTagger

stemmer = FarasaStemmer(interactive=True)
tagger = FarasaPOSTagger(interactive=True)

for lemma in calima_unrecognized:
    stem = stemmer.stem(lemma)
    tag = tagger.tag(lemma)
    # If stem != original and tag != unknown → CALIMA gap
    # If stem == original (no reduction) → likely foreign
```

**Estimated impact:** Classifies 29,985 lemmas into two actionable buckets without manual review.

#### Application 2: Cross-validate DIACRITICS_MISMATCH (after script fix: ~1,555 lemmas)

**Problem:** ~1,555 lemmas have genuine diacritics disagreements between AWN4 and CALIMA (after removing the verb final-fatha false positives).

**Farasa contribution:** Run the undiacritized form through Farasa's diacritizer:
- If Farasa agrees with AWN4 → CALIMA's diacritization may be the outlier
- If Farasa agrees with CALIMA → AWN4 is likely wrong
- If all three disagree → needs manual linguist review

```python
from farasa.diacratizer import FarasaDiacritizer

diacritizer = FarasaDiacritizer(interactive=True)

for lemma in diacritics_mismatched:
    undiacritized = strip_diacritics(lemma.awn4_form)
    farasa_diac = diacritizer.diacritize(undiacritized)
    # Three-way comparison: AWN4 vs CALIMA vs Farasa
```

**Estimated impact:** Provides a tie-breaker for 1,555 diacritics disputes.

#### Application 3: NER for classifying unrecognized lemmas (29,985 lemmas)

**Problem:** Among the unrecognized lemmas, we need to distinguish proper nouns (كونراد, وودهول) from common nouns (أمبيسيلين, فولفاريلا).

**Farasa contribution:** Run through NER to identify `B-PER`, `B-LOC`, `B-ORG` entities:

```python
from farasa.ner import FarasaNamedEntityRecognizer

ner = FarasaNamedEntityRecognizer(interactive=True)

for lemma in calima_unrecognized:
    result = ner.recognize(lemma)
    # B-PER/B-LOC/B-ORG → proper noun, may need noun_prop POS
```

**Estimated impact:** Auto-classifies a significant fraction of the 29,985 unrecognized lemmas. Feeds directly into Q6.6 (cultural relevance) and Q4.1 (POS — should these be `noun_prop`?).

#### Application 4: Lemmatize definition/example sentences (Levels 2-3)

**Problem:** For circularity detection (Q2.2) and lemma-in-example verification (Q3.1), we need to lemmatize running Arabic text, not just isolated words. CALIMA's Analyzer returns all possible analyses for isolated words; Farasa's lemmatizer works on full sentences with context.

**Farasa contribution:** Sentence-level lemmatization for definitions and examples:

```python
from farasa.lemmatizer import FarasaLemmatizer

# Requires manual JAR download
lemmatizer = FarasaLemmatizer(binary_path="/path/to/FarasaLemmatizerJar.jar")

for synset in awn4_synsets:
    definition_lemmas = lemmatizer.lemmatize(synset.definition)
    for example in synset.examples:
        example_lemmas = lemmatizer.lemmatize(example)
        # Check: does the target lemma appear in example_lemmas?
```

**Note:** The lemmatizer JAR is not auto-downloadable. Must be obtained from the QCRI website.

#### Application 5: Spell-check definitions (Level 2)

**Problem:** AI-translated definitions may contain spelling errors or malformed Arabic words.

**Farasa contribution:** Run all 109,901 definitions through the spell checker:

```python
from farasa.spellchecker import FarasaSpellChecker

spellchecker = FarasaSpellChecker(binary_path="/path/to/FarasaSpellCheckerJar.jar")

for synset in awn4_synsets:
    corrected = spellchecker.spell_check(synset.definition)
    if corrected != synset.definition:
        # Flag differences as potential spelling errors
```

**Note:** Also requires manual JAR download. Standalone mode only (no interactive).

### 4.2 Lower-Priority Applications

| Application | Audit Question | Method | Priority |
|---|---|---|---|
| Segment MWE lemmas to detect calques | Q1.7 | Compare Farasa segmentation against CALIMA segmentation for 81,849 MWEs | MEDIUM |
| Extract verb+preposition frames from examples | Q6.2 | POS-tag examples, extract VB+IN bigrams | LOW (depends on Level 3) |
| Stem-based duplicate detection | Q1.9 | Stem all 124,768 lemmas, cluster by identical stems | MEDIUM |

### 4.3 Practical Considerations

#### License
Farasa's Java toolkit carries a **research-only license**. This is acceptable for our audit (academic research), but:
- Any tools we build using Farasa output can be used freely (the outputs are not copyrighted)
- If the audit pipeline is later productionized, Farasa components would need to be replaced or licensed

#### Performance
- **Interactive mode** is essential for batch processing (avoids JVM restart per call)
- **Diacritizer is slow** — for 124K+ lemmas, expect hours of processing
- The segmenter and POS tagger are fast (<1s per sentence in interactive mode)
- Standalone mode is unusable for large-scale audits (JVM startup per call)

#### Missing JARs
Two high-value tools (Lemmatizer, SpellChecker) require manual download from the QCRI website. The download URL may be at `https://farasa.qcri.org/` or `https://alt.qcri.org/tools/`.

#### Java Dependency
Farasa requires Java on the system PATH. All other audit tools (CAMeL, wn, Python scripts) are pure Python. This adds an infrastructure requirement.

---

## 5. Recommended Integration Order

| Phase | Tool | Audit Level | Scope | Blocking? |
|---|---|---|---|---|
| **Phase 1** | Stemmer + POS tagger | Level 1 | Cross-validate 29,985 unrecognized lemmas | No — enhances existing results |
| **Phase 2** | NER | Level 1 | Classify unrecognized lemmas as proper/common nouns | No |
| **Phase 3** | Diacritizer | Level 1 | Cross-validate ~1,555 diacritics mismatches | No — tie-breaker role |
| **Phase 4** | Lemmatizer (if JAR obtained) | Level 2-3 | Sentence-level lemmatization for definitions/examples | Yes — enables circularity and example-lemma checks |
| **Phase 5** | SpellChecker (if JAR obtained) | Level 2 | Definition spell-checking | No |

---

## 6. Summary: What Farasa Adds That CAMeL Tools Cannot

| Unique Farasa Capability | Why It Matters |
|---|---|
| **Independent cross-validation** | Different training data, different algorithms. Agreement = high confidence; disagreement = review needed |
| **Sentence-level lemmatization** | CAMeL's Analyzer works on isolated words. Farasa's lemmatizer works on sentences with context |
| **Stemming** | No equivalent in CAMeL Tools. Useful for duplicate detection and near-match clustering |
| **Spell checking** | No equivalent in CAMeL Tools. Directly addresses definition quality |
| **Named entity gazetteers** | Farasa's segmenter ships with location and person gazetteers (~500 KB total). These could help classify unrecognized lemmas |
