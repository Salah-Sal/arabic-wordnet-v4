# Open-source toolkit for auditing Arabic WordNet 4.0

**Over 80 actively maintained open-source tools, libraries, and lexical resources can power a comprehensive linguistic audit of AWN4's 109,901 LLM-translated synsets.** The ecosystem spans Arabic morphological analysis (CAMeL Tools, Qalsadi, Qutrub), state-of-the-art diacritization (CATT, Shakkala), WordNet parsing (the `wn` Python package with built-in WN-LMF 1.4 support), Arabic language models for quality scoring (AraGPT2, AraBERT, CAMeLBERT), and batch LLM orchestration (Gemini Batch API, DSPy, Instructor). Two standout ecosystems anchor the audit pipeline: the **CAMeL Lab toolkit** (NYU Abu Dhabi) for ML-based morphological analysis and dialect detection, and **Taha Zerrouki's integrated suite** (Mishkal, Qalsadi, Qutrub, Arramooz, PyArabic) for rule-based, dictionary-grounded analysis. Together with the `wn` package for structural validation and the Gemini Batch API for scaled LLM review, these tools cover all 35 review questions across every automation tier.

The tools below are organized by audit function, with GitHub URLs, maintenance status, and mappings to the review question tiers. Questions Q1.x cover structural/format validation, Q2.x address lemma and morphological correctness, Q3.x handle diacritization and vocalization, Q4.x cover definition/gloss quality, Q5.x address semantic relations, Q6.x handle register and naturalness, and Q7.x cover coverage and completeness.

---

## Arabic morphological analysis forms the audit backbone

The single most important tool for the AWN4 audit is **CAMeL Tools** (`https://github.com/CAMeL-Lab/camel_tools`), the MIT-licensed Python toolkit from Nizar Habash's group at NYU Abu Dhabi. With **471+ commits** and active Python 3.12 support, it provides morphological analysis, BERT-based disambiguation, morphological generation, diacritization, POS tagging, dialect identification across 25 city-level dialects plus MSA, NER, and sentiment analysis. Its CALIMA Star morphological databases output roots (جذر), patterns (وزن), lemmas, full POS features, gender, number, case, state, voice, aspect, and mood — directly serving Q2.1 (lemma validation), Q2.2 (root-pattern verification), Q2.3 (verb form/binyan detection), Q3.1 (diacritization checking), and Q6.1 (MSA vs. dialect classification). The tool requires a separate `camel_data` download and a Rust compiler for some components.

**Farasa** (`https://github.com/qcri/FarasaSegmenter`, Python wrapper at `https://github.com/MagedSaeed/farasapy`) from QCRI provides state-of-the-art segmentation, POS tagging, lemmatization, diacritization, and dependency parsing. Its Java core runs through a Python bridge. Farasa serves Q2.1 and Q2.4 (segmentation, lemmatization) but carries a **research-only license** that may restrict production use.

For verb form identification — critical for Q2.3 — **Qutrub** (`https://github.com/linuxscout/qutrub`) is indispensable. This Arabic verb conjugator takes a vocalized verb with future vowel mark and transitivity, then generates all conjugated forms across Forms I through X (أبواب). It can verify that a verb entry in AWN4 uses the correct binyan and produce all expected inflections. **Qalsadi** (`https://github.com/linuxscout/qalsadi`) complements this as a morphological analyzer that returns vocalized forms, lemmas, roots, POS, stems, and affixes using the **Arramooz** dictionary database (`https://github.com/linuxscout/arramooz`), which provides an open-source Arabic morphological dictionary in SQL and CSV formats for direct lookup.

**Qutuf** (`https://github.com/Qutuf/Qutuf`), an Apache 2.0-licensed Java tool, uniquely outputs both morphological patterns (وزن) and roots (جذر) with **certainty scores**, making it valuable for Q2.2 where confidence in pattern identification matters. **Stanford Stanza** (`https://github.com/stanfordnlp/stanza`), Apache 2.0-licensed with 7.5K+ stars, provides UD-based Arabic POS tagging, lemmatization, and dependency parsing trained on the PADT treebank — useful as a validation cross-check for Q2.1 and Q2.4. For stemming, **Tashaphyne** (`https://github.com/linuxscout/tashaphyne`) uniquely performs simultaneous stem and root extraction via a finite-state automaton, while NLTK's built-in **ISRI stemmer** (`nltk.stem.ISRIStemmer`) offers a lighter-weight alternative without root dictionary validation.

