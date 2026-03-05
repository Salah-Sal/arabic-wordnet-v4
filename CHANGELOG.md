# Changelog

All notable changes to Arabic WordNet will be documented in this file.

## [4.1.0] - 2026-03-05

### Added
- +10,720 satellite adjectives (pos=`s`) — achieving full OEWN 2024 adjective coverage
- +9 missing hub verbs (act/move, change, travel, make, communicate, and others)
  that were structural backbone nodes for ~1,190 verb children
- +78 upper-ontology noun synsets completing the noun hierarchy

### Changed
- Total synsets: 109,823 → 120,630 (full OEWN 2024 parity)
- Semantic relations: 265,676 → 297,150 (0 skipped relations, full parity)
- All relation types now at exact parity with OEWN 2024 (hypernym, hyponym, similar, also, domain_topic)

### Source
- Satellite adjective translations generated with Anthropic Claude via Docker pipeline
- Verified against OEWN 2024: all 8 validation checks pass

---

## [4.0.0] - 2026-01-22

### Added
- Initial release of Arabic WordNet 4.0
- 109,823 synsets translated from Open English WordNet
- Full WN-LMF 1.4 XML format compliance
- Arabic definitions for all synsets
- Arabic lemmas for all synsets

### Source
- Derived from Open English WordNet 2024 edition
- Based on Princeton WordNet 3.0 structure
