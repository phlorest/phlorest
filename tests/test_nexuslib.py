import pytest
import newick
import nexus
from nexus.handlers.tree import Tree

from phlorest.nexuslib import NexusFile, newick2nexus, rescale_to_years


def test_rescale_to_years():
    nex = nexus.NexusWriter()
    nex.trees.append(Tree('tree t1 = (A:258,B:123)C:254;'))
    res = rescale_to_years(nex, 'millennia')
    assert '258000' in res.trees.trees[0].newick_string

    with pytest.raises(ValueError):
        _ = rescale_to_years(nex, 'millenia')


def test_newick2nexus():
    assert newick2nexus(newick.loads('(A,B)C;')[0], name='X') == 'tree X = (A,B)C;'


def test_NexusFile(tmp_path, mocker):
    with NexusFile(tmp_path / 'test.nex') as nex:
        nex.append(Tree('tree n = (A:1,B:2)root:3;'), 'a', {'A', 'B'}, 'years', mocker.Mock())
        with pytest.raises(ValueError):
            nex.append(Tree('tree n = (A:1,B:2)root:3;'), 'c', {'A', 'B'}, 'change', mocker.Mock())
    res = nexus.NexusReader.from_file(tmp_path / 'test.nex')
    assert res.trees.ntrees == 1
