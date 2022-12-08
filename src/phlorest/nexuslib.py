import copy
import typing
import zipfile
import functools

import newick
import nexus
from nexus.handlers.tree import Tree as NexusTree
from nexus.tools import visit_tree_nodes

from .metadata import RESCALE_TO_YEARS

__all__ = ['newick2nexus', 'NexusFile']


def newick2nexus(tree: typing.Union[str, newick.Node], name='tree') -> NexusTree:
    tree = getattr(tree, 'newick', tree)
    if not tree.endswith(';'):
        tree += ';'
    return NexusTree('tree {} = {}'.format(name, tree))


def rescale_to_years(nex, orig_scaling, log=None):
    """
    Rescales trees in a nexus file to years (if possible) in the fashion of other `nexus.tools`
    tree manipulation functions.

    :param nex:
    :param orig_scaling:
    :param log:
    :return: The mutated `NexusReader` object.
    """
    def _rescaler(factor, n):
        n._length_formatter = lambda l: '{:.0f}'.format(l) if l else None
        if n._length:
            n.length = n.length * factor

    if orig_scaling in RESCALE_TO_YEARS:
        return visit_tree_nodes(nex, functools.partial(_rescaler, RESCALE_TO_YEARS[orig_scaling]))
    raise ValueError('Cannot rescale {} to years.'.format(orig_scaling))


class NexusFile:
    def __init__(self, path, zipped=False):
        self.path = path
        self._trees = []
        self.scaling = None
        self.zipped = zipped

    def append(self, tree: NexusTree, tid, lids, scaling, log):
        with_lids = bool(lids)
        if with_lids:
            lids = copy.copy(lids)
        ntree = tree.newick_tree
        for node in ntree.walk():
            if node.name == 'root':
                continue
            if node.is_leaf:
                assert node.name
            if node.name:
                try:
                    if with_lids:
                        lids.remove(node.name)
                except KeyError:
                    if node.is_leaf:
                        log.error('{} references undefined leaf {}'.format(tree.name, node.name))
                    else:  # pragma: no cover
                        log.warning(
                            '{} references undefined inner node {}'.format(tree.name, node.name))

        if with_lids and lids:
            log.warning('extra taxa specified in LanguageTable: {}'.format(lids))

        if self.scaling:
            if scaling != self.scaling:
                raise ValueError('All trees in a NexusFile must have the same scaling!')
        else:
            self.scaling = scaling
        self._trees.append(NexusTree.from_newick(ntree, name=tid or tree.name, rooted=tree.rooted))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._trees:
            nex = nexus.NexusWriter()
            for i, tree in enumerate(self._trees, start=1):
                nex.trees.append(NexusTree.from_newick(
                    tree.newick_string, name=tree.name or 'tree{}'.format(i), rooted=tree.rooted))
            nex.write_to_file(self.path)
            if self.zipped:
                with zipfile.ZipFile(
                    self.path.parent / (self.path.name + '.zip'),
                    'w',
                    compression=zipfile.ZIP_DEFLATED
                ) as zf:
                    zf.write(self.path, self.path.name)
                self.path.unlink()
