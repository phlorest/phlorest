import cldfbench

from phlorest.cldfwriter import CLDFWriter
from phlorest.metadata import Metadata
from phlorest.beast import BeastFile


def test_CLDFWriter(repos, tmp_path, mocker, nexus_tree, dataset, glottolog):
    log = mocker.Mock()
    with CLDFWriter(cldf_spec=cldfbench.CLDFSpec(dir=tmp_path)) as writer:
        writer.add_taxa(dataset.taxa, glottolog, mocker.Mock())
        writer.cldf.add_table('test.csv', 'a')
        writer.add_columns('test.csv', {'a': 'b', 'c': 3}, log=log)
        assert log.error.called
        assert writer.cldf['test.csv', 'a']
        writer.add_summary(
            nexus_tree,
            Metadata(name='n', author='a', year=2021),
            mocker.Mock())
        writer.add_posterior(
            [nexus_tree],
            Metadata(name='n', author='a', year=2021),
            mocker.Mock())
        writer.add_data(BeastFile(repos / 'raw' / 'beast.xml'), [], mocker.Mock())
