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

The version string lives in two places that must stay in sync:
- `output/awn4.xml` — the `<Lexicon id="awn4" version="4.0" ...>` attribute
- `WN-LMF-1.4.dtd` — not versioned, but referenced

Current version: **4.1**

---

## Checklist A — After Modifying `awn4.xml` (data changes)

Run these steps in order every time the data changes.

### 1. Run the validation suite

```bash
python scripts/validate_awn4.py --save
# Writes: output/validation_report.txt
```

All 8 checks must pass before proceeding. Fix any failures first.

### 2. Re-compress to `awn4.xml.gz`

```bash
gzip -k -f output/awn4.xml
# Produces: output/awn4.xml.gz (overwrites existing)
```

Both `awn4.xml` and `awn4.xml.gz` must be committed together.

### 3. Update the README metrics

Edit `README.md` — update the Overview table:

| Field | Where to get the current value |
|-------|-------------------------------|
| Total Synsets | `len(wn.Wordnet('awn4:4.0').synsets())` |
| Lexical Entries | count `<LexicalEntry>` elements in XML |
| Senses | count `<Sense>` elements in XML |
| Semantic Relations | count `<SynsetRelation>` elements |

Also update the repo description on GitHub
(Settings → About → Description) — it still shows the initial synset count.

### 4. Update `docs/awn4_validation_report.md`

If synset counts or relation totals changed, update the tables in the report.
Add an update note at the top with the date and new counts.

### 5. Bump the version

Increment according to the versioning scheme above:

```bash
# In output/awn4.xml, update the Lexicon version attribute:
# version="4.0"  →  version="4.1"  (for MINOR change)
# Then re-run steps 1-4.
```

### 6. Commit to `main`

```bash
git add output/awn4.xml output/awn4.xml.gz output/validation_report.txt
git add README.md docs/awn4_validation_report.md
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

---

## Quick Reference: Key Statistics Commands

```python
import wn
arb = wn.Wordnet('awn4:4.0', expand='')

print(f"Total synsets:   {len(arb.synsets()):,}")
print(f"Nouns:           {len(arb.synsets(pos='n')):,}")
print(f"Verbs:           {len(arb.synsets(pos='v')):,}")
print(f"Adjectives (a):  {len(arb.synsets(pos='a')):,}")
print(f"Satellite (s):   {len(arb.synsets(pos='s')):,}")
print(f"Adverbs:         {len(arb.synsets(pos='r')):,}")
print(f"With ILI:        {sum(1 for ss in arb.synsets() if ss.ili):,}")
print(f"Without ILI:     {sum(1 for ss in arb.synsets() if not ss.ili):,}")
```
