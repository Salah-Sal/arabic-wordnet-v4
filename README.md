# Arabic WordNet 4.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18759165.svg)](https://doi.org/10.5281/zenodo.18759165)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

A comprehensive Arabic WordNet containing 109,823 synsets, derived from
the Open English WordNet.

## Overview

| Metric | Value |
|--------|-------|
| Total Synsets | 109,823 |
| Coverage | 100% of OEWN |
| Language | Modern Standard Arabic (arb) |
| Format | WN-LMF 1.4 XML |
| License | CC BY 4.0 |

## Download

- **Primary file**: [`output/awn4.xml.gz`](output/awn4.xml.gz)
- **Format**: WN-LMF 1.4 (Global WordNet Association standard)
- **Also available on**: [Zenodo](https://doi.org/10.5281/zenodo.18759165)

## Installation

Arabic WordNet 4.0 is a data file, not a Python package. To use it in Python,
you need the [`wn`](https://pypi.org/project/wn/) library (v1.0.0+, requires
Python 3.10+).

### Setup

```bash
# Clone the repository
git clone https://github.com/Salah-Sal/arabic-wordnet-v4.git
cd arabic-wordnet-v4

# Create a virtual environment (Python 3.10+ required)
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Usage

```python
import wn

# Load the data (one-time — persists to a local SQLite database)
wn.add('output/awn4.xml.gz')  # path relative to repo root

# Verify
print(wn.lexicons())  # [<Lexicon awn4:4.0 [arb]>]

# Query Arabic synsets
synsets = wn.synsets(lang='arb')
print(f"Total synsets: {len(synsets)}")

# Look up a word
for ss in wn.synsets('كتاب', lang='arb'):
    print(ss.id, ss.lemmas(), ss.definition())
```

After the initial `wn.add()` call, the data is cached locally and you can query
it in future sessions without reloading:

```python
import wn
synsets = wn.synsets(lang='arb')  # works immediately, no wn.add() needed
```

## Citation

If you use this resource, please cite:

```
Abdo, S. (2026). Arabic WordNet 4.0 (v4.0.0) [Data set]. Zenodo.
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
  version      = {4.0.0},
  doi          = {10.5281/zenodo.18759165},
  url          = {https://doi.org/10.5281/zenodo.18759165}
}
```

## Methodology

Arabic WordNet 4.0 was created by translating the Open English WordNet
into Arabic using AI-assisted translation (Google Gemini 3 Pro Preview).

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
