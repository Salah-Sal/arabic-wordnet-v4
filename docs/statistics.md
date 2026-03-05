# Arabic WordNet 4.0 Statistics

Generated: 2026-01-22
Updated: 2026-03-04 (post-satellite adjective update — full OEWN 2024 parity)

## Summary

| Metric | v4.0 (initial) | Current |
|--------|---------------|---------|
| **Total Synsets** | 109,823 | **120,630** |
| **Lexical Entries** | 124,653 | **136,041** |
| **Senses** | 166,643 | **184,238** |
| **Synset Relations** | 265,676 | **297,150** |

## Part of Speech Distribution

| POS | Count | Percentage |
|-----|-------|------------|
| Nouns (n) | 84,956 | 70.4% |
| Satellite Adjectives (s) | 10,720 | 8.9% |
| Verbs (v) | 13,830 | 11.5% |
| Head Adjectives (a) | 7,502 | 6.2% |
| Adverbs (r) | 3,622 | 3.0% |

## Relations Included

This version includes **SynsetRelations** (semantic, language-independent):
- hypernym, hyponym
- instance_hypernym, instance_hyponym
- mero_member, mero_part, mero_substance
- holo_member, holo_part, holo_substance
- entails, is_entailed_by
- causes, is_caused_by
- similar, also, attribute
- domain_topic, domain_region, has_domain_topic, has_domain_region
- exemplifies, is_exemplified_by

**Excluded** (lexical, language-specific): antonym, derivation, pertainym, participle

## ILI Coverage

| Metric | Value |
|--------|-------|
| Synsets with ILI | 117,414 (97.3%) |
| Synsets without ILI | 3,216 (2.7%) |

The 3,216 ILI-free synsets break down as:
- ~2,933 AWN4-custom Arabic synsets (no OEWN equivalent)
- ~283 OEWN-mapped synsets where OEWN itself lacks an ILI assignment

This exactly matches OEWN 2024's own ILI-free count (3,216), confirming the gaps are inherent.

## File Sizes

| Format | Size |
|--------|------|
| XML (uncompressed) | 75.2 MB |
| XML (gzip) | 11.3 MB |

## Data Quality

- No duplicate synsets
- No empty lemmas
- All synset relations point to valid targets
- 0 relations skipped (full OEWN 2024 parity achieved in commit `efeccc8`)

## OEWN 2024 Parity

| Metric | OEWN 2024 | AWN4 | Match |
|--------|-----------|------|-------|
| Total synsets | 120,630 | 120,630 | ✅ |
| hypernym relations | 93,446 | 93,446 | ✅ |
| hyponym relations | 93,446 | 93,446 | ✅ |
| similar relations | 23,188 | 23,188 | ✅ |
| also relations | 2,728 | 2,728 | ✅ |
| domain_topic relations | 6,946 | 6,946 | ✅ |

## Source Attribution

- Derived from Open English WordNet 2024
- Based on Princeton WordNet 3.0 structure
- Initial translation (109,823 synsets) generated with AI assistance (Google Gemini 3 Pro Preview)
- Satellite adjectives (10,720 synsets) and hub verbs (9 synsets) added via Claude translation pipeline
