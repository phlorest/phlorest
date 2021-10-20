import shutil
import pathlib
import argparse

import pytest
from pyglottolog import Glottolog
from nexus.handlers.tree import Tree

from phlorest import *


@pytest.fixture
def dataset(tmp_path):
    shutil.copytree(pathlib.Path(__file__).parent / 'repos', tmp_path / 'repos')

    class DS(Dataset):
        dir = tmp_path / 'repos'
        id = 'phy'

    return DS()


@pytest.fixture
def glottolog():
    return Glottolog(pathlib.Path(__file__).parent / 'glottolog')


@pytest.fixture
def cldfwriter(dataset):
    with dataset.cldf_writer(argparse.Namespace()) as w:
        return w


def test_Dataset(dataset, cldfwriter, mocker, glottolog, tmp_path):
    args = argparse.Namespace(
        writer=cldfwriter, glottolog=mocker.Mock(api=glottolog), log=mocker.Mock())
    dataset.init(args)
    assert dataset.dir.joinpath('cldf').exists()
    print(dataset._lids)
    dataset.add_tree(
        args, Tree('Tree = [&R] (abcd1235,abcd1235)abcd1234;'), NexusFile(tmp_path / 'nex'), 'x')
    dataset.add_data(args, BeastFile(dataset.raw_dir / 'beast.xml'))
    dataset.run_nexus('trees -c -t', dataset.raw_dir / 'nexus.trees')