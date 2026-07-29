"""
Create release instructions for a dataset.

These instructions use the `gh` tool to manipulate the associated GitHub repository.
"""
import argparse

from cldfbench.cli_util import add_dataset_spec, get_dataset


def register(parser: argparse.ArgumentParser):  # pylint: disable=C0116
    add_dataset_spec(parser)
    parser.add_argument('tag')


def run(args: argparse.Namespace):  # pragma: no cover  # pylint: disable=C0116
    tag = args.tag
    if not tag.startswith('v'):
        tag = 'v' + tag
    ds = get_dataset(args)
    props = ds.cldf_reader().properties
    ds.dir.joinpath('relnotes.txt').write_text(
        f"Cite the source as\n\n> {props['dc:bibliographicCitation']}\n\n"
        f"and the Phlorest phylogeny as\n\nDOI",
        encoding='utf8')
    print(f'gh release create {tag} --title "{props["dc:title"]}" --notes-file relnotes.txt')
    print('')
    print("Now you should submit the deposit to the phlorest community and\n"
          "grab the Zenodo version DOI from\n"
          f"https://zenodo.org/account/settings/github/repository/phlorest/{props['rdf:ID']}\n"
          "and add it to\n"
          f"https://github.com/phlorest/{props['rdf:ID']}/releases/edit/{tag}\n"
          f"and the concept DOI under the key 'zenodo_concept_doi' to "
          "metdata.json")
