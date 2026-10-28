# AWN4 Maintenance Guide

This document describes the steps a maintainer must take after modifying the
AWN4 data, scripts, or metadata. Follow the checklist that matches the type
of change you made.

---

## Versioning Scheme

AWN4 uses **semantic versioning** adapted for a lexical resource:

| Digit | Meaning | Example trigger |
|-------|---------|----------------|
| **MAJOR** (4.x.x) | Source wordnet changed (new OEWN version) | Upgrading from OEWN 2024 → OEWN 2025 |
| **MINOR** (x.1.x) | Synset count changes — additions or removals | Adding satellite adjectives, fixing missing synsets |
| **PATCH** (x.x.1) | Corrections to existing synsets only | Fixing a wrong lemma, correcting a definition |

The version lives in these places, which must stay in sync:
- `output/awn4.xml` — the `<Lexicon id="awn4" label="Arabic WordNet 4.x" version="4.x" ...>` attributes
- `scripts/convert_to_lmf.py` — `VERSION` and `LEXICON_LABEL`, which a rebuild writes into the XML
- The release metadata updated in steps 7–9 (git tag, README citation block, `CITATION.bib`)

The scripts read the version from the XML file itself, so none of them hardcodes it.

Current version: **4.1**

---

## Rebuilding `awn4.xml` from source

The XML can be regenerated from its own content, then edited as batch JSON:

```bash
python scripts/extract_translations.py   # writes data/extracted_batches/ (all synsets)
# ... edit or add translations in data/extracted_batches/ ...
python scripts/convert_to_lmf.py         # writes output/awn4.xml; OEWN supplies ILI + relations
```

`data/` is gitignored. A rebuild without edits reproduces the released XML
except for the sense order of 9 multi-sense entries: the 9 hub verbs and 78
upper-ontology nouns were appended after the ID-sorted batches in 4.1, and a
rebuild sorts them in by ID. Bump `VERSION` and `LEXICON_LABEL` in
`convert_to_lmf.py` before rebuilding for a new release.

---

## Checklist A — After Modifying `awn4.xml` (data changes)

Run these steps in order every time the data changes.

### 1. Re-compress to `awn4.xml.gz`

```bash
gzip -k -f output/awn4.xml
# Produces: output/awn4.xml.gz (overwrites existing)
```

Both `awn4.xml` and `awn4.xml.gz` must be committed together. Compress before
validating: the validator reads `awn4.xml.gz` by default, the file users download.

### 2. Run the validation suite

```bash
python scripts/validate_awn4.py --save
# Writes: output/validation_report.txt
```

All 8 checks must pass before proceeding. Fix any failures first. The
validator replaces any installed copy of the same `awn4:<version>` with the
file, so an unbumped version cannot hide your changes behind stale data, and
the report records which lexicon version it checked.

### 3. Update the README metrics and provenance

Edit `README.md` — update the Overview table:

| Field | Where to get the current value |
|-------|-------------------------------|
| Total Synsets | `len(wn.Wordnet('awn4').synsets())` |
| Lexical Entries | count `<LexicalEntry>` elements in XML |
| Senses | count `<Sense>` elements in XML |
| Semantic Relations | count `<SynsetRelation>` elements |

Also update the repo description on GitHub
(Settings → About → Description) — it still shows the initial synset count.

If the change adds LLM-generated content, record the product, model ID and
date with each batch of output, then update the AI disclosure in `NOTICE`, the
README Methodology table, and the `dc:description` in `convert_to_lmf.py`.
Unrecorded provenance cannot be reconstructed later.

### 4. Update `docs/awn4_validation_report.md`

If synset counts or relation totals changed, update the tables in the report.
Add an update note at the top with the date and new counts.

### 5. Bump the version

Increment according to the versioning scheme above:

```bash
# In output/awn4.xml, update the Lexicon version and label attributes:
# version="4.1"  →  version="4.2"  (for MINOR change)
# Make the same change to VERSION and LEXICON_LABEL in scripts/convert_to_lmf.py.
# Then re-run steps 1-4.
```

### 6. Commit to `main`

