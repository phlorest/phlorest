"""
Checks datasets for compliance
"""
from cldfbench.cli_util import add_dataset_spec, get_dataset

# values in metadata.json that should be present and should not be empty
METAKEYS = [
    'id', 'title', 'license', 'citation', 'name', 'author',
    'scaling', 'analysis', 'family'
]


def register(parser):  # pragma: no cover
    add_dataset_spec(parser)


def run(args, d=None):
    if d is None:  # pragma: no cover
        try:
            d = get_dataset(args)
        except Exception as e:
            args.log.error("Unable to load %s - %s" % (args.dataset, e))
            return

    # check metadata
    for mdkey in METAKEYS:
        if not getattr(d.metadata, mdkey, ''):
            args.log.warning("%s metadata missing value for `%s`" % (d.id, mdkey))

    # check title follows required format
    if not getattr(d.metadata, 'title', '').startswith("Phlorest phylogeny derived from"):
        args.log.warning("%s title does not follow `Phlorest phylogeny derived from`" % d.id)

    # we don't have a summary tree file, and it's not flagged as missing
    if not (d.cldf_dir / 'summary.trees').exists() and not d.metadata.missing.get('summary'):
        args.log.warning("%s summary tree file missing" % d.id)

    # we don't have a posterior tree file, and it's not flagged as missing
    if not (d.cldf_dir / 'posterior.trees').exists() and not d.metadata.missing.get('posterior'):
        args.log.warning("%s posterior tree file missing" % d.id)

    # we don't have a nexus data file, and it's not flagged as missing
    if not (d.cldf_dir / 'data.nex').exists() and not d.metadata.missing.get('nexus'):
        args.log.warning("%s nexus data file missing" % d.id)
        
    # do we have characters?
    if not d.characters and not d.metadata.missing.get('characters'):
        args.log.warning("%s characters.csv file missing" % d.id)
    
    # check characters has the right columns
    for char in d.characters:
        if 'concepticonReference' in char:
            args.log.warning("%s characters.csv uses `concepticonReference` rather than `Concepticon_ID`" % d.id)
            break
    
    # check for unneeded Makefile
    if (d.dir / 'Makefile').exists():
        args.log.warning("%s has an unneeded Makefile" % d.id)
    
    # is the cldf valid?
    d.cldf_reader().validate()
