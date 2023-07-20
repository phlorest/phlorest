import pytest

from commonnexus import Nexus

from phlorest.nexuslib import NexusFile, rescale_to_years, Tree


def test_rescale_to_years():
    nex = Nexus("""#NEXUS
begin trees;
tree t1 = (A:258,B:123)C:254;
end;""")
    res = rescale_to_years(nex, 'millennia')
    assert '258000' in res.TREES.TREE.newick_string

    with pytest.raises(ValueError):
        _ = rescale_to_years(nex, 'millenia')


def test_NexusFile(tmp_path, mocker):
    with NexusFile(tmp_path / 'test.nex') as nex:
        nex.append(Tree('n', '(A:1,B:2)root:3;', None), 'a', {'A', 'B'}, 'years', mocker.Mock())
        with pytest.raises(ValueError):
            nex.append(Tree('n', '(A:1,B:2)root:3;', None), 'c', {'A', 'B'}, 'change', mocker.Mock())
    res = Nexus.from_file(tmp_path / 'test.nex')
    assert len(res.TREES.trees) == 1


def test_Tree():
    t = Tree('n', '(A:1,B:2)root:3;', None)
    assert str(t) == '(A:1,B:2)root:3;'