```bash
git add output/awn4.xml output/awn4.xml.gz output/validation_report.txt
git add README.md docs/awn4_validation_report.md scripts/convert_to_lmf.py
git commit -m "Release AWN4 v4.x.x: <short description of what changed>"
```

### 7. Tag the release

```bash
git tag -a v4.x.x -m "AWN4 v4.x.x — <description>"
git push origin main --tags
```

### 8. Create a GitHub Release

```bash
gh release create v4.x.x output/awn4.xml.gz \
  --title "Arabic WordNet 4.x.x" \
  --notes "$(cat <<'EOF'
## What changed
- <list changes>

## Statistics
| Metric | v4.x.x | Previous |
|--------|--------|----------|
| Synsets | 120,630 | 109,901 |
| Relations | 297,150 | 271,752 |

## Verification
All 8 validation checks pass. See output/validation_report.txt.
EOF
)"
```

> **Important:** The GitHub Release asset (`awn4.xml.gz`) is what users download
> via `wn.download('file:awn4.xml.gz')`. If you don't create a new release,
> users pulling from the release tag will get the old data.

### 9. Update Zenodo (major/minor releases only)

For MAJOR or MINOR version bumps, upload a new version to Zenodo:
1. Go to [zenodo.org](https://zenodo.org) → your deposit → "New Version"
2. Upload the new `awn4.xml.gz`
3. Update the metadata (synset count, description)
4. Publish → note the new version DOI
5. Update the version DOI in `CITATION.bib` and in the README citation block
   (version, month, doi, url and the synset count in the note)

Zenodo creates a new DOI for each version while the concept DOI
(`10.5281/zenodo.18335225`) always resolves to the latest. The README DOI
badge, the README download link and `NOTICE` deliberately use the concept
DOI, so they never need updating; only the version-pinned citations change
per release. Do not put a version DOI in the badge: that is how CITATION.bib
and NOTICE drifted to v4.0.0 metadata while the README said v4.1.0.

---

## Checklist B — After Modifying Scripts Only (no data change)

If you only changed Python scripts (`scripts/`, `experiments/`) with no
change to `awn4.xml`:

- [ ] Run the validation suite to confirm nothing broke: `python scripts/validate_awn4.py`
- [ ] Commit to the appropriate branch (`main` for production scripts,
  `explore/linguistic-resources` for review pipeline experiments)
- [ ] No version bump, no new release needed

---

## Checklist C — After Modifying Documentation Only

- [ ] Commit to `main`
- [ ] No version bump, no new release needed
- [ ] If the change corrects factual errors in the README, consider whether
  the GitHub repo description also needs updating

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production data + docs. Only fully validated AWN4 XML lives here. |
| `explore/linguistic-resources` | Review pipeline experiments, REVIEW_GUIDE.md, evidence retrieval scripts |

Merge `explore/linguistic-resources` → `main` when review pipeline improvements
are stable and ready for production use. Data changes (`awn4.xml`) always go
directly to `main`.

---

## Known State After Last Release (v4.1.0)

`v4.1.0` released 2026-03-05. All data commits are released. `main` is clean.

No unreleased data changes.

Known issues in the released 4.1 XML, to fix at the next data release:
- Its `dc:description` credits Claude only for the satellite adjectives. The
  9 hub verbs were also Claude's, and the model for the 78 upper-ontology nouns
  was not recorded; `convert_to_lmf.py` already writes the corrected text.
- Satellite adjectives have no Arabic examples (OEWN has English examples for 6,964).

---

## Quick Reference: Key Statistics Commands

```python
import wn
arb = wn.Wordnet('awn4', expand='')  # any installed version

print(f"Total synsets:   {len(arb.synsets()):,}")
print(f"Nouns:           {len(arb.synsets(pos='n')):,}")
print(f"Verbs:           {len(arb.synsets(pos='v')):,}")
print(f"Adjectives (a):  {len(arb.synsets(pos='a')):,}")
print(f"Satellite (s):   {len(arb.synsets(pos='s')):,}")
print(f"Adverbs:         {len(arb.synsets(pos='r')):,}")
print(f"With ILI:        {sum(1 for ss in arb.synsets() if ss.ili):,}")
print(f"Without ILI:     {sum(1 for ss in arb.synsets() if not ss.ili):,}")
```
