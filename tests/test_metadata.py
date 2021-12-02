from phlorest.metadata import Metadata


def test_Metadata():
    assert Metadata(id='abc').title == 'Phlorest phylogeny abc'
    md = Metadata(
        url='http://dx.doi.org/a/b',
        name='the name',
        scaling='centuries',
        analysis='other',
        data='data.nex',
        author='the author',
        year='2021')
    assert md.url == 'https://doi.org/a/b'
    assert md.common_props()
