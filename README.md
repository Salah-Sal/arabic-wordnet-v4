# Arabic WordNet 4.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18759165.svg)](https://doi.org/10.5281/zenodo.18759165)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

A comprehensive Arabic WordNet with **full coverage** of the Open English WordNet (OEWN) 2024.

## Overview

| Metric | Value |
|--------|-------|
| Total Synsets | 120,630 |
| Lexical Entries | 136,041 |
| Senses | 184,238 |
| Semantic Relations | 297,150 |
| Language | Modern Standard Arabic (arb) |
| Format | WN-LMF 1.4 XML |
| License | CC BY 4.0 |

### POS Breakdown

| POS | Synsets |
|-----|--------|
| Nouns | 84,956 |
| Verbs | 13,830 |
| Adjectives | 7,502 |
| Satellite Adjectives | 10,720 |
| Adverbs | 3,622 |

## Download

- **Primary file**: [`output/awn4.xml.gz`](output/awn4.xml.gz) (~11 MB)
- **Format**: WN-LMF 1.4 (Global WordNet Association standard)
- **Also available on**: [Zenodo](https://doi.org/10.5281/zenodo.18759165)

## Installation

Arabic WordNet 4.0 is a data file, not a Python package. To use it in Python,
you need the [`wn`](https://pypi.org/project/wn/) library (v1.0.0+, requires
Python 3.10+).

### Setup

```bash
pip install wn
```

Or clone the repository:

```bash
git clone https://github.com/Salah-Sal/arabic-wordnet-v4.git
cd arabic-wordnet-v4
pip install -r requirements.txt
```

### Quick Start

```python
import wn

# Load the data (one-time — persists to a local SQLite database)
wn.add('output/awn4.xml.gz')

# Verify
print(wn.lexicons())  # [<Lexicon awn4:4.0 [arb]>]

# Query Arabic synsets
synsets = wn.synsets(lang='arb')
print(f"Total synsets: {len(synsets)}")  # 120630
```

After the initial `wn.add()` call, the data is cached locally and you can query
it in future sessions without reloading:

```python
import wn
synsets = wn.synsets(lang='arb')  # works immediately, no wn.add() needed
```

### Usage Examples

#### Look Up a Word

```python
import wn

for ss in wn.synsets('كتاب', lang='arb'):
    print(ss.id, ss.lemmas(), ss.definition())

# awn4-02873453-n ['كتاب', 'مجلد'] أشياء مادية تتكون من عدد من الصفحات مجلدة معاً
# awn4-06406508-n ['سِفر', 'كتاب'] قسم رئيسي من عمل مكتوب طويل
# awn4-06422547-n ['كتاب']          عمل مكتوب أو مؤلف تم نشره ...
```

#### Traverse Semantic Relations

```python
import wn

arb = wn.Wordnet(lang='arb')
ss = arb.synsets('كتاب')[2]  # publication sense

print(ss.definition())
# عمل مكتوب أو مؤلف تم نشره (مطبوع على صفحات مجلدة معاً)

for hyp in ss.hypernyms():
    print(f"Hypernym: {hyp.lemmas()} — {hyp.definition()}")
    # Hypernym: ['مطبوعة', 'منشور'] — نسخة من عمل مطبوع معروض للتوزيع

for hypo in ss.hyponyms()[:3]:
    print(f"Hyponym: {hypo.lemmas()} — {hypo.definition()[:50]}")
    # Hyponym: ['مرجع موثوق'] — عمل مكتوب موثوق به
    # Hyponym: ['كتب النوادر'] — كتب عن مواضيع غريبة أو غير عادية
    # Hyponym: ['دستور الأدوية'] — (علم الأدوية) كتاب يحتوي على ت...
```

#### Explore a Word's Senses

```python
import wn

arb = wn.Wordnet(lang='arb')

for word in arb.words('كتاب'):
    print(f"{word.lemma()} — {len(word.senses())} senses")
    for sense in word.senses():
        ss = sense.synset()
        print(f"  {ss.id}: {ss.definition()[:60]}")
```

#### Cross-Lingual Lookup (English to Arabic via ILI)

To look up the Arabic equivalent of an English word, first load both OEWN and AWN4,
then use the Interlingual Index (ILI) to bridge between them:

```python
import wn

# Load both wordnets (one-time)
wn.download('oewn:2024')          # English
wn.add('output/awn4.xml.gz')      # Arabic

arb = wn.Wordnet(lang='arb')

for ss in wn.synsets('book', lang='en', pos='n')[:3]:
    ili = ss.ili
    if ili:
        ar = arb.synsets(ili=ili)
        if ar:
            print(f"EN: {ss.lemmas()[:3]}")
            print(f"AR: {ar[0].lemmas()} — {ar[0].definition()[:60]}")
            print()

# EN: ['Koran', 'Quran', "al-Qur'an"]
# AR: ['القرآن', 'القرآن الكريم', 'الكتاب'] — الكتاب المقدس للإسلام ...
#
# EN: ['book']
# AR: ['كتاب'] — عمل مكتوب أو مؤلف تم نشره ...
#
# EN: ['Bible', 'Christian Bible', 'Book']
# AR: ['الإنجيل', 'الكتاب المقدس', 'الوحي'] — الكتابات المقدسة للديانات المسيحية
```

#### Using `expand` to Control Cross-Lingual Relations

When both OEWN and AWN4 are loaded, relation traversal may follow links into the
English lexicon by default. Use `expand=''` to restrict traversal to Arabic only:

```python
import wn

# Default: relations can expand into OEWN (English)
arb = wn.Wordnet(lang='arb')
print(arb.expanded_lexicons())  # [<Lexicon oewn:2024 [en]>]

# Restricted: stay within Arabic only
arb_only = wn.Wordnet(lang='arb', expand='')
print(arb_only.expanded_lexicons())  # []

# Both return the same Arabic hypernyms for this synset,
# but expand='' prevents any English-only relations from appearing
ss = arb_only.synsets('كتاب')[2]
for hyp in ss.hypernyms():
    print(hyp.lemmas(), hyp.definition()[:50])
```

For more on interlingual queries, see the
[`wn` documentation on interlingual features](https://wn.readthedocs.io/en/stable/guides/interlingual.html).

## Citation

If you use this resource, please cite:

```
Abdo, S. (2026). Arabic WordNet 4.0 (v4.1.0) [Data set]. Zenodo.
https://doi.org/10.5281/zenodo.18759165
```

BibTeX:

```bibtex
@dataset{abdo2026arabicwordnet,
  author       = {Abdo, Salah},
  title        = {{Arabic WordNet 4.0}},
  year         = {2026},
  month        = jan,
  publisher    = {Zenodo},
  version      = {4.1.0},
  doi          = {10.5281/zenodo.18759165},
  url          = {https://doi.org/10.5281/zenodo.18759165}
}
```

## Methodology

Arabic WordNet 4.0 was created by translating the Open English WordNet 2024
into Arabic using AI-assisted translation. The translation pipeline used
Google Gemini 3 Pro Preview for the initial 109,901 synsets (nouns, verbs,
adjectives, adverbs), and Anthropic Claude for the remaining 10,729 synsets
(satellite adjectives and upper-ontology entries).

All 120,630 synsets include Arabic definitions with full tashkeel
(diacritical marks) on lemmas.

## Attribution

This resource is derived from:

- **Open English WordNet** - https://en-word.net/
  Copyright (c) 2019-present, The Open English WordNet Team
  Licensed under CC BY 4.0

- **Princeton WordNet 3.0** - https://wordnet.princeton.edu/
  Copyright 2006 by Princeton University

## License

This work is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for full details.

## Contact

- **Author**: Salah Abdo
- **Email**: Salah.Abdo.Tech@gmail.com
- **Issues**: https://github.com/Salah-Sal/arabic-wordnet-v4/issues

## Version History

See [CHANGELOG.md](CHANGELOG.md) for version history.
