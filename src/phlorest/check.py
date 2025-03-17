import typing

from pycldf import Dataset as CLDFDataset

import attr
from cldfbench.dataset import dataset_from_module

from phlorest import Dataset, Metadata

# values in metadata.json that should be present and should not be empty
METAKEYS = [a.name for a in attr.fields(Metadata) if a.metadata.get('required')]


def run_checks(d: typing.Union[CLDFDataset, Dataset], log) -> bool:
    """
    Run a couple of Phlorest-specific checks on a dataset.

    To invoke from a dataset's `test.py` module, include

    .. code-block:: python

        def test_phlorest_check(cldf_dataset, cldf_logger):
            from phlorest.check import run_checks
            assert run_checks(cldf_dataset, cldf_logger)

    :return: `True` if all checks passed, `False` otherwise.
    """
    if isinstance(d, CLDFDataset):
        d = dataset_from_module(
            d.directory.joinpath('..', 'cldfbench_{}.py'.format(d.properties['rdf:ID'])))

    success = True

    def check(condition, msg):
        if condition:
            log.warning('{0.id}: {1}'.format(d, msg))
            return False
        return True

    # check metadata
    for mdkey in METAKEYS:
        success &= check(
            not getattr(d.metadata, mdkey, ''),
            "metadata missing value for `%s`" % mdkey)

    success &= check(
        not (d.raw_dir / 'sources.bib').exists(),
        "raw/sources.bib file missing")

    success &= check(
        not (d.dir / 'CONTRIBUTORS.md').exists(),
        "CONTRIBUTORS.md file missing")

    success &= check(
        not ((d.cldf_dir / 'summary.trees').exists() or d.metadata.missing.get('summary')),
        "missing summary tree not declared")

    success &= check(
        not ((d.cldf_dir / 'posterior.trees.zip').exists() or d.metadata.missing.get('posterior')),
        "missing posterior tree not declared")

    success &= check(
        not ((d.cldf_dir / 'data.nex').exists() or d.metadata.missing.get('nexus')),
        "missing nexus data not declared")

    success &= check(
        not (d.characters or d.metadata.missing.get('characters')),
        "missing characters.csv not declared")

    success &= check(
        any('concepticonReference' in char for char in d.characters),
        "characters.csv uses `concepticonReference` rather than `Concepticon_ID`")

    # check that characters are coded if possible
    if d.characters and not d.metadata.missing.get('concepticon'):
        success &= check(
            all(char.get('Concepticon_ID', "") == "" for char in d.characters),
            "characters.csv file missing concepticon coding")

    # check that we have the same number of entries in ./etc/characters.csv and
    # ./cldf/parameters.csv
    if d.characters:
        try:
            nparams = len(d.cldf_dir.read_csv('parameters.csv', dicts=True))
        except FileNotFoundError:
            nparams = 0
        success &= check(
            nparams != len(d.characters), "characters.csv does not match parameters.csv")

    success &= check((d.dir / 'Makefile').exists(), "has a legacy Makefile")
    return success
