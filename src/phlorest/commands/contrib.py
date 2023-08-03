"""
Generates CONTRIBUTORS.md from raw/sources.bib
"""
from cldfbench.cli_util import add_dataset_spec, get_dataset


def register(parser):  # pragma: no cover
    add_dataset_spec(parser)


def person_to_str(p):  # inverse of pybtex's str()
    von_last = ' '.join(p.prelast_names + p.last_names)
    jr = ' '.join(p.lineage_names)
    first = ' '.join(p.first_names + p.middle_names)
    return ' '.join(part for part in (first, jr, von_last) if part)


def run(args, d=None):
    if d is None:  # pragma: no cover
        try:
            d = get_dataset(args)
        except Exception as e:
            args.log.error("Unable to load %s - %s" % (args.dataset, e))
            raise

    # assume first source is this dataset
    print("%-30s| GitHub user | Description | Role" % 'Name')
    print("%-30s| ----------- | ----------- | ----" % ('-' * 30))
    for author in d.raw_dir.read_bib()[0].entry.persons['author']:
        print("%-30s|             | author      | Author" % person_to_str(author))