For grammar checking (Q4.3), **LanguageTool** (`https://github.com/languagetool-org/languagetool`, 14.1K stars) has initial Arabic support with 114 grammar rules, and the **Arabic GEC pipeline** from CAMeL Lab (`https://github.com/CAMeL-Lab/arabic-gec`) uses AraBART fine-tuned on QALB datasets for grammatical error correction — directly applicable to detecting grammar errors in LLM-generated glosses.

---

## Diacritization tools enable vocalization validation at scale

Diacritization correctness (Q3.x) is one of the most critical audit dimensions, and multiple complementary tools exist. **CATT** (`https://github.com/abjadai/catt`), the Character-based Arabic Tashkeel Transformer, represents the **current state of the art** — its encoder-only and encoder-decoder transformer models using Noisy-Student training outperform GPT-4-turbo by **9.36% relative DER**. Apache 2.0-licensed, it achieves 30–35% relative DER improvements over prior work on WikiNews and CATT benchmarks.

**Shakkala** (`https://github.com/Barqawiz/Shakkala`) uses deep BiLSTM with character embeddings, achieving **DER 2.88% and WER 6.37%** on the Fadel et al. 2019 benchmark — significantly outperforming all non-neural systems. Its three model versions include a best-performing v3 limited to 315 characters. **Mishkal** (`https://github.com/linuxscout/mishkal`) takes a complementary rule-based approach: its pipeline runs morphological analysis via Qalsadi, applies word frequency scoring, then syntax analysis via ArAnaSyn and semantic analysis via Asmai. While achieving DER 13.78%, its interpretability is invaluable — it generates all possible diacritized forms for each word ranked by frequency, enabling direct **comparison against dictionary-attested forms** for Q3.2.

Additional neural diacritizers include **Shakkelha** (`https://github.com/AliOsm/shakkelha`, EMNLP 2019), **Deep Diacritization** (`https://github.com/BKHMSI/deep-diacritization`, WER 5.34%), and the QCRI **Advancing Arabic Diacritization** project (`https://github.com/qcri/advancing-arabic-diacritization`, EMNLP 2025). The **Arabic Text Diacritization Benchmark** (`https://github.com/AliOsm/arabic-text-diacritization`) provides a standard 55K-line, 2.3M-word dataset with DER/WER computation scripts for evaluating any diacritizer — essential for calibrating the audit pipeline.

The recommended diacritization audit strategy for Q3.x: run AWN4 entries through both CATT (neural, highest accuracy) and Mishkal (rule-based, dictionary-grounded), flag entries where the two disagree, and cross-reference against Arramooz and CAMeL Tools morphological output.

---

## The `wn` Python package anchors structural and relational validation

For parsing, validating, and querying AWN4's WN-LMF 1.4 XML format, the **`wn` package** (`https://github.com/goodmami/wn`, v1.0.0) is the primary tool. Created by Michael Wayne Goodman, it natively parses any WN-LMF XML file (versions 1.1 through 1.4) into a SQLite-backed queryable database with a single call: `wn.add("awn4.xml")`. Its modules directly serve structural audit questions:

- **`wn.validate`** checks for empty definitions, ill-formatted entries, duplicate definitions, and whitespace issues (Q1.1–Q1.3)
- **`wn.taxonomy`** provides `roots()`, `leaves()`, `hypernym_paths()`, and `taxonomy_depth()` — detecting orphan synsets, disconnected subtrees, and hierarchy anomalies (Q5.1–Q5.3)
- **`wn.similarity`** computes path similarity, Wu-Palmer, and LCH measures for semantic consistency checking (Q5.4)
- **`wn.lmf.load()`** returns the raw LexicalResource object for low-level field inspection

For **cycle detection** (Q5.2), combine `wn.taxonomy.hypernym_paths()` with NetworkX's `nx.find_cycle()` for rigorous graph analysis. The `wn` package also supports loading OEWN alongside AWN4 for interlingual comparison via CILI links — enabling Q7.1 (coverage checking against the source English wordnet).

The **Global WordNet Association schemas** (`https://github.com/globalwordnet/schemas`) provide the canonical **WN-LMF-1.4.dtd** for XML validation via `xmllint --dtdvalid WN-LMF-1.4.dtd awn4.xml` (Q1.1). The **gwn-scala-api** (`https://github.com/jmccrae/gwn-scala-api`) offers format conversion between WNLMF, JSON, RDF, and WNDB with a `--validate` flag. The **Open English WordNet** itself (`https://github.com/globalwordnet/english-wordnet`, 682 stars, 1,963 commits) serves as the gold-standard reference — the 2024 and 2025 editions provide the source synsets that AWN4 translated.

