"""
Functionality to write trees to Nexus files in a standardized way.
"""
import copy
import logging
import pathlib
import zipfile
import functools
import dataclasses
from typing import Optional, Union

import newick
from commonnexus import Nexus
from commonnexus.blocks import Trees

from .metadata import RESCALE_TO_YEARS, YearMultiplesType

__all__ = ['NexusFile', 'Tree', 'rescale_to_years', 'norm_taxon_name']

PathType = Union[str, pathlib.Path]
TreeType = Union['Tree', str, newick.Node]


def norm_taxon_name(s: Optional[str]) -> Optional[str]:
    """
    Normalize a taxon name to make it suitable as identifier.
    """
    return s.replace('-', '_') if s else s


def norm_taxon_name_visitor(n: newick.Node):
    """
    Normalize a node name.
    """
    n.name = norm_taxon_name(n.name)


def rescale_to_years(nex: Nexus, orig_scaling: YearMultiplesType, **_) -> Nexus:
    """
    Rescales trees in a nexus file to years (if possible).

    :param nex:
    :param orig_scaling:
    :param log:
    :return: The mutated `Nexus` object.
    """
    def _rescaler(factor: Union[int, float], n: newick.Node):
        n._length_formatter = lambda lg: f'{lg:.0f}' if lg else None  # pylint: disable=W0212
        if n._length:  # pylint: disable=W0212
            n.length = n.length * factor

    if orig_scaling not in RESCALE_TO_YEARS:
        raise ValueError(f'Cannot rescale {orig_scaling} to years')
    year_multiple = RESCALE_TO_YEARS[orig_scaling]
    trees = []
    for tree in nex.TREES.trees:
        nwk = tree.newick
        nwk.visit(functools.partial(_rescaler, year_multiple))
        trees.append((tree.name, nwk, tree.rooted))
    kwarg = nex.TREES.TRANSLATE.mappings if nex.TREES.TRANSLATE else {}
    kwarg.update(lowercase_command=True)
    nex.replace_block(nex.TREES, Trees.from_data(*trees, **kwarg))
    return nex


@dataclasses.dataclass
class Tree:
    """Data of a tree relevant for serializing as TREE command in Nexus."""
    name: str
    newick: Union[str, newick.Node]
    rooted: Optional[bool] = None

    def __str__(self):
        return self.newick if isinstance(self.newick, str) else f'{self.newick.newick};'


class NexusFile:
    """A Nexus file as context manager, which will write to disk on exit."""
    def __init__(self, path: PathType, zipped: bool = False):
        self.path = path
        self._trees = []
        self.scaling = None
        self.zipped = zipped

    def _get_tree(self, tree, tid, rooted) -> tuple[newick.Node, str, Optional[bool]]:
        if isinstance(tree, Tree):
            tid = tid or tree.name
            rooted = rooted or tree.rooted
            tree = tree.newick
        if isinstance(tree, str):
            tree = newick.loads(tree)[0]
        assert isinstance(tree, newick.Node)
        return tree, tid, rooted

    def append(self,  # pylint: disable=R0917,R0913
               tree: Union[Tree, str, newick.Node],
               tid: str,
               lids: Union[list[str], set[str]],
               scaling,
               log: logging.Logger,
               rooted: Optional[bool] = None):
        """Add a tree."""
        tree, tid, rooted = self._get_tree(tree, tid, rooted)
        tree.visit(norm_taxon_name_visitor)

        with_lids = bool(lids)
        if with_lids:
            lids = copy.copy(lids)
        for node in tree.walk():
            if node.name == 'root':
                continue
            if node.is_leaf:
                assert node.name
            if node.name and with_lids:
                try:
                    lids.remove(node.name)
                except (ValueError, KeyError):  # set.remove may raise KeyError!
                    if node.is_leaf:
                        log.error('%s references undefined leaf %s', tree.name, node.name)
                    else:  # pragma: no cover
                        log.warning('%s references undefined inner node %s', tree.name, node.name)

        if with_lids and lids:
            log.warning('extra taxa specified in LanguageTable: %s', lids)

        if self.scaling:
            if scaling != self.scaling:
                raise ValueError('All trees in a NexusFile must have the same scaling!')
        else:  # First appended tree determines the scaling.
            self.scaling = scaling
        self._trees.append((tid, tree, rooted))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._trees:
            nex = Nexus.from_blocks(Trees.from_data(*self._trees, lowercase_command=True))
            nex.to_file(self.path)
            if self.zipped:
                with zipfile.ZipFile(
                    self.path.parent / (self.path.name + '.zip'),
                    'w',
                    compression=zipfile.ZIP_DEFLATED
                ) as zf:
                    zf.write(self.path, self.path.name)
                self.path.unlink()
