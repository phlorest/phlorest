import shutil
import argparse

import nexus
from nexus.tools.util import get_nexus_reader
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


def test_Dataset_run_treeannotator(dataset, mocker, repos):
    mocker.patch(
        'phlorest.dataset.shutil', mocker.Mock(which=mocker.Mock(return_value=None)))
    with pytest.raises(ValueError):
        dataset.run_treeannotator('', '')

    def annotate(args, **kw):
        shutil.copy(repos / 'raw' / 'nexus.trees', args[-1])

    mocker.patch('phlorest.dataset.shutil', mocker.Mock())
    mocker.patch('phlorest.dataset.subprocess', mocker.Mock(check_call=annotate))
    _ = dataset.run_treeannotator('cmd', 'in')
    res = dataset.run_treeannotator('cmd', get_nexus_reader(dataset.raw_dir / 'nexus.trees'))
    assert isinstance(res, nexus.NexusReader)


def test_Dataset_run_rscript(dataset, mocker):
    def rscript(args, **kw):
        kw['cwd'].joinpath('res.txt').write_text('hello', encoding='utf8')

    mocker.patch('phlorest.dataset.subprocess', mocker.Mock(check_call=rscript))
    res = dataset.run_rscript('', 'res.txt')
    assert res == 'hello'


def test_Dataset_remove_burnin(dataset):
    assert dataset.remove_burnin(
        dataset.raw_dir / 'nexus.trees', 0, as_nexus=True).trees.ntrees == 1


def test_Dataset_sample(dataset):
    res = dataset.sample(
        dataset.raw_dir / 'nexus.trees', n=1, strip_annotation=True, detranslate=True)
    assert res