For comparing against previous Arabic WordNet versions, **AWN V3** (`https://github.com/HadiPTUK/AWN3.0`) provides 9,576 manually curated synsets with documented corrections from V1, and the original **AWN V1** is available at `https://sourceforge.net/projects/awnbrowser/` with a SQLite conversion at `https://github.com/AhlemGit/Arabic-WordNet-To-SQLite`.

---

## Language models and embeddings power quality and naturalness checks

For detecting unnatural, machine-generated text in AWN4 glosses (Q4.1, Q6.2), **AraGPT2** (`https://github.com/aub-mind/arabert`, models at `huggingface.co/aubmindlab/aragpt2-*`) provides perplexity scoring across four model sizes from 135M to **1.46B parameters**, trained on 77GB of Arabic text. High perplexity signals unnatural phrasing — a direct indicator of translation artifacts. **AraELECTRA** (same repo, `huggingface.co/aubmindlab/araelectra-base`) uses discriminator-based pre-training and achieves **98% accuracy** at detecting machine-generated text, making it directly applicable for flagging LLM-generated entries that read unnaturally.

**AraBERT** (`huggingface.co/aubmindlab`) with its masked language model scoring can evaluate whether specific terms are contextually appropriate in a gloss (Q4.2). **CAMeLBERT** (`https://github.com/CAMeL-Lab/CAMeLBERT`) provides a family of 8 BERT models covering MSA, Classical Arabic, Dialectal Arabic, and mixed registers — the **MSA vs. DA vs. CA variants enable register classification** (Q6.1), and fine-tuned NER models can flag named entities incorrectly included as common nouns.

For **duplicate and near-duplicate synset detection** (Q4.4), Arabic sentence embeddings are essential. The **Omartificial-Intelligence-Space Arabic Matryoshka Embeddings** (`huggingface.co/collections/Omartificial-Intelligence-Space/arabic-matryoshka-embedding-models`) achieve #1 on MTEB Arabic STS17 with a score of **85.3**. **Google LaBSE** (`sentence-transformers/LaBSE`) and **Microsoft multilingual-e5-large** (`intfloat/multilingual-e5-large`) provide strong multilingual alternatives. Computing pairwise cosine similarity across all 109K synset glosses flags redundant entries and translation duplicates.

For **dialect detection** (Q6.1), CAMeL Tools' built-in Dialect ID classifies text into 25 city-level dialects plus MSA, while **MARBERT** (`huggingface.co/UBC-NLP/MARBERT`) is pre-trained on dialectal Arabic tweets and fine-tunable for dialect identification. No dedicated **calque/translation artifact detector** exists for Arabic, but a composite approach using AraGPT2 perplexity + AraBERT MLM scoring + Arabic GEC error detection effectively identifies most translation artifacts.

---

## Lexical resources provide ground truth for dictionary attestation

For Q2.5 (dictionary attestation), several structured Arabic lexical resources are available. **Lane's Arabic-English Lexicon** is digitized in Perseus TEI XML at `https://github.com/laneslexicon/lexicon_xml` (CC BY-SA 3.0) — the authoritative classical Arabic reference. **Hans Wehr's Dictionary of Modern Written Arabic** has an open-source Flutter app at `https://github.com/GibreelAbdullah/HansWehrDictionary` with a SQLite database, and is searchable via `https://ejtaal.net`. The **Arabic Reverse Dictionary dataset** (`https://github.com/Waadtss/ArReverseDictionary`) provides **58,010 entries** from the LMF Contemporary Arabic dictionary in JSON format.

The **Arabic Ontology** from Birzeit University (`https://ontology.birzeit.edu`, tools at `https://github.com/SinaLab/sinatools`) offers ~1,300 fully ontologized concepts and 11,000 partially validated concepts mapped to Princeton WordNet, Wikidata, BFO, and DOLCE. Its **synonym evaluation tool** directly assesses synset membership quality (Q5.5). The associated **SinaTools** package includes ArabGlossBERT for word sense disambiguation and a synonyms generator that extends and evaluates synsets.

