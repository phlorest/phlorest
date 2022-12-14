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

    nex = d.read_nexus('nexus.trees', preprocessor=lambda s: s.replace('Cojubim', 'abcdefg'))
    assert 'abcdefg' in nex.write()


def test_PhlorestDir_remove_rate(repos):
    d = PhlorestDir(repos / 'raw')
    nex = d.read_nexus('trees_with_rate.trees')
    res = d.remove_rate(nex.trees.trees[0])
    assert '[&rate=0.10061354528306601]' not in res


@pytest.mark.noci
def test_Dataset(dataset, cldfwriter, mocker, glottolog, tmp_path):
    args = argparse.Namespace(
        writer=cldfwriter, glottolog=mocker.Mock(api=glottolog), log=mocker.Mock())
    dataset._cmd_makecldf(args)
    dataset._cmd_readme(args)


def test_Dataset_run_treeannotator(dataset, mocker, repos):
    def annotate(args, **kw):
        shutil.copy(repos / 'raw' / 'nexus.trees', args[-1])

    mocker.patch('phlorest.dataset.ensure_cmd', mocker.Mock(return_value='cmd'))
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


def test_PhlorestDir_read_trees(dataset):
    tfile = dataset.raw_dir / 'posterior.trees'
    # no args
    assert len(dataset.raw_dir.read_trees(tfile, remove_rate=True)) == 3
    
    # sample
    assert len(dataset.raw_dir.read_trees(tfile, sample=2)) == 2
    
    # burnin
    trees = dataset.raw_dir.read_trees(tfile, burnin=2)
    assert len(trees) == 1
    assert 'tree TREE3' in trees[0]

    trees = dataset.raw_dir.read_trees(tfile, burnin=1)
    assert len(trees) == 2
    assert 'tree TREE2' in trees[0]
    assert 'tree TREE3' in trees[1]
    
    # strip_annotation
    trees = dataset.raw_dir.read_trees(tfile, burnin=2, strip_annotation=True)
    assert len(trees) == 1
    assert 'tree TREE3' in trees[0]
    assert '[' not in trees[0]

    # preprocessor
    trees = dataset.raw_dir.read_trees(
        tfile,
        burnin=2,
        preprocessor=lambda t: t.replace("tree TREE", "tree TESTTREE")
    )
    assert len(trees) == 1
    assert 'tree TESTTREE' in trees[0]
    
    # detranslate
    trees = dataset.raw_dir.read_trees(tfile, burnin=2, detranslate=True)
    assert len(trees) == 1
    assert 'Cojubim' in trees[0]
    
    # combined
    trees = dataset.raw_dir.read_trees(
        tfile,
        burnin=1, 
        sample=1,
        preprocessor=lambda t: t.replace("tree TREE", "tree TESTTREE"),
        strip_annotation=True,
        detranslate=True
    )
    assert len(trees) == 1
    assert 'TREE1' not in trees[0], \
        'Tree1 should never be sampled due to burn-in setting'
    assert '[' not in trees[0]
    assert 'Cojubim' in trees[0]

