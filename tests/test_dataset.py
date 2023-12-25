import shutil
import argparse

import pytest

from phlorest.dataset import PhlorestDir


@pytest.fixture
def cldfwriter(dataset):
    with dataset.cldf_writer(argparse.Namespace()) as w:
        return w


def test_PhlorestDir(repos):
    d = PhlorestDir(repos / 'raw')
    nex = d.read_nexus('nexus.trees', preprocessor=lambda s: s.replace('Cojubim', 'abcdefg'))
    assert 'abcdefg' in str(nex)

    nex = d.read_nexus('nexus.trees.gz')
    assert nex.TREES.TREE

    nex = d.read_nexus('nexus.trees.bz2')
    assert nex.TREES.TREE


def test_PhlorestDir_with_rates(repos):
    d = PhlorestDir(repos / 'raw')
    nex = d.read_nexus('trees_with_rate.trees')
    for node in nex.TREES.TREE.newick.walk():
        if node.name == '1':
            assert ('height' in node.properties) and ('rate' in node.properties)


@pytest.mark.noci
def test_Dataset(dataset, cldfwriter, mocker, glottolog, tmp_path):
    assert dataset.metadata.title == "Phlorest phylogeny derived from the author 2021 'The name'"
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
    res = dataset.run_treeannotator('cmd', dataset.raw_dir / 'nexus.trees')
    assert res.TREES


def test_Dataset_run_rscript(dataset, mocker):
    def rscript(args, **kw):
        kw['cwd'].joinpath('res.txt').write_text('hello', encoding='utf8')

    mocker.patch('phlorest.dataset.subprocess', mocker.Mock(check_call=rscript))
    res = dataset.run_rscript('', 'res.txt')
    assert res == 'hello'


def test_PhlorestDir_read_trees(dataset):
    tfile = dataset.raw_dir / 'posterior.trees'
    # no args
    assert len(dataset.raw_dir.read_trees(tfile)) == 3
    
    # sample
    assert len(dataset.raw_dir.read_trees(tfile, sample=2)) == 2
    
    # burnin
    trees = dataset.raw_dir.read_trees(tfile, burnin=2)
    assert len(trees) == 1
    assert 'TREE3' == trees[0].name

    trees = dataset.raw_dir.read_trees(tfile, burnin=1)
    assert len(trees) == 2
    assert 'TREE2' == trees[0].name
    assert 'TREE3' == trees[1].name
    
    # strip_annotation
    trees = dataset.raw_dir.read_trees(tfile, burnin=2, strip_annotation=True)
    assert len(trees) == 1
    assert 'TREE3' == trees[0].name
    assert '[' not in trees[0].newick.newick

    # preprocessor
    trees = dataset.raw_dir.read_trees(
        tfile,
        burnin=2,
        preprocessor=lambda t: t.replace("tree TREE", "tree TESTTREE")
    )
    assert len(trees) == 1
    assert 'TESTTREE3' == trees[0].name
    
    # detranslate
    trees = dataset.raw_dir.read_trees(tfile, burnin=2, detranslate=True)
    assert len(trees) == 1
    assert 'Cojubim' in trees[0].newick.newick
    
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
    assert 'TREE1' != trees[0].name, 'Tree1 should never be sampled due to burn-in setting'
    assert '[' not in trees[0].newick.newick
    assert 'Cojubim' in trees[0].newick.newick
