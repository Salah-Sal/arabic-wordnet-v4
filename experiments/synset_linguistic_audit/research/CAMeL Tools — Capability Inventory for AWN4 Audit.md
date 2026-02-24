# CAMeL Tools — Capability Inventory for AWN4 Linguistic Audit

| | |
|---|---|
| **Version** | 1.5.x (CAMeL Lab, NYU Abu Dhabi) |
| **Source** | Obeid et al., LREC 2020 |
| **License** | MIT (toolkit); GPL v2 (CALIMA Star morphology DBs) |
| **Local clone** | `/Users/salahmac/Desktop/MLProjects/wn-project/camel_tools` |

---

## 1. Module Inventory

### 1.1 Morphological Analysis Engine (`camel_tools.morphology/`)

The core of CAMeL Tools. Uses CALIMA Star — the most authoritative MSA morphological database — with prefix-stem-suffix decomposition and compatibility tables.

| Class | Purpose |
|-------|---------|
| `MorphologyDB` | Loads morphological databases (`calima-msa-r13`, `calima-egy-r13`) |
| `Analyzer` | Takes an Arabic word → returns ALL possible morphological analyses (~40 features each) |
| `Generator` | Takes a lemma + features → generates all valid surface forms |
| `Reinflector` | Combines Analyzer + Generator: takes surface word + target features → reinflected form |

**Key pattern**: `Analyzer.analyze('كتب')` returns a list of dicts, each with:
- `lex` (lemma), `root`, `pattern` (wazn), `diac` (fully diacritized), `gloss` (English)
- `pos` (30+ values), `catib6`, `ud` (Universal Dependencies)
- `gen`, `num`, `cas`, `stt`, `vox`, `asp`, `mod`, `per`, `rat`
- `prc0-3` (proclitics), `enc0-2` (enclitics)
- `bw` (Buckwalter tag), `caphi` (phonological)

### 1.2 Morphological Disambiguation (`camel_tools.disambig/`)

| Class | Method | Description |
|-------|--------|-------------|
| `MLEDisambiguator` | Maximum Likelihood | Word-based MLE lookup + pos-lex log probability ranking |
| `BERTUnfactoredDisambiguator` | Neural | Fine-tuned BERT for morphosyntactic tagging (MSA, Egyptian, Gulf models) |

**Why disambiguation matters — Analyzer vs Disambiguator**:

Arabic is massively ambiguous at the word level. The `Analyzer` returns **all possible** morphological interpretations for a word in isolation. For example, the undiacritized word **كتب** yields:

| # | `lex` (lemma) | `diac` | `pos` | `gloss` |
|---|---|---|---|---|
| 1 | كَتَبَ | كَتَبَ | verb | he wrote |
| 2 | كَتَبَ | كُتِبَ | verb | it was written (passive) |
| 3 | كِتَاب | كُتُب | noun | books (plural of كتاب) |
| 4 | كَاتَبَ | كَاتَبَ | verb | he corresponded with |

One surface form, 4+ completely different words. The Analyzer has no way to choose — it returns the full menu.

The **Disambiguator** uses context to pick the single best analysis:
- **MLE**: "what POS/lemma is statistically most frequent for this word?"
- **BERT**: "given the surrounding words in the sentence, which analysis fits best?"

For isolated lemmas (Level 1 audit checks), the Analyzer alone suffices. For **sentences** — AWN4 definitions and examples — we need the Disambiguator. Specific audit uses:

- **Q3.3 "Does the target lemma appear in the example?"** — We can't string-match كتب; we need to know if it's the verb كَتَبَ or the noun كُتُب. Disambiguation resolves the `lex` (lemma) in context.
- **Q2.3 "Are definition words valid MSA?"** — Disambiguate each word in the definition to check if the selected analysis has `source: lex` (known to CALIMA) vs a backoff/unknown.
- **Q3.2 "Is the example parseable?"** — Low-confidence disambiguation scores signal potentially unnatural or malformed text.

### 1.3 Tokenization (`camel_tools.tokenizers/`)

| Class | Description |
|-------|-------------|
| `simple_word_tokenize()` | Language-agnostic word boundary splitter (whitespace + Unicode punctuation) |
| `MorphologicalTokenizer` | Disambiguator-based morpheme-level tokenization. Schemes: `atbtok`, `atbseg`, `bwtok`, `d1-3tok/seg` |

### 1.4 Feature Tagging (`camel_tools.tagger/`)

