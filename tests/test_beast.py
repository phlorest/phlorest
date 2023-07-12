from phlorest import BeastFile


def test_BeastFile_1(dataset):
    bf = BeastFile(None, text=dataset.raw_dir.read('beast2.xml.gz'))
    nex = bf.nexus()
    matrix = nex.characters.get_matrix()
    assert list(matrix['A'])[135] == 'again-62'  # check one
    assert sorted(nex.taxa) == ['A', 'B', 'C']
    assert len(matrix['A']) == 235


def test_BeastFile_2(dataset):
    bf = BeastFile(None, text=dataset.raw_dir.read('beast.xml'))
    nex = bf.nexus()
    matrix = nex.characters.get_matrix()
    assert nex.taxa == ['Jeju', 'SouthJeolla', 'NorthJeolla']
    assert len(matrix['Jeju']) == 384
    assert list(matrix['Jeju'])[1] == '2'  # no character labels
