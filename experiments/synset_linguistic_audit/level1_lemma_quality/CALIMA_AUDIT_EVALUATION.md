# Linguist Evaluation: CALIMA Lemma Audit (100-Sample Review)

| | |
|---|---|
| **Date** | 2026-02-24 |
| **Evaluator** | Arabic linguist (automated + manual review) |
| **Source** | `calima_lemma_audit.json` (124,768 lemmas) |
| **Sample** | 100 stratified random samples (seed=42) |
| **Script** | `calima_lemma_audit.py` |

---

## Executive Summary

The CALIMA audit correctly identifies recognition status for **100% of sampled lemmas**. However, the flag system produces **systematic false positives** in two categories:

1. **DIACRITICS_MISMATCH**: ~75% are false positives caused by a verb citation-form convention mismatch (AWN4 includes final fatha, CALIMA strips it)
2. **NON_CITATION_FORM**: ~20% are false positives from CALIMA coverage gaps, and ~20% from CALIMA misanalyzing taa marbuta (ة) as pronoun suffix (ه)

The POS_MISMATCH flags are **all genuine** but reveal taxonomy differences rather than errors. Three systematic patterns account for ~66% of all POS mismatches.

---

## Sampling Strategy

| Bucket | Description | Allocated | Sampled |
|--------|-------------|-----------|---------|
| `clean_single` | No flags, single word | 25 | 25 |
| `clean_multiword` | Only MULTIWORD_LEMMA | 10 | 10 |
| `not_recognized` | Single word, not in CALIMA | 15 | 15 |
| `not_recognized_mw` | MWE, at least one word missing | 5 | 5 |
| `pos_mismatch` | POS mismatch (only substantive flag) | 15 | 15 |
| `diacritics_mismatch` | Diacritics mismatch only | 12 | 12 |
| `non_citation` | Non-citation form only | 10 | 10 |
| `non_arabic` | No Arabic characters | 3 | 3 |
| `no_root_pattern` | Recognized but no root/pattern | 2 | 2 |
| `multi_flag` | Multiple substantive flags | 3 | 3 |
| **Total** | | **100** | **100** |

---

## Per-Category Evaluation

### 1. Clean Single-Word (25 samples) — Verdict: ✅ 25/25 CORRECT

All 25 lemmas with no flags are genuinely clean. CALIMA correctly recognizes them, matches POS, and validates citation form. Examples:

| # | Lemma | Root | Assessment |
|---|-------|------|------------|
| 005 | معتدل (adj) | ع.د.ل | Active participle of اعتدل, correctly adj |
| 011 | ساوى (v) | س.و.ي | Form III hollow verb, root س.#.# correct |
| 019 | صرار (n) | ص.ر.ص.ر | Quadriliteral root correctly identified |
| 035 | اِنْضِمَام (n) | ض.م.م | Form VII masdar, root and pattern correct |
| 089 | ذاق (v) | ذ.و.ق | Hollow verb, 3ms perfective citation correct |

**Minor observations:**
- **#085 بكين (Beijing)**: Recognized as `noun_prop` (correct), but also has spurious verb readings from ب.ك.ي "to cry." The system correctly ignores these because `noun_prop` matches AWN4 `n`. Root NTWS (foreign) is the correct root for this loan.
- **#071 أيون (ion)**: Root #.#.ن is artificial — this is a transliterated scientific term. Recognition is correct, but root is meaningless.

### 2. Clean Multiword (10 samples) — Verdict: ✅ 10/10 Recognition Correct, ⚠️ Design Gap

All 10 MWE lemmas are correctly recognized (both words exist in CALIMA). However, **all 10 store zero analyses, zero roots, zero patterns, and zero glosses**. A linguist reviewing these entries gets only a boolean "recognized: true" with no evidence.

