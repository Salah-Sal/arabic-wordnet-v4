# Arabic WordNet 4.0 (AWN4)

A comprehensive Arabic WordNet with 109,823 synsets, derived from the Open English WordNet (OEWN) 2024.

## Overview

| Metric | Value |
|--------|-------|
| Total Synsets | 109,823 |
| Nouns | ~84,000 |
| Verbs | ~14,000 |
| Adjectives | ~8,000 |
| Adverbs | ~4,000 |
| Coverage | 100% of OEWN 2024 |

## Quick Start

```python
import wn

# Add Arabic WordNet 4.0 from local file
wn.add('awn4.xml')

# Use it
ar = wn.Wordnet('awn4')
synsets = list(ar.synsets())
print(f'Total synsets: {len(synsets)}')

# Look up a word
words = ar.words(form='كتاب')
for word in words:
    for sense in word.senses():
        ss = sense.synset()
        print(f'{ss.id}: {ss.definition()}')
```

Output:
```
Total synsets: 109823
awn4-02873453-n: أشياء مادية تتكون من عدد من الصفحات مجلدة معاً
awn4-06422547-n: عمل مكتوب أو مؤلف تم نشره (مطبوع على صفحات مجلدة معاً)
awn4-06406508-n: قسم رئيسي من عمل مكتوب طويل
```

## Format

AWN4 is distributed in WN-LMF 1.4 XML format, compatible with:
- Global WordNet Association standards
- Open Multilingual Wordnet (OMW)
- Python `wn` library

## Attribution

This Arabic WordNet is derived from the [Open English WordNet](https://en-word.net/),
developed by the Global WordNet Association and licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## License

CC BY 4.0 - Creative Commons Attribution 4.0 International

## Version History

- **v4.0** (2024): Initial release with 109,823 synsets
  - Based on OEWN 2024
  - Includes SynsetRelations (hypernym, hyponym, meronymy, etc.)
  - Excludes SenseRelations (antonym, derivation) for accuracy

## Citation

```bibtex
@inproceedings{awn4,
  title = {Arabic WordNet 4.0: A Comprehensive Arabic Lexical Database},
  author = {[Authors]},
  booktitle = {Proceedings of the Global WordNet Conference 2024},
  year = {2024}
}
```

## Contact

[Contact Information]

## Project Structure

```
arabic-wordnet-v4/
├── README.md               # This file
├── LICENSE                 # CC BY 4.0 license
├── CHANGELOG.md           # Version history
├── CITATION.bib           # BibTeX citation
├── output/
│   ├── awn4.xml           # Main WordNet file (WN-LMF 1.4)
│   └── awn4.xml.gz        # Compressed version (10 MB)
├── scripts/
│   └── convert_to_lmf.py  # Conversion script
└── docs/
    └── statistics.md      # Detailed statistics
```
