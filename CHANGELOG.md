# Changelog

All notable changes to the Arabic WordNet project will be documented in this file.

## [4.0] - 2024

### Added
- Initial release of Arabic WordNet 4.0
- 109,823 synsets translated from Open English WordNet (OEWN) 2024
- Full Arabic definitions for all synsets
- Arabic lemmas (1-4 per synset, average ~1.5)
- Arabic examples where available
- Synset relations (hypernym, hyponym, meronymy, holonymy, etc.)
- ILI mappings for cross-linguistic linking (97.2% coverage)
- WN-LMF 1.4 compliant XML format

### Features
- Deterministic ID generation using SHA-256 hashing for version stability
- Proper Arabic script attribute (`script="Arab"`)
- Multiple senses per lemma supported with ordering

### Excluded (by design)
- SenseRelations (antonym, derivation) - require manual cross-linguistic validation
- Will be added in future versions after proper review

## Comparison with Previous Versions

| Version | Year | Synsets | Source |
|---------|------|---------|--------|
| AWN v1 | 2006 | ~11,000 | PWN 3.0 |
| AWN v2 | 2013 | ~9,916 | PWN 3.0 |
| AWN v3 | 2018 | ~9,916 | PWN 3.0 |
| **AWN v4** | **2024** | **109,823** | **OEWN 2024** |

This represents an **11x increase** in coverage.
