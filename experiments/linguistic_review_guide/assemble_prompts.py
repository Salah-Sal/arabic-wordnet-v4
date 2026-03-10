#!/usr/bin/env python3
"""
Assemble complete review prompts for all evidence files.

For each .evidence.yaml file:
1. Preprocess it (strip noise fields)
2. Inject into prompt_template.md along with draft_api.md and output_template.yaml
3. Write the assembled prompt to generated_prompts/<synset_id>.md

Usage:
    python assemble_prompts.py
    python assemble_prompts.py --evidence-dir "path/to/evidence/files"
    python assemble_prompts.py --output-dir "path/to/output"
"""

import argparse
import os
import sys
import yaml

from preprocess_evidence import preprocess, ArabicDumper


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_EVIDENCE_DIR = os.path.join(SCRIPT_DIR, "sample synsets with  dictionary evidenc")
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "generated_prompts")
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "prompt_template.md")
ALGORITHM_PATH = os.path.join(SCRIPT_DIR, "draft_api.md")
OUTPUT_SCHEMA_PATH = os.path.join(SCRIPT_DIR, "output_step0.yaml")


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_evidence(path: str) -> dict:
    """Load raw evidence YAML."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def preprocess_evidence(data: dict) -> str:
    """Preprocess evidence dict, return compact YAML string."""
    compacted = preprocess(data)
    return yaml.dump(
        compacted,
        Dumper=ArabicDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=200,
    )


def extract_synset_info(data: dict) -> str:
    """Extract synset summary from evidence data as a readable YAML block."""
    synset = data.get("synset", {})
    info = {
        "id": synset.get("id", ""),
        "ili": synset.get("ili", ""),
        "pos": synset.get("pos", ""),
        "lemmas": synset.get("lemmas", []),
        "definition_ar": synset.get("definition_ar", ""),
    }
    oewn = synset.get("oewn", {})
    if oewn:
        info["definition_en"] = oewn.get("definition_en", "")
        info["lemmas_en"] = oewn.get("lemmas_en", [])
    chain = synset.get("hypernym_chain", {})
    if chain and chain.get("path"):
        parent = chain["path"][0]
        info["direct_hypernym"] = {
            "id": parent.get("id", ""),
            "lemmas": parent.get("lemmas", []),
            "definition_ar": parent.get("definition_ar", ""),
        }
    return yaml.dump(
        info,
        Dumper=ArabicDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=200,
    )


def extract_synset_id(filename: str) -> str:
    """Extract synset ID from filename like 'awn4-13927849-n.evidence.yaml'."""
    return filename.replace(".evidence.yaml", "")


def assemble_prompt(template: str, algorithm: str, output_schema: str, synset_info: str, evidence: str) -> str:
    """Replace injection slots in template."""
    result = template.replace("{{SYNSET_INFO}}", synset_info)
    result = result.replace("{{ALGORITHM}}", algorithm)
    result = result.replace("{{OUTPUT_SCHEMA}}", output_schema)
    result = result.replace("{{EVIDENCE_DATA}}", evidence)
    return result


def main():
    parser = argparse.ArgumentParser(description="Assemble review prompts for all evidence files")
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR, help="Directory with .evidence.yaml files")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for assembled prompts")
    args = parser.parse_args()

    # Load static components
    template = load_text(TEMPLATE_PATH)
    algorithm = load_text(ALGORITHM_PATH)
    output_schema = load_text(OUTPUT_SCHEMA_PATH)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Find all evidence files
    evidence_files = sorted(
        f for f in os.listdir(args.evidence_dir) if f.endswith(".evidence.yaml")
    )

    if not evidence_files:
        print(f"No .evidence.yaml files found in {args.evidence_dir}")
        sys.exit(1)

    print(f"Found {len(evidence_files)} evidence files")
    print(f"Output directory: {args.output_dir}")
    print()

    for filename in evidence_files:
        synset_id = extract_synset_id(filename)
        evidence_path = os.path.join(args.evidence_dir, filename)
        output_path = os.path.join(args.output_dir, f"{synset_id}.prompt.md")

        # Load and extract synset info + preprocess evidence
        raw_data = load_evidence(evidence_path)
        synset_info = extract_synset_info(raw_data)
        compact_evidence = preprocess_evidence(raw_data)
        evidence_lines = compact_evidence.count("\n")

        # Assemble
        prompt = assemble_prompt(template, algorithm, output_schema, synset_info, compact_evidence)
        prompt_lines = prompt.count("\n")

        # Write
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        print(f"  {synset_id}: evidence {evidence_lines} lines → prompt {prompt_lines} lines")

    print(f"\nDone. {len(evidence_files)} prompts written to {args.output_dir}/")


if __name__ == "__main__":
    main()
