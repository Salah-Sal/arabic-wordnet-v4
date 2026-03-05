"""
verify_discrepancies.py
-----------------------
Verifies whether the three structural discrepancies found between AWN4 and OEWN 2024
are resolved in the updated AWN4 (post-satellite-adjective update).

Run from the arabic-wordnet-v4/ root:
    python experiments/dict_evidence_retrieval/verify_discrepancies.py

Requires:
    pip install wn
    wn.download('oewn:2024')   (one-time, if not already in ~/.wn_data/)
    # AWN4 is loaded from output/awn4.xml.gz by this script
"""

import sys
import os
import wn

AWN4_XML = os.path.join(os.path.dirname(__file__), "../../output/awn4.xml.gz")
AWN4_XML = os.path.normpath(AWN4_XML)

# The 9 hub verb ILIs identified as missing in the original discrepancy report
MISSING_VERB_ILIS = {
    "i22325": "change, alter, modify (transitive)",
    "i22389": "change (intransitive)",
    "i33603": "act, move",
    "i25546": "travel, go, move, locomote",
    "i25403": "move, displace (transitive)",
    "i30898": "make, create",
    "i33643": "induce, stimulate, cause",
    "i29849": "communicate",
    "i30960": "interact",
}

SEPARATOR = "─" * 60


def reload_awn4():
    """Remove old AWN4 from wn db and reload from current XML."""
    print("Step 0 — Reloading AWN4 database")
    print(f"  XML path: {AWN4_XML}")

    # Check what's currently loaded
    lexicons = wn.lexicons()
    awn4_loaded = [lx for lx in lexicons if lx.id == "awn4"]

    if awn4_loaded:
        print(f"  Removing existing AWN4 ({awn4_loaded[0].version})…")
        wn.remove("awn4")
    else:
        print("  No existing AWN4 in database.")

    print("  Loading updated AWN4…")
    wn.add(AWN4_XML)
    lexicons = wn.lexicons()
    awn4_new = [lx for lx in lexicons if lx.id == "awn4"]
    if awn4_new:
        print(f"  Loaded AWN4 {awn4_new[0].version} successfully.")
    else:
        print("  ERROR: AWN4 not found after add().", file=sys.stderr)
        sys.exit(1)
    print()


def check_satellite_adjectives(arb, en):
    """Check 1: Are satellite adjectives (pos='s') now present in AWN4?"""
    print(SEPARATOR)
    print("CHECK 1 — Satellite Adjectives (pos='s')")
    print(SEPARATOR)

    awn4_s = arb.synsets(pos="s")
    oewn_s = en.synsets(pos="s")
    n_awn4 = len(awn4_s)
    n_oewn = len(oewn_s)
    coverage = (n_awn4 / n_oewn * 100) if n_oewn else 0

    print(f"  OEWN satellite adj synsets: {n_oewn:,}")
    print(f"  AWN4 satellite adj synsets: {n_awn4:,}")
    print(f"  Coverage:                   {coverage:.1f}%")

    if n_awn4 == 0:
        print("  STATUS: ❌ STILL MISSING — satellite adjectives absent from AWN4")
    elif n_awn4 == n_oewn:
        print("  STATUS: ✅ RESOLVED — full satellite adjective parity")
    else:
        print(f"  STATUS: ⚠️  PARTIAL — {n_oewn - n_awn4:,} satellite synsets still missing")

    # Cross-check via ILI
    oewn_s_ilis = {ss.ili for ss in oewn_s if ss.ili}
    awn4_s_ilis = {ss.ili for ss in awn4_s if ss.ili}
    overlap = oewn_s_ilis & awn4_s_ilis
    print(f"\n  ILI cross-check:")
    print(f"    OEWN s-synsets with ILI: {len(oewn_s_ilis):,}")
    print(f"    AWN4 s-synsets with ILI: {len(awn4_s_ilis):,}")
    print(f"    ILI overlap:             {len(overlap):,}")
    print()


