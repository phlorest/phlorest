import pytest
import newick
import nexus
from nexus.handlers.tree import Tree

from phlorest.nexuslib import NexusFile, newick2nexus


def test_newick2nexus():
    assert newick2nexus(newick.loads('(A,B)C;')[0], name='X') == 'tree X = (A,B)C;'


def test_NexusFile(tmp_path, mocker):
    with NexusFile(tmp_path / 'test.nex') as nex:
        nex.append(Tree('tree n = (A:1,B:2)root:3;'), 'a', {'A', 'B'}, 'centuries', mocker.Mock())
        nex.append(Tree('tree n = (A:1,B:2)root:3;'), 'b', {'A', 'B'}, 'years', mocker.Mock())
        with pytest.raises(ValueError):
            nex.append(Tree('tree n = (A:1,B:2)root:3;'), 'c', {'A', 'B'}, 'change', mocker.Mock())
    res = nexus.NexusReader.from_file(tmp_path / 'test.nex')
    assert res.trees.ntrees == 2
    assert '100' in res.trees.trees[0]