`DefaultTagger` wraps any disambiguator to produce tags for ANY single morphological feature. Supported features: `diac`, `bw`, `lex`, `gloss`, `pos`, `asp`, `cas`, `mod`, `num`, `gen`, `form_num`, `form_gen`, `stt`, `vox`, `per`, `enc0-2`, `prc0-3`, `atbtok/seg`, `bwtok`, `d1-3tok/seg`, `catib6`, `ud`, `caphi`.

### 1.5 Dialect Identification (`camel_tools.dialectid/`)

| Model | Labels |
|-------|--------|
| `DIDModel26` | 25 Arabic city dialects + MSA |
| `DIDModel6` | 6 regions (Gulf, Levant, Maghreb, Nile Basin, Gulf of Aden, MSA) |

Uses TF-IDF + KenLM language models + Multinomial Naive Bayes.

### 1.6 Named Entity Recognition (`camel_tools.ner/`)

BERT-based NER with BIO tagging: `B-LOC`, `B-ORG`, `B-PERS`, `B-MISC`, `I-*`, `O`. Pretrained model: `arabert`.

### 1.7 Sentiment Analysis (`camel_tools.sentiment/`)

BERT-based: `positive`, `negative`, `neutral`. Pretrained: `arabert`, `mbert`.

### 1.8 Utilities (`camel_tools.utils/`)

| Module | Capability |
|--------|-----------|
| `charmap.py` | `CharMapper` — 21 built-in maps: Arabic ↔ BW, SafeBW, XMLBW, HSB, `arclean` |
| `charsets.py` | Pre-computed Unicode sets: Arabic letters, diacritics, BW/SafeBW/XMLBW/HSB, emoji |
| `dediac.py` | Dediacritization: `dediac_ar()`, `dediac_bw()`, etc. |
| `normalize.py` | Alef normalization, Teh Marbuta → Heh, Alef Maksura → Yeh, NFC/NFKC |
| `transliterate.py` | `Transliterator` — marker-based skip support |
| `stringutils.py` | Unicode string type checking |

### 1.9 CLI Tools

| Command | Purpose |
|---------|---------|
| `camel_morphology` | Analyze / generate / reinflect from terminal |
| `camel_diac` | Automatic diacritization (MLE) |
| `camel_dediac` | Strip diacritics |
| `camel_transliterate` | Convert between encoding schemes |
| `camel_arclean` | Normalize non-standard Arabic characters |
| `camel_word_tokenize` | Word-boundary tokenization |
| `camel_data` | Download/install data packages |

---

## 2. Complete Morphological Feature Model

Every analysis from `Analyzer`/`Disambiguator` is a dict with these features:

### Closed-set morphological features

| Feature | Code | Values |
|---------|------|--------|
| POS | `pos` | noun, noun_prop, noun_num, noun_quant, adj, adj_comp, adj_num, adv, adv_interrog, adv_rel, pron, pron_dem, pron_exclam, pron_interrog, pron_rel, verb, verb_pseudo, part, part_dem, part_det, part_focus, part_fut, part_interrog, part_neg, part_restrict, part_verb, part_voc, prep, abbrev, punc, conj, conj_sub, interj, digit, latin |
| Aspect | `asp` | c (command), i (imperfective), p (perfective), na |
| Case | `cas` | n (nominative), a (accusative), g (genitive), na, u |
| Form gender | `form_gen` | f, m, na |
| Gender | `gen` | f, m, na |
| Form number | `form_num` | s, d, p, na, u |
| Number | `num` | s (singular), d (dual), p (plural), na, u |
| Mood | `mod` | i (indicative), j (jussive), s (subjunctive), na, u |
| Person | `per` | 1, 2, 3, na |
| Rationality | `rat` | y (rational/human), n (irrational), na |
| State | `stt` | c (construct/idafa), d (definite), i (indefinite), na, u |
| Voice | `vox` | a (active), p (passive), na, u |

### Open-set lexical features

| Feature | Description |
|---------|-------------|
| `diac` | Fully diacritized surface form |
| `lex` | Lemma (citation form) |
| `root` | Traditional Arabic root consonants |
| `pattern` | Templatic morphological pattern (وزن) |
| `gloss` | English gloss(es), semicolon-separated |
| `bw` | Buckwalter POS tag string |
| `caphi` | CAPHI phonological representation |
| `catib6` | CATiB6 POS tag |
| `ud` | Universal Dependencies POS tag |
| `source` | Analysis source: lex, punct, foreign, spvar, digit, backoff |

### Clitic features

