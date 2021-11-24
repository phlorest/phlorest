import copy
import functools

import nexus
from nexus.handlers.tree import Tree as NexusTree

from .metadata import RESCALE_TO_YEARS


def format_tree(tree: NexusTree, default_label='tree', newick=None, name=None):
    rooting = '' if tree.rooted is None else '[&{}] '.format('R' if tree.rooted else 'U')
    return 'tree {} = {}{}'.format(
        name or tree.name or default_label, rooting, newick or tree.newick_string)


class NexusFile:
    def __init__(self, path):
        self.path = path
        self._trees = []
        self.scaling = None

    def append(self, tree: NexusTree, tid, lids, scaling, log):
        def _rescaler(factor, n):
            n._length_formatter = lambda l: '{:.0f}'.format(l) if l else None
            if n._length:
                n.length = n.length * factor

        rescale = lambda s: s  # noqa: E731
        if scaling in RESCALE_TO_YEARS:
            rescale = functools.partial(_rescaler, RESCALE_TO_YEARS[scaling])
            scaling = 'years'

        with_lids = bool(lids)
        if with_lids:
            lids = copy.copy(lids)
        ntree = tree.newick_tree
        for node in ntree.walk():
            rescale(node)
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
                    else:
                        log.warning(
                            '{} references undefined inner node {}'.format(tree.name, node.name))

        if with_lids and lids:
            log.warning('extra taxa specified in LanguageTable: {}'.format(lids))

        if self.scaling:
            if scaling != self.scaling:
                raise ValueError('All trees in a NexusFile must have the same scaling!')
        else:
            self.scaling = scaling
        self._trees.append(NexusTree(format_tree(tree, newick=ntree.newick + ';', name=tid)))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        nex = nexus.NexusWriter()
        for i, tree in enumerate(self._trees, start=1):
            nex.trees.append(format_tree(tree, default_label='tree{}'.format(i)))
        nex.write_to_file(self.path)
