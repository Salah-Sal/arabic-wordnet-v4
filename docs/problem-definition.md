# Problem definition: grounding the lemmas of Arabic WordNet 4.1

Status: agreed problem statement, 2026-10-18. This document defines the problem and how it
will be measured. It deliberately proposes no correction method; that comes after the
measurement.

## 1. The resource

Arabic WordNet 4.1 (`output/awn4.xml`, `<Lexicon version="4.1">`) has 120,630 synsets,
136,041 lexical entries and 184,238 senses (lemma–synset pairs). Every synset mirrors an
Open English WordNet 2024 synset by ID (`awn4-00001740-n` ↔ `oewn-00001740-n`), and all
synset relations are copied from OEWN. There are no Arabic-native synsets.

The Arabic content was produced by LLM translation, synset by synset, with the English
definition in context: Google Gemini 3 Pro Preview for about 110K synsets and Anthropic
Claude for the 10.7K satellite adjectives and upper-ontology synsets added in 4.1.

## 2. Problem statement

The Arabic lemmas of AWN 4.1 were generated from a language model's internal knowledge.
They were never selected against:

1. **terminological standards**: the unified terms of the Arabic language academies and
   terminology bodies;
2. **lexicographic evidence**: that an Arabic dictionary records the word with this meaning;
3. **linguistic norms**: citation form, lexicalisation and register.

As a result, a lemma's validity and provenance cannot be known from the data. A correct
lemma and an invented one look identical in the file. The preliminary measurements below
show that a large share of lemmas diverge from terminological standards and from an earlier
human revision of Arabic WordNet, and that a minority are semantically wrong.

**The problem** is to give each (lemma, synset) pair a grounded status against those three
standards, and to measure how AWN 4.1 fares on each, before choosing any correction method.

## 3. What was observed

The figures come from an exploratory audit on 2026-10-18 (method in the appendix). They
orient the work; they are not the measurement this document defines.

### 3.1 Shape of the data

| Observation | Value |
|---|---|
| Lemmas per synset | 1 lemma: 52%, 2: 43%, 3 or more: 5% |
| Multi-word lemmas | 65% of entries |
| Diacritised lemmas | satellite adjectives 100%, verbs 64%, nouns 6% |
| Verbs in the imperfect instead of the perfect citation form | 4.7% (`يعطس`, `يعمل`) |
| Lemmas containing a parenthetical disambiguator | 586 verbs, 134 nouns (`صَفَّرَ (إلكترونياً)`) |
| Adverbs of the form `بشكل` + adjective | 16% |
| Adjectives of the form `غير / عديم / لا` + X | 8–13% |
| Synsets per lemma | some generic words are attached to many fine senses: `تماماً` to 41 adverb synsets |

### 3.2 Semantic validity (reading samples)

About 120 synsets were read against the English. They were drawn from three sets: a random
sample of 45, 30 synsets whose English lemmas are highly polysemous, and the 41 synsets
sharing `تماماً`.

- **Most lemmas are acceptable.** In the random sample, about 2 lemmas were clearly
  wrong-sense: *bathe* "swim for pleasure" → `اِسْتَحَمَّ`, and *bomb* → `فجّر`. About 5 more
  were borderline.
- **Errors concentrate in polysemous light verbs.** *catch* "be affected by (a cold)" →
  `أمسك، التقط`; *see* "deliberate" → bare `نظر` instead of `نظر في`.
- **Generic fillers on fine senses.** `تماماً` sits on *quite/rather* "to a degree", next to
  `إلى حد ما`, which means the opposite.
- **Descriptions stand in for words.** Examples: `اقْتَرَحَ رَسْمِيّاً`, `أرسل فاتورة`,
  `عديم الوركين`, and the calque `آكلة التين` (*figeater*).
- **The definitions are translated English glosses, not Arabic lexicography.** Some contain a
  wrong-sense word. For *altered*, "changed in form or character" became
  `… في الشكل أو الشخصية`, where *character* (nature) was rendered as personality.

### 3.3 Divergence from terminological standards

The dictionaries database holds 107 dictionaries. 51 of them are typed ARABTERM, and 50 of
those are terminology standards: the unified dictionaries, ALECSO's ArabTerm glossaries, the
Unified Medical Dictionary, the IEC Electropedia, AGROVOC and others. The remaining one,
al-Mawrid al-Hadith, is a general bilingual dictionary filed under the same type, so it is
excluded here.

