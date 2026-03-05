#!/usr/bin/env python3
"""Validate a satellite translation batch output against its input."""

import json
import re
import sys


def has_arabic(text: str) -> bool:
    """Check if text contains Arabic characters."""
    return bool(re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', text))


def has_tashkeel(text: str) -> bool:
    """Check if text contains tashkeel diacritics."""
    return bool(re.search(r'[\u064B-\u0652]', text))


def validate(input_path: str, output_path: str) -> bool:
    with open(input_path) as f:
        inp = json.load(f)
    with open(output_path) as f:
        out = json.load(f)

    errors = []

    # Structure check
    if 'translations' not in out:
        errors.append("Missing 'translations' key in output")
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return False

    satellites = inp['satellites']
    translations = out['translations']

    # Count check
    if len(translations) != len(satellites):
        errors.append(
            f"Entry count mismatch: input={len(satellites)}, output={len(translations)}"
        )

    # Per-entry checks
    for i, (sat, trans) in enumerate(zip(satellites, translations)):
        tag = f"[{i}] {sat['id']}"

        # ID match
        if trans.get('id') != sat['id']:
            errors.append(f"{tag}: ID mismatch (got {trans.get('id', 'MISSING')})")

        # lem_ar
        lem_ar = trans.get('lem_ar', [])
        if not isinstance(lem_ar, list) or len(lem_ar) == 0:
            errors.append(f"{tag}: lem_ar must be a non-empty list")
        else:
            for j, lem in enumerate(lem_ar):
                if not isinstance(lem, str) or not has_arabic(lem):
                    errors.append(f"{tag}: lem_ar[{j}] not Arabic: {repr(lem)}")
                elif not has_tashkeel(lem):
                    errors.append(f"{tag}: lem_ar[{j}] missing tashkeel: {lem}")

        # def_ar
        def_ar = trans.get('def_ar', '')
        if not isinstance(def_ar, str) or len(def_ar) < 5:
            errors.append(f"{tag}: def_ar too short: {repr(def_ar)}")
        elif not has_arabic(def_ar):
            errors.append(f"{tag}: def_ar has no Arabic: {repr(def_ar)}")

        # ex_ar
        if not isinstance(trans.get('ex_ar'), list):
            errors.append(f"{tag}: ex_ar must be a list")

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):", file=sys.stderr)
        for e in errors[:30]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more", file=sys.stderr)
        return False

    print(f"VALIDATION PASSED: {len(translations)} entries OK")
    return True


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.json>", file=sys.stderr)
        sys.exit(1)

    ok = validate(sys.argv[1], sys.argv[2])
    sys.exit(0 if ok else 1)
