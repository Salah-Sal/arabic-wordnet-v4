"""
Install a WN-LMF file into the wn database exactly as it is on disk.

wn.add() silently skips a lexicon whose id:version is already installed, so
after editing awn4.xml without bumping the version a plain wn.add() leaves the
old data in place and every later query reads it. The specifier also changes
with each release, so it must come from the file rather than being hardcoded.
"""

from pathlib import Path

import wn
import wn.lmf
import wn.project


def install_lexicon(path: Path) -> str:
    """Install the lexicon in *path*, replacing any installed copy.

    Returns its specifier (e.g. 'awn4:4.1') for wn.Wordnet().
    """
    infos = []
    for package in wn.project.iterpackages(path):  # decompresses .gz to a temp dir
        infos += wn.lmf.scan_lexicons(package.resource_file())
    if len(infos) != 1:
        raise SystemExit(f"ERROR: expected one lexicon in {path}, found {len(infos)}")
    spec = f"{infos[0]['id']}:{infos[0]['version']}"

    if any(lex.specifier() == spec for lex in wn.lexicons()):
        print(f"  Replacing installed {spec} with {path}")
        wn.remove(spec)
    wn.add(str(path))
    return spec