For 21,588 synsets, an English lemma that has only one OEWN sense appears in a standard, so
the English bridge cannot drift to another meaning.

| Comparison | Result |
|---|---|
| AWN 4.1 shares at least one term with the standards | 49% |
| They share at least one content word | 75% |
| *For comparison:* AWN 4.1 shares a term with al-Mawrid alone (21,979 synsets) | 36% |

Examples of divergence:

| Concept | AWN 4.1 | Reference term (source) |
|---|---|---|
| anorexia nervosa | فقدان الشهية العصبي | قَهَم عُصابي (Unified Medical Dictionary) |
| shareware | برمجيات تجريبية، شيروير | بَرْمَجِيَّة مُشْتَرَكَة (unified IT dictionary); برمجيات تشاركية (informatics dictionary) |
| Gordon setter | جوردون سيتر | السّاطِر الغوردونيّ (al-Mawrid: bilingual, not a standard) |

A non-match is not automatically an error. Glossaries are incomplete and noisy, and the
first example sets the sanctioned term against the term in actual use (see policy 6.2).

### 3.4 Lexicographic attestation

| Lemma type | Found as a headword in any of the 107 dictionaries |
|---|---|
| Single-word lemmas | 73% |
| Multi-word lemmas | 14% |

### 3.5 Comparison with AWN V3

AWN V3 (Freihat, Khalilia, Bella & Giunchiglia 2024) is a human revision of AWN V1 by two
translators and a linguist. It covers 9,576 synsets, deleted 8,751 of 20,560 earlier lemmas,
and marks lexical gaps and phrasets. Its PWN 3.0 offsets align directly with AWN 4.1 IDs.

On the 9,547 overlapping synsets, AWN 4.1's lemma–synset pairs compare as follows:

| AWN 4.1 pairs | Share |
|---|---|
| Kept as validated lemmas by V3 | 37% |
| Explicitly deleted by V3's annotators | 10% |
| Marked by V3 as a gap or phraset | 2% |
| Neither confirmed nor rejected | 51% |
| *Synset level:* V3 validated lemmas absent from AWN 4.1 | 45% |

V3 is not treated as ground truth. Several of its deletions follow its strict anti-polysemy
policy rather than identifying errors: `تيار` removed from *electric current*, `اقتراع` from
*vote*, and *animal* marked as a lexical gap. A manual review also found quality problems in
the V3 data.

## 4. Consumers

The resource serves three kinds of user, and the status record must serve all three:

- **NLP use** (word sense disambiguation, machine translation, lexical substitution): needs
  every pair to be semantically valid, and needs full coverage.
- **A human thesaurus** for learners, writers and translators: needs real, idiomatic words,
  with descriptions marked as such.
- **A terminology reference**: needs the sanctioned term and its provenance.

## 5. The grounded status record

### Per (lemma, synset) pair

| Field | Values |
|---|---|
| sense | same · related · wrong · unverifiable |
| lexicality | word · established term · description (true gap) · description (a word exists) · transliteration |
| standard | matches a standard term · a different standard term exists · no standard covers it |
| attestation | dictionary sense · dictionary headword only (sense unverified) · human-revised wordnet (V3) · none |
| register | MSA · classical · colloquial · loanword |
| form | ok · defect (citation form, diacritics, parenthetical, agreement, Latin script) |

### Per synset

| Field | Values |
|---|---|
| missing | standard or attested terms absent from the synset |
| definition | faithful and idiomatic · translationese · contains a wrong-sense word |
| granularity | a generic lemma shared across many fine senses (flag) |
| order | which lemma is preferred first |

## 6. Policies

These decide what counts as an error. Without them, an error rate is undefined.

### 6.1 Lexical gaps

When Arabic has no word for the concept, the descriptive phrase stays as a lemma, tagged as
non-lexicalised, so that a thesaurus or terminology user can filter it out. A description
used where Arabic *has* a word is a defect: for example `أرسل فاتورة` where `فَوْتَرَ` or
`طالَبَ` exist.

### 6.2 Standard versus usage

