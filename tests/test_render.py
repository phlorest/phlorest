import collections

import pytest
from pycldf import Dataset
from nexus.handlers.tree import Tree

from phlorest.render import add_glottolog_links, render_tree, render_summary_tree


def test_add_glottolog_links(tmp_path, repos):
    add_glottolog_links(
        repos / 'summary_tree.svg',
        collections.defaultdict(lambda: (None, 'The Name')),
        tmp_path / 'test.svg')
    assert 'The Name' in tmp_path.joinpath('test.svg').read_text(encoding='utf8')


@pytest.mark.noci
def test_render(tmp_path):
    render_tree(
        Tree('tree n = (A:500,B:500.7):700;').newick_tree,
        tmp_path / 'test.svg',
        gcodes={'A': ('x', 'y'), 'B': ('x', '')},
        scaling='years',
        legend='The Legend',
    )
    assert tmp_path.joinpath('test.svg').exists()


@pytest.mark.noci
def test_render_summary_tree(repos, tmp_path):
    render_summary_tree(
        Dataset.from_metadata(repos / 'cldf' / 'Generic-metadata.json'),
        tmp_path / 'test.svg',
    )
    assert tmp_path.joinpath('test.svg').exists()
