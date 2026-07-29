import pytest

from phlorest.metadata import Metadata


def make_one(**kw):
    d = dict(
        url='http://dx.doi.org/a/b',
        name='the name',
        cldf='github.com/x/y',
        scaling='centuries',
        analysis='other',
        data='data.nex',
        author='the author',
        year='2021')
    d.update(kw)
    return Metadata(**d)


def test_Metadata():
    assert Metadata(id='abc').title == 'Phlorest phylogeny abc'
    md = make_one()
    assert md.url == 'https://doi.org/a/b'
    assert md.common_props()


def test_Metadata_invalid():
    with pytest.raises(ValueError):
        make_one(scaling='x')

    with pytest.raises(ValueError):
        make_one(analysis='x')