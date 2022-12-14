import shutil
import pathlib

import pytest
from nexus.handlers.tree import Tree
from pyglottolog import Glottolog


@pytest.fixture
def repos():
    return pathlib.Path(__file__).parent / 'repos'


@pytest.fixture
def nexus_tree():
    return Tree('tree name = (A:45.5,B:34.7):56.5;')


@pytest.fixture
def glottolog():
    return Glottolog(pathlib.Path(__file__).parent / 'glottolog')


@pytest.fixture
def tmp_repos(repos, tmp_path):
    shutil.copytree(repos, tmp_path / 'repos')
    return tmp_path / 'repos'


@pytest.fixture
def dataset(tmp_repos):
    from phlorest import Dataset

    class DS(Dataset):
        dir = tmp_repos
        id = 'phy'

        def cmd_makecldf(self, args):
            self.init(args)
            args.writer.add_summary(
                self.raw_dir.read_tree('nexus.trees'),
                self.metadata,
                args.log
            )

    return DS()
