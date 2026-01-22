# Arabic WordNet 4.0

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

- **Primary file**: `awn4.xml.gz`
- **Format**: WN-LMF 1.4 (Global WordNet Association standard)

## Installation

### Using the `wn` Python library

```bash
pip install wn
```

```python
import wn
wn.download('file:awn4.xml.gz')

# Query Arabic synsets
synsets = wn.synsets(lang='arb')
print(f"Total synsets: {len(synsets)}")
```

## Citation

If you use this resource, please cite:

```
Abdo, S. (2026). Arabic WordNet 4.0. https://github.com/Salah-Sal/arabic-wordnet-v4
```

BibTeX:

```bibtex
@misc{abdo2026arabicwordnet,
  author       = {Abdo, Salah},
  title        = {{Arabic WordNet 4.0}},
  year         = {2026},
  month        = jan,
  publisher    = {GitHub},
  url          = {https://github.com/Salah-Sal/arabic-wordnet-v4},
  note         = {Derived from Open English WordNet}
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