| Feature | Description | Example values |
|---------|-------------|----------------|
| `prc0` | Article proclitic | 0, Al_det, lA_neg, mA_neg, mA_rel |
| `prc1` | Prep proclitic | 0, bi_prep, li_prep, ka_prep, la_prep, min_prep |
| `prc2` | Conj proclitic | 0, fa_conj, wa_conj |
| `prc3` | Question proclitic | 0, >a_ques |
| `enc0` | Pronominal enclitic | 0, 1s_poss, 3ms_dobj, etc. (40+ values) |

### Probability features

| Feature | Description |
|---------|-------------|
| `pos_logprob` | Log probability of the POS |
| `lex_logprob` | Log probability of the lemma |
| `pos_lex_logprob` | Log probability of the POS-lemma pair |

---

## 3. Pre-trained Models & Data

| Package | Size | License | Description |
|---------|------|---------|-------------|
| `morphology-db-msa-r13` | 40.5 MB | GPL v2 | CALIMA Star MSA morphology DB (default) |
| `morphology-db-egy-r13` | 67.3 MB | GPL v2 | CALIMA Star Egyptian Arabic DB |
| `disambig-mle-calima-msa-r13` | 88.7 MB | GPL v2 | MLE disambiguation for MSA |
| `disambig-mle-calima-egy-r13` | 27.2 MB | GPL v2 | MLE disambiguation for Egyptian |
| BERT unfactored models | varies | | MSA, Egyptian, Gulf BERT disambiguation |
| `dialectid-default` | 282.3 MB | MIT | 26-class dialect ID model |
| `ner-arabert` | 541.6 MB | AraBERT | Named Entity Recognition |
| `sentiment-analysis-arabert` | 541.6 MB | AraBERT | Sentiment analysis |

Data installed at `~/.camel_tools/` (or `$CAMELTOOLS_DATA`).

---

## 4. Mapping to AWN4 Audit — 35 Questions Across 7 Levels

### Level 1: Lemma Quality — STRONG

| Audit Question | CAMeL Tool | How |
|---|---|---|
| Q1.1 Citation form valid? | `Analyzer.analyze(lemma)` | Empty result = unknown to CALIMA |
| Q1.2 Diacritization correct? | `Analyzer` → `diac` | Compare AWN4 diacritics vs CALIMA canonical form |
| Q1.3 Root valid? | `Analyzer` → `root` | Traditional root consonants |
| Q1.4 Binyan/wazn correct? | `Analyzer` → `pattern` | Templatic morphological pattern |
| Q1.5 Lemma in CALIMA DB? | `Analyzer.analyze(lemma, backoff='NONE')` | No backoff = strict existence check |

### Level 2: Definition Quality — WEAK

| Audit Question | CAMeL Tool | How |
|---|---|---|
| Q2.1 Circular definition? | — | No capability. Needs LLM or custom logic. |
| Q2.2 Calque detection? | — | No capability. Needs LLM. |
| Q2.3 Definition words valid MSA? | `Analyzer` + `Disambiguator` | Analyze each word in definition; flag unknown words. |
| Q2.4 Dialect contamination in def? | `DIDModel26.predict()` | Flag definitions classified as non-MSA. |

### Level 3: Example Quality — MARGINAL

| Audit Question | CAMeL Tool | How |
|---|---|---|
| Q3.1 Example present? | — | Data check (76.1% missing). |
| Q3.2 Example parseable? | `Disambiguator.disambiguate()` | Low-confidence parses → potentially unnatural. |
| Q3.3 Target lemma in example? | `Disambiguator` → `lex` per token | Check if target lemma appears in disambiguated sentence. |

### Level 4: POS Validation — STRONG

| Audit Question | CAMeL Tool | How |
|---|---|---|
| Q4.1 POS correct? | `Analyzer` → `pos` | 30+ granular POS tags. |
| Q4.2 POS consistent with WN? | `Analyzer` → `ud` | Map AWN4 n/v/a/r to UD tags for cross-validation. |
| Q4.3 POS fine-grained type? | `Analyzer` → `pos` | Distinguish noun vs noun_prop vs noun_num vs noun_quant, etc. |

### Level 5: Semantic Relations — NONE

No capability. Requires `wn` package for graph traversal.

### Level 6: Arabic-Specific Properties — STRONG

| Audit Question | CAMeL Tool | How |
|---|---|---|
| Q6.1 Morphological pattern? | `Analyzer` → `pattern` | Wazn/binyan for verbs and nouns. |
| Q6.2 Plural forms? | `Generator.generate(lemma, {num:'p'})` | Enumerate all plurals in CALIMA. |
| Q6.3 Gender? | `Analyzer` → `gen`, `form_gen` | Semantic vs morphological gender. |
| Q6.4 Number? | `Analyzer` → `num`, `form_num` | Semantic vs morphological number. |
| Q6.5 Rationality? | `Analyzer` → `rat` | Rational (human) vs irrational. |
| Q6.6 State/Definiteness? | `Analyzer` → `stt` | Construct, definite, indefinite. |
| Q6.7 Voice? | `Analyzer` → `vox` | Active vs passive. |
| Q6.8 Case? | `Analyzer` → `cas` | Nominative, accusative, genitive. |