When the sanctioned term and the term in actual use differ (`قهم عصابي` vs
`فقدان الشهية العصبي`), both are lemmas. Each carries its provenance.

### 6.3 Polysemy

A generic word that expresses the specific sense in context is valid, but it is ranked below
the specific term. `تيار` is valid on *electric current*, with `تيار كهربائي` first. This
differs from AWN V3, which removes such lemmas.

## 7. Evidence available

| Evidence | Covers | Limits |
|---|---|---|
| Dictionaries database: classical, modern (al-Wasīṭ, al-Kabīr), bilingual (al-Mawrid) | sense attestation, register | classical-heavy; weak on modern general vocabulary |
| Terminology standards: 50 ARABTERM-typed sources in the same database (al-Mawrid excluded) | standard terms | mostly technical domains |
| AWN V3 | candidate lemmas, human-rejected lemmas, gaps | policy-laden, quality issues; a source and a seed for hard cases, not gold |
| Rules and a morphological analyser | form | — |
| OEWN definitions, examples and hypernyms | sense, definition, granularity | judgement is required |

There is no usage corpus. The work stays within the dictionaries database for now. Qabas
(Birzeit) was considered and not added: it links lemmas morphologically and across lexicons,
but carries no senses, glosses or English mapping.

## 8. Measurement design (stage 1)

- **Population:** all 184,238 (lemma, synset) pairs, plus synset-level fields.
- **Sample:** a uniform random core of about 200 pairs, for an unbiased overall rate. On top
  of that, oversampled strata for locating errors:
  - polysemous verbs;
  - multi-word lemmas;
  - adverbs and satellite adjectives;
  - pairs that disagree with the glossaries;
  - pairs that V3 deleted.

  Estimates are weighted back to the population.
- **Judge:** open. A DSPy program running GLM‑5.3‑flash is intended to be part of the
  solution. How it is judged, calibrated and checked against human grading is the next design
  question. Whatever the judge, every reported error rate should come with the judge's
  agreement with a human-graded subset.
- **Output:** rates per field and stratum, with confidence intervals and judge agreement.
  These decide which correction problems are worth solving.

## 9. Out of scope for this document

- Correction methods.
- Retrieval pipelines.
- The earlier per-synset review waves.
- The evidence-filter experiment.

Those are candidate tools, to be chosen after the measurement.

## References

- Freihat, Khalilia, Bella, Giunchiglia (2024). *Advancing the Arabic WordNet: Elevating
  Content Quality.* OSACT 2024. https://aclanthology.org/2024.osact-1.9/ — data:
  https://github.com/HadiPTUK/AWN3.0
- Bentivogli, Pianta (2000). *Looking for lexical gaps.* EURALEX 2000.
- Bergh, Waitelonis, Siegel (2025). *Leveraging LLMs to Automatically Construct WordNets as
  Bilingual Resources.* GWC 2025. https://aclanthology.org/2025.gwc-1.24.pdf
- Jarrar, Hammouda (2024). *Qabas: An Open-Source Arabic Lexicographic Database.*
  LREC-COLING 2024. https://aclanthology.org/2024.lrec-main.1170

## Appendix: how the preliminary figures were computed

- **Data:** `output/awn4.xml` (4.1) and OEWN 2024 (`english-wordnet-2024.xml.gz`), joined by
  synset ID.
- **Form patterns (3.1):** regular expressions over every lemma–synset pair, counted per POS.
- **Glossary agreement (3.3):**
  - Only English lemmas with exactly one OEWN sense, matched case-insensitively against
    the English sides of the 50 standard sources (al-Mawrid al-Hadith excluded; an earlier
    draft included it and reported 45%).
  - Arabic terms were split on `، ; ؛ ,`. Brackets were stripped, and the text was
    normalised (hamza and alef forms, ta marbuta, diacritics), with and without the article.
- **Attestation (3.4):** the normalised lemma, with and without the article, looked up as an
  exact `headword_norm` in any dictionary.
- **AWN V3 (3.5):**
  - Source files: the "organized columns" CSVs.
  - The final column is the validated synset, or `GAP`; there are also "Deleted lemmas" and
    "Phrase" columns.
  - IDs were mapped as `awn4-{offset:08d}-{pos}`, trying both `a` and `s` for adjectives.
  - Lemmas were normalised as above.
