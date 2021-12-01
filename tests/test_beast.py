import pytest

from phlorest import BeastFile


@pytest.mark.slow
def test_BeastFile(dataset):
    bf = BeastFile(None, text=dataset.raw_dir.read('beast2.xml.gz'))
    nex, chars = bf.nexus_and_characters()
    assert len(chars) == 18438
