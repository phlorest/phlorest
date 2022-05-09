from phlorest import BeastFile

def test_BeastFile(dataset):
    bf = BeastFile(None, text=dataset.raw_dir.read('beast2.xml.gz'))
    nex, chars = bf.nexus_and_characters()
    assert chars[135] == (136, 'again-62')  # check one
    assert sorted(nex.data.taxa) == sorted(['A', 'B', 'C'])
    assert len(chars) == nex.data.nchar == 235
