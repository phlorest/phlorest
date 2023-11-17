import copy
import typing
import zipfile
import functools
import dataclasses

import newick
from commonnexus import Nexus
from commonnexus.blocks import Trees

from .metadata import RESCALE_TO_YEARS

__all__ = ['NexusFile', 'Tree', 'rescale_to_years', 'norm_taxon_name']


def norm_taxon_name(s):
    return s.replace('-', '_') if s else s


def rescale_to_years(nex: Nexus, orig_scaling, log=None) -> Nexus:
    """
    Rescales trees in a nexus file to years (if possible).

    :param nex:
    :param orig_scaling:
    :param log:
    :return: The mutated `Nexus` object.
    """
    def _rescaler(factor, n):
        n._length_formatter = lambda lg: '{:.0f}'.format(lg) if lg else None
        if n._length:
            n.length = n.length * factor

    if orig_scaling in RESCALE_TO_YEARS:
        trees = []
        for tree in nex.TREES.trees:
            nwk = tree.newick
            nwk.visit(functools.partial(_rescaler, RESCALE_TO_YEARS[orig_scaling]))
            trees.append((tree.name, nwk, tree.rooted))
        kwarg = nex.TREES.TRANSLATE.mappings if nex.TREES.TRANSLATE else {}
        kwarg.update(lowercase_command=True)
        nex.replace_block(nex.TREES, Trees.from_data(*trees, **kwarg))
        return nex
    raise ValueError('Cannot rescale {} to years.'.format(orig_scaling))


@dataclasses.dataclass
class Tree:
    name: str
    newick: typing.Union[str, newick.Node]
    rooted: typing.Optional[bool] = None

    def __str__(self):
        return self.newick if isinstance(self.newick, str) else '{};'.format(self.newick.newick)


class NexusFile:
    def __init__(self, path, zipped=False):
        self.path = path
        self._trees = []
        self.scaling = None
        self.zipped = zipped

    def append(self,
               tree: typing.Union[Tree, str, newick.Node],
               tid: str,
               lids: typing.List[str],
               scaling,
               log,
               rooted: typing.Optional[bool] = None):
        if isinstance(tree, Tree):
            tid = tid or tree.name
            rooted = rooted or tree.rooted
            tree = tree.newick
        if isinstance(tree, str):
            tree = newick.loads(tree)[0]

        def norm(n):
            n.name = norm_taxon_name(n.name)
        tree.visit(norm)

        with_lids = bool(lids)
        if with_lids:
            lids = copy.copy(lids)
        for node in tree.walk():
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
        self._trees.append((tid, tree, rooted))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._trees:
            nex = Nexus.from_blocks(
                Trees.from_data(*self._trees, **dict(lowercase_command=True)))
            nex.to_file(self.path)
            if self.zipped:
                with zipfile.ZipFile(
                    self.path.parent / (self.path.name + '.zip'),
                    'w',
                    compression=zipfile.ZIP_DEFLATED
                ) as zf:
                    zf.write(self.path, self.path.name)
                self.path.unlink()
