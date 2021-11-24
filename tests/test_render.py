import collections

from phlorest.render import add_glottolog_links


def test_add_glottolog_links(tmp_path, repos):
    add_glottolog_links(
        repos / 'summary_tree.svg',
        collections.defaultdict(lambda: (None, 'The Name')),
        tmp_path / 'test.svg')
    assert 'The Name' in tmp_path.joinpath('test.svg').read_text(encoding='utf8')