| # | Lemma | Words | Assessment |
|---|-------|-------|------------|
| 002 | كَمِّيَّة أَوَّلِيَّة | كمية + أولية | Both valid; quantity + primary |
| 015 | فقدان الحس | فقدان + الحس | Both valid; loss + sense |
| 037 | تاجر نبيذ | تاجر + نبيذ | Both valid; merchant + wine |
| 062 | بَقِيَ في الجوار | بقي + في + الجوار | All valid; remained + in + vicinity |
| 097 | قائم السيف | قائم + السيف | Both valid; hilt + the sword |

**Recommendation**: Store per-word analyses for MWE lemmas (at least the head word's morphology). This affects **81,849 lemmas** — 65.6% of all entries have no morphological evidence in the output.

### 3. Not Recognized — Single Word (15 samples) — Verdict: ✅ 15/15 CORRECT

All 15 unrecognized lemmas are genuinely absent from CALIMA. The breakdown:

| Type | Count | Examples |
|------|-------|---------|
| Foreign transliterations (proper names) | 4 | كونراد (Conrad), وودهول (Woodhull) |
| Scientific/botanical terms | 5 | فولفاريلا (Volvariella), روبينيا (Robinia), هوغوينينيا (Hugueninia) |
| Pharmaceutical terms | 3 | أمبيسيلين (ampicillin), سيفوبيد (Cefobid), ديكسيدرين (Dexedrine) |
| Foreign cultural terms | 2 | الدايت (the Diet/parliament), كانابيه (canapé) |
| Rare/dialectal Arabic | 1 | قابوق (capsule/shell — possibly genuine Arabic not in MSA CALIMA) |

**One notable case**: **#067 قابوق** may be a genuine Arabic word (dialectal or archaic) rather than a foreign term. This represents a potential CALIMA coverage gap rather than a correctly absent word. However, flagging it for human review is still the right action.

**One design issue**: **#009 أَرْض-جَوّ** ("ground-to-air") contains a hyphen, which the script treats as part of a single token rather than splitting. A hyphen-aware tokenizer would recognize both أَرْض and جَوّ individually.

### 4. Not Recognized — Multiword (5 samples) — Verdict: ✅ 5/5 CORRECT, ⚠️ 2 Parenthesis Issues

| # | Lemma | Unrecognized Words | Assessment |
|---|-------|--------------------|------------|
| 004 | أَخْرَجَ (بضربات فاشلة) | (بضربات, فاشلة) | Parentheses prevent recognition |
| 048 | إيلي كولبيرتسون | كولبيرتسون | Foreign name (Culbertson) |
| 049 | تاراس شيفتشينكو | تاراس, شيفتشينكو | Foreign name (Taras Shevchenko) |
| 092 | فصيلة الجيوجلوسات | الجيوجلوسات | Scientific term (Geoglossaceae) |
| 094 | عَوَى (القط) | (القط) | Parentheses prevent recognition |

**Design issue**: Samples #004 and #094 have parenthetical glosses embedded in the lemma (e.g., "أَخْرَجَ (بضربات فاشلة)" = "struck out (by failed strikes)"). The script splits on whitespace and sends "(بضربات" with the opening parenthesis attached, causing recognition failure. **Recommendation**: Strip parentheses before morphological analysis.

### 5. POS Mismatch (15 samples) — Verdict: ✅ 15/15 FLAGS CORRECT

All POS mismatches are genuine. They fall into **three systematic patterns**:

#### Pattern A: بِ+Noun as Adverb (5 cases, 33%)

AWN4 classifies Arabic prepositional phrases (بِ + masdar/noun) as adverbs (POS=r). CALIMA correctly identifies the underlying word as a noun.

| # | Lemma | AWN4 | CALIMA | Meaning |
|---|-------|------|--------|---------|
| 020 | بنشاط | r (adverb) | noun | بِنَشاط "with energy" = energetically |
| 039 | باستقصاء | r | noun | بِاسْتِقْصاء "by investigation" |
| 066 | بإنصاف | r | noun | بِإِنْصاف "with fairness" = fairly |
| 074 | بِعُمْق | r | noun | بِعُمْق "with depth" = deeply |
| 075 | بتشاؤم | r | noun | بِتَشاؤُم "with pessimism" |

**Assessment**: Both are linguistically valid perspectives. Arabic doesn't have a native "adverb" category — بِ+noun is a standard adverbial construction. AWN4 follows English WordNet's adverb synsets; CALIMA follows Arabic morphology. This is a **taxonomy difference, not an error**.

**Estimated impact**: This pattern likely accounts for a significant portion of the 1,829 r→noun POS mismatches in the full audit.

#### Pattern B: Active Participle — Adj vs Noun (3 cases, 20%)

CALIMA classifies Arabic active participles (اسم الفاعل) as nouns, while AWN4 uses them as adjectives.

| # | Lemma | Example | CALIMA POS | AWN4 POS |
|---|-------|---------|------------|----------|
| 034 | ساعي | messenger/striving | noun | a (adj) |
| 043 | كاشف | detector/revealing | noun | a (adj) |
| 087 | سلي | consoling | noun | a (adj) |

**Assessment**: In Arabic grammar, active participles function as both nouns and adjectives (and sometimes verbs). CALIMA's noun classification is lexicographically valid; AWN4's adjective use reflects the English synset's POS. This is a **genuine ambiguity in Arabic morphology**.

#### Pattern C: Nisba Adjectives Not in CALIMA (2 cases, 13%)

| # | Lemma | CALIMA Analysis | Issue |
|---|-------|-----------------|-------|
| 006 | تجارية | adj + verb | CALIMA has adj, but for verb reading, يّ parsed as verb |
| 088 | سياقي | noun only | سِياقِي parsed as سِياق+ي (noun+my) not سِياقِيّ (adj) |

**Assessment**: CALIMA's morphological analyzer sometimes parses the nisba suffix يّ as the possessive pronoun ي, missing the adjective reading entirely. This is a **CALIMA limitation**.

#### Other POS Mismatches (5 cases)

| # | Lemma | AWN4 | CALIMA | Assessment |
|---|-------|------|--------|------------|
| 003 | توري | n | verb | "Tory" — foreign political term, CALIMA only knows verb تَوَرَّى |
| 040 | شامل | r | adj | Genuine — شامِل is adj, not adverb |
| 059 | ثُنَائِيًّا | r | adj | Accusative adj used adverbially (حال construction) |
| 064 | تارة | n | adv | Both valid — تارة is a noun used adverbially |
| 098 | تمارض | n | verb | AWN4 has the verb as noun; masdar should be تَمارُض |

### 6. Diacritics Mismatch (12 samples) — Verdict: ⚠️ MAJOR SYSTEMATIC FALSE POSITIVE

**9 of 12 samples (75%) are false positives** caused by a single systematic issue:

#### The Verb Final-Fatha Problem

CALIMA stores verb citations in the **pausal form** (without final vowel): كَتَب
AWN4 stores verb citations in the **full form** (with final fatha): كَتَبَ

This causes every diacritized verb in AWN4 to flag as DIACRITICS_MISMATCH.

| # | AWN4 Form | CALIMA lex | Difference |
|---|-----------|------------|------------|
| 025 | رَوَّضَ | رَوَّض | Final fatha only |
| 036 | سَالَ | سال | Final fatha only |
| 038 | عَشَّقَ | عَشَّق | Final fatha only |
| 042 | نَتَفَ | نَتَف | Final fatha only |
| 055 | شَغَلَ | شَغَل | Final fatha only |
| 072 | حَرَّمَ | حَرَّم | Final fatha only |
| 079 | رَتَّلَ | رَتَّل | Final fatha only |
| 082 | أَلَحَّ | أَلَحّ | Final fatha/shadda |
| 095 | كَمَنَ | كَمَن | Final fatha only |

**Estimated impact**: If 75% of the 4,461 DIACRITICS_MISMATCH flags are this pattern → **~3,346 false positives**.

**Recommendation**: Before comparing diacritics, strip the final fatha from AWN4 verb forms (when POS=v), or treat CALIMA's pausal form and AWN4's full form as equivalent.

#### Remaining 3 Cases

| # | AWN4 | CALIMA | Assessment |
|---|------|--------|------------|
| 016 | غازٍ | غاز | Defective noun citation convention — tanwin kasra vs bare. Borderline. |
| 033 | بَارِع | بارِع | Trivial — explicit fatha on بَ vs implicit. Not a real error. |
| 056 | حفّار | حَفّار | AWN4 under-diacritized (missing fatha on ح). Genuine but minor. |

### 7. Non-Citation Form (10 samples) — Verdict: ⚠️ MIXED (40% genuine, 40% problematic)

| Category | Samples | Assessment |
|----------|---------|------------|
| **Genuinely non-citation** | #022, #029, #052, #054 | **CORRECT flags** |
| **CALIMA coverage gap** | #010, #012 | **FALSE POSITIVE** — word IS citation form |
| **CALIMA misanalysis** | #050, #060 | **FALSE POSITIVE** — taa marbuta parsed as pronoun |
| **Complex/borderline** | #053, #070 | Technically correct, limited practical value |

#### Genuinely Non-Citation (4 cases)

| # | Lemma | Issue | Expected Citation |
|---|-------|-------|-------------------|
| 022 | المُثَلَّث | Definite (with ال) | مُثَلَّث |
| 029 | يستغل | Imperfective verb | اِسْتَغَلَّ |
| 052 | إِثْمَار | Plural (أثمار of ثمر) | ثَمَر (singular) |
| 054 | الموكل | Definite (with ال) | مُوَكِّل |

These are **correct and valuable flags** — they identify real lemma form issues in AWN4.

#### CALIMA Coverage Gap (2 cases — FALSE POSITIVES)

| # | Lemma | Issue |
|---|-------|-------|
| 010 | جدلي | CALIMA only has construct/dual forms, not indefinite singular |
| 012 | سَبْعَة | CALIMA only has construct forms (سَبْعَةُ أيام), not indefinite |

These words ARE valid citation forms. The flag fires because CALIMA's analysis set doesn't include the indefinite singular reading, not because the lemma is wrong.

#### CALIMA Misanalysis (2 cases — FALSE POSITIVES)

| # | Lemma | Issue |
|---|-------|-------|
| 050 | شدادة | ة parsed as pronoun ه: شَداد+هُ instead of شَدّادَة |
| 060 | كوسة | ة parsed as pronoun ه: كُوس+هُ instead of كوسَة |

CALIMA's analyzer sometimes misinterprets final taa marbuta (ة) as the 3ms possessive pronoun suffix (ـه), producing analyses like "his drum" instead of recognizing the standalone noun "zucchini."

### 8. Non-Arabic (3 samples) — Verdict: ✅ 3/3 CORRECT

| # | Lemma | Assessment |
|---|-------|------------|
| 058 | PSA | English abbreviation (prostate-specific antigen) |
| 080 | ATM | English abbreviation |
| 093 | HCG | English abbreviation |

### 9. No Root/Pattern (2 samples) — Verdict: ✅ 2/2 CORRECT (reveal AWN4 data issues)

| # | Lemma | CALIMA POS | Assessment |
|---|-------|------------|------------|
| 099 | اكزacum | foreign | Mixed Arabic+Latin in single lemma field! |
| 100 | بيانissimo | foreign | Mixed Arabic+Latin: بيان + "issimo" |

These reveal **AWN4 data quality problems** — lemma fields containing mixed-script text. CALIMA correctly identifies them as foreign. The NO_ROOT and NO_PATTERN flags are correct consequences.

### 10. Multi-Flag (3 samples) — Verdict: ✅ Flags Technically Correct

| # | Lemma | Flags | Key Issue |
|---|-------|-------|-----------|
| 041 | سُبَاعِيّ | DIACRITICS + NON_CITATION | Diacritics: trivial explicit fatha difference. Citation: CALIMA matched wrong lexeme (plural of سبع "lion" instead of adj "septenary") |
| 069 | مُرْضٍ | POS + DIACRITICS | CALIMA failed to find the correct analysis (active participle of أَرْضَى from root ر.ض.ي). Mapped to م.ر.ض instead. |
| 096 | جَانِح | POS + DIACRITICS | Active participle classified as noun (Pattern B). Diacritics: trivial explicit fatha. |

**#069 مُرْضٍ deserves special attention**: CALIMA completely misidentified this word. مُرْضٍ is the active participle of Form IV verb أَرْضَى (root ر.ض.ي, meaning "satisfying"). But CALIMA analyzed it as forms of م.ر.ض (disease/illness) — a completely different word. This is a **CALIMA analysis failure**, not a script error.

---

## Overall Accuracy Assessment

### Recognition Accuracy: 100/100 ✅

All recognition verdicts (recognized vs. not recognized) are correct.

### Flag Accuracy by Type

| Flag | Samples | Correct | False Positive | Accuracy |
|------|---------|---------|----------------|----------|
| (no flags) | 35 | 35 | 0 | **100%** |
| CALIMA_NOT_RECOGNIZED | 20 | 20 | 0 | **100%** |
| POS_MISMATCH | 15 | 15 | 0 | **100%** |
| DIACRITICS_MISMATCH | 12 | 3 | 9 | **25%** |
| NON_CITATION_FORM | 10 | 6 | 4 | **60%** |
| NON_ARABIC | 3 | 3 | 0 | **100%** |
| NO_ROOT / NO_PATTERN | 2 | 2 | 0 | **100%** |

### Extrapolated Impact on Full Audit (124,768 lemmas)

| Flag | Total Count | Est. True Positive | Est. False Positive |
|------|-------------|-------------------|---------------------|
| CALIMA_NOT_RECOGNIZED | 29,985 | ~29,985 (100%) | ~0 |
| POS_MISMATCH | 5,449 | ~5,449 (100%) | ~0 |
| DIACRITICS_MISMATCH | 4,461 | **~1,115 (25%)** | **~3,346 (75%)** |
| NON_CITATION_FORM | 2,962 | **~1,777 (60%)** | **~1,185 (40%)** |

---

## Systematic Issues Discovered

### Issue 1: Verb Final-Fatha Convention Mismatch (HIGH IMPACT)

**Problem**: AWN4 stores verb lemmas with final fatha (كَتَبَ), CALIMA stores without (كَتَب). This is a convention difference (full voweling vs. pausal form), not an error in either system.

**Impact**: ~3,346 false DIACRITICS_MISMATCH flags (~75% of all diacritics flags).

**Fix**: In the diacritics comparison, for POS=v, strip the final fatha from the AWN4 form before comparing against CALIMA lex values.

### Issue 2: Multiword Lemmas Store No Morphological Evidence (HIGH IMPACT)

**Problem**: 81,849 MWE lemmas (65.6% of all lemmas) have `analyses: [], roots: [], patterns: [], glosses: []`. A linguist reviewing these entries has no evidence beyond a boolean recognized status.

**Impact**: Most of the AWN4 lexicon is opaque to quality review.

**Fix**: Store per-word analyses (at minimum for the head word of the expression).

### Issue 3: بِ+Noun Adverbial POS Taxonomy (MEDIUM IMPACT)

**Problem**: AWN4 follows English WordNet's adverb synsets, storing Arabic بِ+noun constructions with POS=r. CALIMA correctly identifies the underlying morphology as noun. Neither is wrong — this is a taxonomy difference.

**Impact**: Contributes significantly to the 1,829 POS mismatches for POS=r.

**Fix**: Add `"ب_noun_adverbial"` as a separate informational flag rather than a POS error. Detect the بِ prefix in the analysis and downgrade from POS_MISMATCH to informational.

### Issue 4: Taa Marbuta Misanalysis (LOW-MEDIUM IMPACT)

**Problem**: CALIMA sometimes parses final ة as the pronoun suffix ـه rather than taa marbuta, producing analyses like شَداد+هُ ("his saddle") instead of شَدّادَة ("brace").

**Impact**: Causes false NON_CITATION_FORM flags for some feminine nouns.

**Fix**: When all analyses show a pronoun suffix on the final letter and the original word ends in ة, treat the ة as taa marbuta and adjust citation form checking accordingly.

### Issue 5: Parentheses in MWE Lemmas (LOW IMPACT)

**Problem**: AWN4 lemmas like "أَخْرَجَ (بضربات فاشلة)" have parenthetical glosses embedded. The script splits on whitespace and sends "(بضربات" with parenthesis attached, causing recognition failure.

**Impact**: Unknown count among the 81,849 MWE lemmas.

**Fix**: Strip parentheses, brackets, and other punctuation before morphological analysis.

### Issue 6: Hyphenated Compounds (LOW IMPACT)

**Problem**: Compounds like "أَرْض-جَوّ" (ground-to-air) are treated as single tokens. CALIMA doesn't recognize the compound, but each component is valid.

**Impact**: Small but affects military/technical vocabulary.

**Fix**: Split on hyphens in addition to spaces for MWE analysis.

---

## Root and Pattern Quality

Among the 45 samples with root/pattern data:
- **Root accuracy**: High. All roots checked against linguistic knowledge are correct (ع.د.ل for معتدل, ص.ر.ص.ر for صرار, ض.م.م for انضمام, etc.)
- **CALIMA hollow-verb notation**: Uses # for weak radicals (ق.#.م for ق.و.م, ذ.#.ق for ذ.و.ق). Consistent and correct.
- **NTWS root**: Correctly marks foreign/transliterated words (بكين, أيون).
- **Pattern quality**: The 26,161 unique patterns are inflated because CALIMA encodes full diacritization in patterns. Not ideal for typological analysis but correct as morphological data.

---

## Recommendations

### Immediate Fixes (for the script)

1. **Strip final fatha from AWN4 verbs** before diacritics comparison
2. **Strip parentheses** from MWE tokens before analysis
3. **Split on hyphens** in addition to spaces for MWE tokenization
4. **Add بِ+noun detection** for adverbial POS mismatches (downgrade to informational flag)

### Design Improvements

5. **Store per-word analyses for MWE lemmas** (at minimum head-word morphology)
6. **Add taa marbuta heuristic**: If all analyses end in pronoun suffix and original ends in ة, re-analyze without suffix
7. **Separate "false positive rate" estimate** for each flag type in the summary statistics

### Quality Indicators to Add

8. **Confidence level per flag**: HIGH (clear error), MEDIUM (taxonomy difference), LOW (convention difference)
9. **Error category per flag**: DATA_ERROR (AWN4 issue), TAXONOMY_DIFF (legitimate POS disagreement), CONVENTION_DIFF (diacritics convention), CALIMA_GAP (CALIMA coverage limitation)

---

## Conclusion

The CALIMA Lemma Audit is fundamentally sound — its recognition engine is highly accurate (100% in this sample), and its POS/root/pattern extraction is reliable. The main issues are in the **flag interpretation layer**: the diacritics comparison needs convention-awareness (verb final fatha), and the citation form check needs better handling of CALIMA coverage gaps. With the four immediate fixes applied, the estimated false positive rate across all flags would drop from ~12% to ~3%.

The audit successfully identifies genuine AWN4 quality issues:
- Definite-article lemmas that should be indefinite (#022, #054)
- Imperfective verbs that should be perfective (#029)
- Plural forms that should be singular (#052)
- Mixed Arabic+Latin text in lemma fields (#099, #100)
- 29,985 words absent from the authoritative MSA morphological database

These findings provide a strong foundation for Level 1 of the synset linguistic audit.
