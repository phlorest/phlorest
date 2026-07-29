"""
Generates content for CONTRIBUTORS.md from raw/sources.bib
"""
import argparse
from typing import Optional

from clldutils.clilib import Table, add_format
from cldfbench.cli_util import add_dataset_spec

from phlorest.dataset import Dataset
from phlorest.cli_util import get_dataset


def register(parser):  # pragma: no cover  # pylint: disable=C0116
    add_dataset_spec(parser)
    add_format(parser, 'pipe')


def person_to_str(p):  # inverse of pybtex's str()
    """Format name of a person."""
    von_last = ' '.join(p.prelast_names + p.last_names)
    jr = ' '.join(p.lineage_names)
    first = ' '.join(p.first_names + p.middle_names)
    return ' '.join(part for part in (first, jr, von_last) if part)


def run(args: argparse.Namespace, d: Optional[Dataset] = None):  # pylint: disable=C0116
    if d is None:  # pragma: no cover
        d = get_dataset(args)

    with Table(args, 'Name', 'GitHub user', 'Description', 'Role') as t:
        # assume first source is this dataset
        for author in d.raw_dir.read_bib()[0].entry.persons['author']:
            t.append([person_to_str(author), '', 'author', 'Author'])
