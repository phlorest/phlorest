"""
Checks datasets for compliance
"""
import sys
from cldfbench.cli_util import add_dataset_spec, get_dataset

# values in metadata.json that should be present and should not be empty
METAKEYS = [
    'id', 'title', 'license', 'citation', 'name', 'author',
    'scaling', 'analysis', 'family'
]


def register(parser):
    add_dataset_spec(parser)


def run(args):
    try:
        d = get_dataset(args)
    except Exception as e:
        print("Error: unable to load %s - %s" % (args.dataset, e))
        return
        
    # check metadata
    for mdkey in METAKEYS:
        if not getattr(d.metadata, mdkey, ''):
            print("Error: %s metadata missing value for `%s`" % (d.id, mdkey))

    # check title follows required format
    if not getattr(d.metadata, 'title', '').startswith("Phlorest phylogeny derived from"):
        print("Error: %s title does not follow `Phlorest phylogeny derived from`" % d.id)

    # we don't have a summary tree file, and it's not flagged as missing
    if not (d.cldf_dir / 'summary.trees').exists() and not d.metadata.missing.get('summary'):
        print("Error: %s summary tree file missing" % d.id)

    # we don't have a posterior tree file, and it's not flagged as missing
    if not (d.cldf_dir / 'posterior.trees').exists() and not d.metadata.missing.get('posterior'):
        print("Error: %s posterior tree file missing" % d.id)

    # we don't have a nexus data file, and it's not flagged as missing
    if not (d.cldf_dir / 'data.nex').exists() and not d.metadata.missing.get('nexus'):
        print("Error: %s nexus data file missing" % d.id)
        
    # do we have characters?
    if not d.characters and not d.metadata.missing.get('characters'):
        print("Error: %s characters.csv file missing" % d.id)
    
    # check characters has the right columns
    for char in d.characters:
        if 'concepticonReference' in char:
            print("Error: %s characters.csv uses `concepticonReference` rather than `Concepticon_ID`" % d.id)
            break
    
    # is the cldf valid?
    d.cldf_reader().validate()
