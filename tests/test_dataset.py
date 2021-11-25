import argparse

import pytest

from phlorest.dataset import PhlorestDir


@pytest.fixture
def cldfwriter(dataset):
    with dataset.cldf_writer(argparse.Namespace()) as w:
        return w


def test_PhlorestDir(repos):
    d = PhlorestDir(repos / 'raw')
    nex = d.read_nexus('nexus.trees')
    assert nex.trees.trees[0] == d.read_tree(d / 'nexus.trees')
    assert nex.trees.trees[0] != d.read_tree(d / 'nexus.trees', detranslate=True)
    assert d.read_nexus('nexus.trees', remove_rate=True).trees.trees[0] == nex.trees.trees[0]


@pytest.mark.noci
def test_Dataset(dataset, cldfwriter, mocker, glottolog, tmp_path):
    args = argparse.Namespace(
        writer=cldfwriter, glottolog=mocker.Mock(api=glottolog), log=mocker.Mock())
    dataset._cmd_makecldf(args)
    dataset._cmd_readme(args)
