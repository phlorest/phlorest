"""

"""
from cldfbench.cli_util import add_dataset_spec, get_dataset


def register(parser):
    add_dataset_spec(parser)
    parser.add_argument('tag')


def run(args):  # pragma: no cover
    tag = args.tag
    if not tag.startswith('v'):
        tag = 'v' + tag
    ds = get_dataset(args)
    cldf = ds.cldf_reader()
    ds.dir.joinpath('relnotes.txt').write_text(
        """\
Cite the source as

> {}

and the Phlorest phylogeny as

DOI""".format(cldf.properties['dc:bibliographicCitation']),
        encoding='utf8')
    print('gh release create {} --title "{}" --notes-file relnotes.txt'.format(
        tag, cldf.properties['dc:title']))
    print('')
    print("Now you should submit the deposit to the phlorest community and\n"
          "grab the Zenodo version DOI from\n"
          "https://zenodo.org/account/settings/github/repository/phlorest/{0}\n"
          "and add it to\n"
          "https://github.com/phlorest/{0}/releases/edit/{1}\n and the concept DOI "
          "under the key 'zenodo_concept_doi' to "
          "metdata.json".format(cldf.properties['rdf:ID'], tag))