For **frequency validation** (Q7.2), the **CAMeL Arabic Frequency Lists** (`https://github.com/CAMeL-Lab/Camel_Arabic_Frequency_Lists`) derived from **17.3 billion tokens** with separate lists for Classical Arabic, Dialectal Arabic, MSA, and mixed text provide the most comprehensive frequency baseline. The **wordfreq** library (`https://github.com/rspeer/wordfreq`) offers quick Python-based frequency lookups with Arabic support. **Wiktextract** (`https://github.com/tatuylonen/wiktextract`) extracts structured Arabic word senses, translations, and synonyms from Wiktionary dumps — pre-extracted data is available at `https://kaikki.org/dictionary/`. The comprehensive **Masader** catalogue (`https://github.com/ARBML/masader`) indexes **500+ Arabic NLP datasets** with 25+ annotation attributes.

---

## Batch LLM processing at 109K-synset scale is both feasible and affordable

For running per-synset LLM review checks at scale (the automation tiers requiring LLM judgment), the **Gemini Batch API** (`https://ai.google.dev/gemini-api/docs/batch-api`) is the primary engine. Launched in early 2026, it offers a **50% cost discount** over standard rates with a 24-hour turnaround window. For AWN4's 109,901 synsets at approximately 500 input + 200 output tokens per synset, total cost at batch Gemini Flash pricing comes to roughly **$11**, making multiple audit passes economically feasible. The `google-genai` Python SDK supports inline requests and JSONL file upload. However, the free tier is severely limited (**500 RPD** for Flash post-December 2025 reductions) — Tier 1 billing enablement is essential.

**DSPy** (`https://github.com/stanfordnlp/dspy`, 28K+ stars, MIT license) from Stanford provides the ideal framework for structuring per-synset review prompts. Its typed signatures define input/output schemas (e.g., `synset_id, lemmas, gloss → verdict, issues, confidence`), and its **MIPROv2 optimizer** automatically improves prompts against a gold-standard sample. DSPy 3's JSONAdapter enforces valid structured output, and its multi-model portability lets you benchmark Gemini Flash against alternatives.

**Instructor** (`https://github.com/567-labs/instructor`, 9K+ stars) ensures every LLM response conforms to a Pydantic schema with automatic retries on validation failure — define a `SynsetReview` model and Instructor handles structured extraction from any provider. **LiteLLM** (`https://github.com/BerriAI/litellm`, 36K stars) provides a unified API layer across 100+ LLM providers with cost tracking, retry logic, and load balancing. For evaluating audit pipeline quality, **DeepEval** (`https://github.com/confident-ai/deepeval`, 6K+ stars) offers a Pytest-based unit-testing framework for LLMs with custom metric definitions and batch evaluation.

If local model inference is preferred, **vLLM** (`https://github.com/vllm-project/vllm`, 50K+ stars) provides high-throughput offline batch inference with structured JSON output via PagedAttention. **Outlines** (`https://github.com/dottxt-ai/outlines`, 13.4K stars, Apache 2.0) guarantees 100% valid JSON through FSM-based constrained token sampling — relevant for local models where API-level structured output isn't available.

---

## String processing and corpus tools complete the pipeline

**PyArabic** (`https://github.com/linuxscout/pyarabic`, GPLv3) is the foundational utility library for all Arabic text processing: `strip_tashkeel()` for diacritics removal, `vocalizedlike()` for diacritics-aware comparison, Alef/Hamza/Taa Marbuta normalization, Buckwalter transliteration, and character classification. It underpins Mishkal, Qalsadi, Qutrub, and Tashaphyne, forming a consistent text processing layer for Q1.x and Q3.x.

**SinaTools** (`https://github.com/SinaLab/sinatools`, MIT license, published ACLing 2024) from Birzeit University provides a uniquely valuable **diacritic-based word matching** algorithm: the `Implication` algorithm determines whether two Arabic words with different diacritization are morphologically the same, achieving **99.32% accuracy**. This directly serves Q3.2 (comparing partially vocalized AWN4 entries against dictionary forms). SinaTools also includes a morphology tagger (90.5% lemmatization accuracy), word sense disambiguation, a synonyms generator, and Arabic-specific Jaccard similarity — all at 33K tokens/second.

For **Unicode normalization** (Q1.2), **PyICU** (`https://github.com/ovalhub/pyicu`) wraps the reference ICU library with full NFC/NFD/NFKC/NFKD normalization, locale-aware Arabic collation, and Unicode regex with Arabic script properties. The **tnkeeh** library (`https://github.com/ARBML/tnkeeh`) provides quick regex-based Arabic preprocessing including diacritics removal, tatweel removal, and HuggingFace dataset integration for ML pipelines.

For **fuzzy matching** across orthographic variants (Q2.6), the `deNormalize()` approach from al-Raqmiyyat (`https://alraqmiyyat.github.io/2013/01-02.html`) converts search terms into regex patterns matching all Arabic orthographic variants — an elegant solution for searching AWN4 entries despite Alef/Hamza inconsistencies.