### Level 7: Cross-Synset Consistency — MODERATE

| Audit Question | CAMeL Tool | How |
|---|---|---|
| Q7.1 Lemma normalization? | `dediac_ar()` + `normalize_unicode()` | Catch inconsistent diacritization across synsets. |
| Q7.2 POS consistency? | `Analyzer` → cross-reference `pos` | Same lemma should get same POS in all synsets. |
| Q7.3 Dialect contamination? | `DIDModel26.predict()` | Batch-check all definitions/examples. |

---

## 5. Coverage Summary

| Audit Level | CAMeL Coverage | Primary Module |
|---|---|---|
| **1. Lemma Quality** | STRONG | Analyzer (root, pattern, diac, lex) |
| **2. Definition Quality** | WEAK | Disambiguator + Dialect ID (partial) |
| **3. Example Quality** | MARGINAL | Disambiguator (parsability only) |
| **4. POS Validation** | STRONG | Analyzer (30+ POS, UD mapping) |
| **5. Semantic Relations** | NONE | — (needs `wn` package) |
| **6. Arabic-Specific Props** | STRONG | Analyzer + Generator (full feature model) |
| **7. Cross-Synset Consistency** | MODERATE | dediac + normalize + Dialect ID |

**Bottom line**: CAMeL Tools covers **Levels 1, 4, and 6 comprehensively** (~15 of 35 questions). It provides partial support for Levels 2, 3, and 7 (~6 questions). It has no capability for Level 5 (semantic relations, ~5 questions). The remaining ~9 questions require LLM-based analysis (Gemini Flash).

---

## 6. Gaps — What CAMeL Tools Does NOT Provide

1. **No WordNet/ontology integration** — No synset management, no hypernym/hyponym chains.
2. **No definition semantic analysis** — Cannot detect circular definitions, calques, or semantic completeness.
3. **No example generation or evaluation** — Does not assess example quality or naturalness.
4. **No semantic similarity** — No embeddings for synonym comparison within synsets.
5. **No root-to-lemma reverse lookup** — Goes word → analyses, not root → all_lemmas.
6. **MSA and Egyptian only** for morphological DB — Gulf/Levant only via BERT disambig models.

---

## 7. Code Patterns for the Audit

### Pattern A: Validate a lemma exists in CALIMA

```python
from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer

db = MorphologyDB.builtin_db('calima-msa-r13', 'a')
analyzer = Analyzer(db, backoff='NONE')
analyses = analyzer.analyze('كتب')
# Empty list → lemma unknown to CALIMA
```

### Pattern B: Extract root + pattern + POS

```python
for a in analyses:
    print(a['lex'], a['root'], a['pattern'], a['pos'])
# كَتَبَ  k.t.b  1a2a3  verb
# كُتُب   k.t.b  1u2u3  noun
```

### Pattern C: Generate all plurals of a noun

```python
from camel_tools.morphology.generator import Generator
db = MorphologyDB.builtin_db('calima-msa-r13', 'g')
generator = Generator(db)
forms = generator.generate('كِتَاب', {'pos': 'noun', 'num': 'p'})
# → كُتُب, etc.
```

### Pattern D: Diacritize text (MLE)

```python
from camel_tools.disambig.mle import MLEDisambiguator
disambig = MLEDisambiguator.pretrained('calima-msa-r13')
result = disambig.disambiguate(['كتب', 'المقالة'])
diac = result[0].analyses[0].analysis['diac']
```

### Pattern E: Detect dialectal content

```python
from camel_tools.dialectid import DialectIdentifier
did = DialectIdentifier.pretrained()
prediction = did.predict(['هذا التعريف يحتوي على كلمات عامية'])
# prediction.top → 'MSA' or dialect code (e.g., 'CAI', 'AMM')
```

### Pattern F: Reinflect a word (e.g., singular → plural)

```python
from camel_tools.morphology.reinflector import Reinflector
db = MorphologyDB.builtin_db('calima-msa-r13', 'r')
reinflector = Reinflector(db)
result = reinflector.reinflect('كاتب', {'num': 'p'})
# → كُتَّاب, كاتِبون, etc.
```
