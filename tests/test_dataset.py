import cldfbench

from phlorest.dataset import CLDFWriter


def test_CLDFWriter(tmp_path):
    with CLDFWriter(cldf_spec=cldfbench.CLDFSpec(dir=tmp_path)) as writer:
        writer.cldf.add_table('test.csv')
        writer.add_columns('test.csv', {'a': 'b'})
        assert writer.cldf['test.csv', 'a']