For **collocation extraction and frequency analysis** (Q4.5, Q7.2), NLTK's collocations module (`nltk.collocations`) provides bigram/trigram extraction with PMI, chi-square, and likelihood-ratio measures when combined with PyArabic normalization. **ArabiCorpus** (`https://arabicorpus.byu.edu/`) offers a searchable 200-million-word corpus across newspapers, modern literature, and classical texts — though it is **scheduled for shutdown on July 1, 2027**. The **Tanzil Quran corpus** (`https://tanzil.net/`, Python interface at `https://github.com/hci-lab/PyQuran`) provides a gold-standard fully vocalized classical Arabic reference with morphological annotations. Stanza (`https://github.com/stanfordnlp/stanza`) and spaCy via the spacy-stanza bridge (`https://github.com/explosion/spacy-stanza`) provide UD-based Arabic parsing pipelines for syntactic analysis of glosses.

---

## Mapping tools to the 35 review questions

The following table maps the primary tool to each audit tier. Each tool listed is the recommended first choice; most questions benefit from cross-validation with a second tool.

| Audit tier | Review focus | Primary tools | GitHub repositories |
|---|---|---|---|
| Q1.x: Format & structure | WN-LMF validation, XML schema, field completeness | `wn` (validate, lmf), xmllint + WN-LMF-1.4.dtd | `goodmami/wn`, `globalwordnet/schemas` |
| Q2.x: Lemma & morphology | Root extraction, pattern verification, binyan detection, citation form, POS | CAMeL Tools, Qutrub, Qalsadi, Qutuf | `CAMeL-Lab/camel_tools`, `linuxscout/qutrub`, `linuxscout/qalsadi`, `Qutuf/Qutuf` |
| Q3.x: Diacritization | Tashkeel correctness, dictionary comparison, consistency | CATT, Mishkal, Shakkala, SinaTools (Implication) | `abjadai/catt`, `linuxscout/mishkal`, `Barqawiz/Shakkala`, `SinaLab/sinatools` |
| Q4.x: Gloss quality | Definition naturalness, grammar, duplicates, completeness | AraGPT2 (perplexity), Arabic GEC, Arabic embeddings, Gemini+DSPy | `aub-mind/arabert`, `CAMeL-Lab/arabic-gec`, `stanfordnlp/dspy` |
| Q5.x: Semantic relations | Hypernym cycles, orphan detection, relation consistency, taxonomy depth | `wn` (taxonomy), NetworkX, OEWN cross-reference | `goodmami/wn`, `globalwordnet/english-wordnet` |
| Q6.x: Register & naturalness | MSA vs. dialect, translation artifacts, calque detection | CAMeLBERT (dialect), AraELECTRA, AraGPT2 | `CAMeL-Lab/CAMeLBERT`, `aub-mind/arabert` |
| Q7.x: Coverage & completeness | Frequency attestation, dictionary coverage, lexical gaps | CAMeL Frequency Lists, wordfreq, Hans Wehr, Lane's, Arabic Ontology | `CAMeL-Lab/Camel_Arabic_Frequency_Lists`, `laneslexicon/lexicon_xml`, `SinaLab/sinatools` |

---

## Conclusion

The open-source Arabic NLP ecosystem has matured substantially, and **no single tool gap prevents a fully automated first-pass audit** of AWN4's 109,901 synsets. The most impactful toolchain combines CAMeL Tools (morphological ground truth), the `wn` package (structural validation), CATT + Mishkal (diacritization cross-checking), AraGPT2 (naturalness scoring), CAMeL Frequency Lists (attestation), and the Gemini Batch API + DSPy + Instructor (scaled LLM review at ~$11 per full pass). Two lesser-known but high-value discoveries are **SinaTools** from Birzeit University, whose diacritic-aware matching algorithm solves the hard problem of comparing partially vocalized entries at 99.3% accuracy, and **Qutuf**, which uniquely outputs morphological patterns with confidence scores. The Taha Zerrouki ecosystem (Mishkal, Qalsadi, Qutrub, Arramooz, PyArabic, Tashaphyne) deserves special attention: these six interlocking GPL-licensed tools share data structures and form a complete rule-based analysis pipeline complementary to CAMeL's ML-based approach — running both in parallel maximizes detection coverage. The practical bottleneck is not tooling but **calibration**: building a gold-standard sample of 500–1,000 manually reviewed synsets to tune thresholds for each automated check before scaling to the full dataset.