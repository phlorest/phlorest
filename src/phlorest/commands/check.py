"""
Checks datasets for compliance
"""
from cldfbench.cli_util import add_dataset_spec, get_dataset

# values in metadata.json that should be present and should not be empty
METAKEYS = [
    'id', 'title', 'license', 'citation', 'name', 'author',
    'scaling', 'analysis', 'family'
]
# FIXME: maybe get these from phlorest.Metadata?


def register(parser):  # pragma: no cover
    add_dataset_spec(parser)


def run(args, d=None):
    if d is None:  # pragma: no cover
        try:
            d = get_dataset(args)
        except Exception as e:
            args.log.error("Unable to load %s - %s" % (args.dataset, e))
            raise

    def check(condition, msg):
        if condition:
            args.log.warning('{0.id}: {1}'.format(d, msg))

    # check metadata
    for mdkey in METAKEYS:
        check(
            not getattr(d.metadata, mdkey, ''),
            "metadata missing value for `%s`" % mdkey)

    check(
        not (d.raw_dir / 'source.bib').exists(),
        "raw/source.bib file missing")

    check(
        not getattr(d.metadata, 'title', '').startswith("Phlorest phylogeny derived from"),
        "title does not follow `Phlorest phylogeny derived from`")

    check(
        not (d.cldf_dir / 'summary.trees').exists() and not d.metadata.missing.get('summary'),
        "summary tree file missing")

    check(
        not (d.cldf_dir / 'posterior.trees').exists() and not d.metadata.missing.get('posterior'),
        "posterior tree file missing")

    check(
        not (d.cldf_dir / 'data.nex').exists() and not d.metadata.missing.get('nexus'),
        "nexus data file missing")

    check(
        not d.characters and not d.metadata.missing.get('characters'),
        "characters.csv file missing")
    
    check(
        any('concepticonReference' in char for char in d.characters),
        "characters.csv uses `concepticonReference` rather than `Concepticon_ID`")

    # check that characters are coded if possible
    if d.characters and not d.metadata.missing.get('concepticon'):
        check(
            all(char.get('Concepticon_ID', "") == "" for char in d.characters),
            "characters.csv file missing concepticon coding")

    check(
        (d.dir / 'Makefile').exists(),
        "has an unneeded Makefile")

    # is the cldf valid?
    d.cldf_reader().validate()
