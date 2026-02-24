import xml.etree.ElementTree as ET
import csv
import random
import os
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
AWN4_BASE = SCRIPT_DIR.parent.parent
source_xml = str(AWN4_BASE / "output" / "awn4.xml")
output_csv = str(SCRIPT_DIR / "sample_for_review.csv")
sample_size = 100

def get_synset_data(xml_file):
    """
    Parses the XML and yields synset data.
    Since the file is large, we can iterate or just parse if memory allows. 
    Given it's ~70MB, standard parsing is fine for this environment.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Namespace handling usually needed if distinct, but ElementTree handles simple cases well.
    # We need to map lemma IDs to their written forms first.
    
    lexicon = root.find('Lexicon')
    
    # 1. Build Lemma Map: EntryID -> WrittenForm
    # We also need to map SenseID -> SynsetID to know which lemmas belong to which synset.
    
    synset_to_lemmas = {} # SynsetID -> list of lemmas
    
    print("Mapping entries...")
    for entry in lexicon.findall('LexicalEntry'):
        lemma = entry.find('Lemma').get('writtenForm')
        for sense in entry.findall('Sense'):
            synset_id = sense.get('synset')
            if synset_id not in synset_to_lemmas:
                synset_to_lemmas[synset_id] = []
            synset_to_lemmas[synset_id].append(lemma)
            
    # 2. Collect Synsets
    print("Collecting synsets...")
    all_synsets = []
    for synset in lexicon.findall('Synset'):
        sid = synset.get('id')
        pos = synset.get('partOfSpeech')
        
        definition = synset.find('Definition')
        definition_text = definition.text if definition is not None else ""
        
        examples = [ex.text for ex in synset.findall('Example')]
        
        lemmas = synset_to_lemmas.get(sid, [])
        
        all_synsets.append({
            'id': sid,
            'pos': pos,
            'lemmas': "، ".join(lemmas),
            'definition': definition_text,
            'examples': " | ".join(examples)
        })
        
    return all_synsets

def main():
    if not os.path.exists(source_xml):
        print(f"Error: Could not find {source_xml}")
        return

    data = get_synset_data(source_xml)
    
    # Select random sample
    sample = random.sample(data, min(sample_size, len(data)))
    
    # Write to CSV
    print(f"Writing {len(sample)} entries to {output_csv}...")
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Synset ID', 'POS', 'Arabic Lemmas', 'Definition', 'Examples', 'Linguist Rating (1-5)', 'Comments'])
        
        for row in sample:
            writer.writerow([
                row['id'],
                row['pos'],
                row['lemmas'],
                row['definition'],
                row['examples'],
                '', '' # Empty columns for linguist
            ])
    
    print("Done.")

if __name__ == "__main__":
    main()