def check_missing_hub_verbs(arb, en):
    """Check 2: Are the 9 missing hub verbs now translated in AWN4?"""
    print(SEPARATOR)
    print("CHECK 2 — 9 Missing Hub Verbs")
    print(SEPARATOR)

    awn4_verb_ilis = {ss.ili for ss in arb.synsets(pos="v") if ss.ili}
    oewn_verb_ilis = {ss.ili for ss in en.synsets(pos="v") if ss.ili}

    print(f"  OEWN verb synsets with ILI: {len(oewn_verb_ilis):,}")
    print(f"  AWN4 verb synsets with ILI: {len(awn4_verb_ilis):,}")
    print()

    resolved = []
    still_missing = []
    for ili, desc in MISSING_VERB_ILIS.items():
        if ili in awn4_verb_ilis:
            resolved.append((ili, desc))
        else:
            still_missing.append((ili, desc))

    if resolved:
        print(f"  RESOLVED ({len(resolved)}/9):")
        for ili, desc in resolved:
            print(f"    ✅  {ili}  {desc}")
        print()

    if still_missing:
        print(f"  STILL MISSING ({len(still_missing)}/9):")
        for ili, desc in still_missing:
            print(f"    ❌  {ili}  {desc}")

    if not still_missing:
        print("  STATUS: ✅ ALL 9 HUB VERBS RESOLVED")
    elif not resolved:
        print(f"\n  STATUS: ❌ ALL 9 HUB VERBS STILL MISSING")
    else:
        print(f"\n  STATUS: ⚠️  PARTIAL — {len(still_missing)} of 9 still missing")
    print()


def check_ili_coverage(arb, en):
    """Check 3: ILI coverage — are the gaps inherent (from OEWN) or AWN4 errors?"""
    print(SEPARATOR)
    print("CHECK 3 — ILI Coverage")
    print(SEPARATOR)

    awn4_no_ili = [ss for ss in arb.synsets() if not ss.ili]
    oewn_no_ili = [ss for ss in en.synsets() if not ss.ili]
    awn4_total = len(arb.synsets())
    oewn_total = len(en.synsets())

    print(f"  AWN4 total synsets:      {awn4_total:,}")
    print(f"  AWN4 without ILI:        {len(awn4_no_ili):,}  ({len(awn4_no_ili)/awn4_total*100:.1f}%)")
    print(f"  OEWN total synsets:      {oewn_total:,}")
    print(f"  OEWN without ILI:        {len(oewn_no_ili):,}  ({len(oewn_no_ili)/oewn_total*100:.1f}%)")

    # Check if AWN4 ILI-free synsets are Arabic-custom (awn4- IDs with 8x/9x prefix)
    # vs ones inherited from OEWN with no ILI
    oewn_no_ili_ids = {ss.id for ss in oewn_no_ili}
    awn4_no_ili_awn4_custom = [ss for ss in awn4_no_ili if ss.id.startswith("awn4-8") or ss.id.startswith("awn4-9")]
    awn4_no_ili_oewn_inherited = [ss for ss in awn4_no_ili if ss not in awn4_no_ili_awn4_custom]

    print(f"\n  AWN4 ILI-free breakdown:")
    print(f"    AWN4-custom Arabic synsets (no OEWN equivalent): {len(awn4_no_ili_awn4_custom):,}")
    print(f"    OEWN-mapped synsets where OEWN itself lacks ILI: {len(awn4_no_ili_oewn_inherited):,}")

    if len(awn4_no_ili) <= len(oewn_no_ili):
        print(f"\n  STATUS: ✅ INHERENT — all ILI gaps match OEWN's own gaps (or fewer)")
    else:
        excess = len(awn4_no_ili) - len(oewn_no_ili)
        print(f"\n  STATUS: ⚠️  AWN4 has {excess:,} more ILI-free synsets than OEWN")
    print()


def check_relation_symmetry(arb, en):
    """Check relation counts against OEWN — compare key relation types."""
    print(SEPARATOR)
    print("CHECK 4 — Relation Counts vs OEWN")
    print(SEPARATOR)

    relations = ["hypernym", "hyponym", "similar", "also", "domain_topic",
                 "antonym", "derivation", "holonym", "meronym"]

    print(f"  {'Relation':<20} {'OEWN':>10} {'AWN4':>10} {'Diff':>10}")
    print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*10}")
    for rel in relations:
        oewn_count = sum(1 for ss in en.synsets() for _ in ss.get_related(rel))
        awn4_count = sum(1 for ss in arb.synsets() for _ in ss.get_related(rel))
        diff = awn4_count - oewn_count
        flag = "  ✅" if diff == 0 else (f"  +{diff:,}" if diff > 0 else f"  {diff:,}")
        print(f"  {rel:<20} {oewn_count:>10,} {awn4_count:>10,} {flag}")
    print()


def main():
    print("AWN4 Discrepancy Verification")
    print("=" * 60)
    print(f"Checking: {AWN4_XML}")
    print()

    reload_awn4()

    arb = wn.Wordnet("awn4:4.0", expand="")
    en = wn.Wordnet("oewn:2024", expand="")

    print(f"  AWN4 total synsets: {len(arb.synsets()):,}")
    print(f"  OEWN total synsets: {len(en.synsets()):,}")
    print()

    check_satellite_adjectives(arb, en)
    check_missing_hub_verbs(arb, en)
    check_ili_coverage(arb, en)
    check_relation_symmetry(arb, en)

    print(SEPARATOR)
    print("VERIFICATION COMPLETE")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
