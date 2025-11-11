import gzip
import bz2
import shlex
import shutil
import random
import typing
import pathlib
import subprocess

import cldfbench
from cldfbench.datadir import DataDir
from pyglottolog.languoids import Glottocode
from clldutils.path import TemporaryDirectory, ensure_cmd
from pycldf.trees import TreeTable
from cldfviz.tree import render
from commonnexus import Nexus
from commonnexus.tools.normalise import normalise as nexus_norm

from .nexuslib import Tree
from .metadata import Metadata
from .cldfwriter import CLDFWriter


class PhlorestDir(DataDir):
    """
    Enhanced `DataDir`, adding methods to access phylogenetic data.
    """
    def read_nexus(self,
                   path: typing.Optional[typing.Union[str, pathlib.Path]] = None,
                   text: typing.Optional[str] = None,
                   encoding: str = 'utf-8-sig',
                   normalise: bool = False,
                   preprocessor: typing.Callable[[str], str] = lambda s: s) -> Nexus:
        """
        :param path: path to nexus file (or `None`).
        :param text: text content of a nexus file.
        :return: Initialized `Nexus` object.
        """
        assert (path or text) and not (path and text), 'Must pass either path or text'
        if path:
            path = self._path(path)
            if path.suffix == '.gz':
                with gzip.open(path, 'rt', encoding='utf8') as fp:
                    text = fp.read()
            if path.suffix == '.bz2':
                with bz2.open(path, 'rt', encoding='utf8') as fp:
                    text = fp.read()
        res = Nexus(preprocessor(text or self.read(path, encoding=encoding)))
        return nexus_norm(res) if normalise else res

    def read_trees(self,
                   path: typing.Union[str, pathlib.Path] = None,
                   text: str = None,
                   detranslate: bool = False,
                   burnin: int = 0,
                   sample: int = 0,
                   strip_annotation: bool = False,
                   seed=12345,
                   preprocessor: typing.Callable[[str], str] = lambda s: s) -> typing.List[Tree]:
        """
        Reads trees from `path` and transforms them as required.

        Processing order:
            burnin -> sample -> strip_annotation -> remove_rate -> detranslate

        :param path: path to nexus file.
        :param text: nexus content in text.
        :param detranslate: return trees with translate blocks removed (default=False).
        :param burnin: number of trees to remove as burn-in (default=none).
        :param sample: number of trees to sample (default=all).
        :param remove_rate: remove extra rate information.
        :param strip_annotation: remove comments and annotations in trees (default=False).
        :param preprocessor: function to preprocess nexus text.
        :return:
        """
        nex = self.read_nexus(path=path, text=text, preprocessor=preprocessor)
        trees = nex.TREES.trees
        # remove burn-in first
        if burnin:
            trees = trees[burnin:]
        # ..then sample if needed
        if sample and len(trees) > sample:
            random.seed(seed)
            trees = random.sample(trees, sample)

        trees = [Tree(tree.name, tree.newick, tree.rooted) for tree in trees]
        # ...then detranslate.
        if detranslate:
            # We must use a reference to the same block in order to make the translation-mapping
            # caching work.
            cmd = nex.TREES.translate
            for tree in trees:
                tree.newick = cmd(tree.newick)

        # remove comments if asked
        if strip_annotation:
            for tree in trees:
                tree.newick.strip_comments()

        return trees

    def read_tree(self,
                  path: typing.Union[str, pathlib.Path] = None,
                  text: str = None,
                  detranslate: bool = False,
                  burnin: int = 0,
                  sample: int = 0,
                  remove_rate: bool = False,
                  strip_annotation: bool = False,
                  seed=12345,
                  preprocessor=lambda s: s) -> Tree:
        return self.read_trees(
            path=path,
            text=text,
            detranslate=detranslate,
            burnin=burnin,
            sample=sample,
            strip_annotation=strip_annotation,
            seed=seed,
            preprocessor=preprocessor)[0]


class Dataset(cldfbench.Dataset):
    """
    An augmented `cldfbench.Dataset`

    - swapping in `PhlorestDir` as `DataDir` implementation for `raw`
    - swapping in a custom CLDFWriter implementation `phorest.cldfwriter.CLDFWriter`
    - adding methods to be called in implementations of `cmd_makecldf` for simpler manipulation of \
      phylogenetic data,
    - enhancing README.md by adding an SVG plot of the summary tree.
    """
    metadata_cls = Metadata
    datadir_cls = PhlorestDir

    def __init__(self):
        cldfbench.Dataset.__init__(self)
        self._lids = set()

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return cldfbench.CLDFSpec(dir=self.cldf_dir, writer_cls=CLDFWriter)

    def cmd_download(self, args):  # pragma: no cover
        pass

    def _cmd_makecldf(self, args):
        if self.metadata.family and Glottocode.pattern.match(self.metadata.family):
            glang = args.glottolog.api.languoid(self.metadata.family)
            self.metadata.family = '{} [{}]'.format(glang.name, glang.id)
        cldfbench.Dataset._cmd_makecldf(self, args)

        cldf = self.cldf_reader()
        for tree in TreeTable(cldf):
            if tree.tree_type == 'summary':
                legend = "Summary tree"
                if cldf.properties.get('dc:subject', {}).get('analysis'):
                    title = cldf.properties['dc:subject']['analysis'].title()
                    legend += ' of a {} analysis'.format(title)
                if cldf.properties.get('dc:subject', {}).get('family'):
                    family = cldf.properties['dc:subject']['family']
                    legend += ' of the {} family'.format(family)
                if tree.tree_branch_length_unit:
                    legend += ' with branches in {}'.format(tree.tree_branch_length_unit)

                return render(
                    tree,
                    output=self.dir / 'summary_tree.svg',
                    glottolog_mapping={
                        r['ID']: (r['Glottocode'], r.get('Glottolog_Name'))
                        for r in cldf['LanguageTable'] if r['Glottocode']},
                    legend=legend,
                    width=1000,
                    with_glottolog_links=True
                )

    def init(self, args):
        """
        Create rows in LanguageTable according to `etc/taxa.csv` and add sources from
        `raw/sources.bib`.
        """
        args.writer.add_taxa(self.taxa, args.glottolog.api, args.log)
        if self.raw_dir.joinpath('sources.bib').exists():
            args.writer.cldf.sources.add(
                self.raw_dir.joinpath('sources.bib').read_text(encoding='utf8'))

    def _cmd_readme(self, args):
        cldfbench.Dataset._cmd_readme(self, args)
        text = self.dir.joinpath('README.md').read_text(encoding='utf8')
        text = text.replace('Available online', 'Source available online')
        pre, header, post = text.partition('## Description')
        text = pre + header + '\n\n' + self.metadata.text_description + post

        lines = []
        for line in text.split('\n'):
            lines.append(line)
            if line.startswith('[![CLDF validation]') and self.metadata.zenodo_concept_doi:
                lines.append(
                    '[![DOI](https://zenodo.org/badge/DOI/{0}.svg)](https://doi.org/{0})'.format(
                        self.metadata.zenodo_concept_doi))  # pragma: no cover
        text = '\n'.join(lines)

        if self.dir.joinpath('summary_tree.svg').exists():
            text += \
                "\n## Summary Tree\n\n![summary]({0}{1}/main/summary_tree.svg)\n\n" \
                "[Summary tree visualized with IcyTree]" \
                "(https://icytree.org/?url={0}{1}/refs/heads/main/cldf/summary.trees)\n".format(
                    'https://raw.githubusercontent.com/phlorest/', self.id)
        self.dir.joinpath('README.md').write_text(text, encoding='utf8')
        print('gh repo edit --description "{}" --add-topic "phylogeny"'.format(self.metadata.title))
        if self.metadata.family:
            print('gh repo edit --add-topic "language-family-{}"'.format(
                self.metadata.family.lower().replace(' ', '')))
        if self.metadata.url:  # pragma: no cover
            print('gh repo edit --homepage "{}"'.format(self.metadata.url))

    def _read_from_etc(self, name):
        if (self.etc_dir / name).exists():
            return list(self.etc_dir.read_csv(name, dicts=True))
        return []

    @property
    def taxa(self) -> typing.List[dict]:
        return self._read_from_etc('taxa.csv')

    @property
    def characters(self) -> typing.List[dict]:
        return self._read_from_etc('characters.csv')

    @staticmethod
    def run_treeannotator(cmd, input: typing.Union[str, pathlib.Path]) -> Nexus:
        with TemporaryDirectory() as d:
            in_ = d / 'in.nex'
            if isinstance(input, str):
                in_.write_text(input, encoding='utf8')
            else:
                shutil.copy(input, in_)
            out = d / 'out.nex'
            subprocess.check_call(
                [ensure_cmd('treeannotator')] + shlex.split(cmd) + [str(in_), str(out)],
                stderr=subprocess.DEVNULL,
            )
            return Nexus(out.read_text(encoding='utf8'))

    @staticmethod
    def run_rscript(script, output_fname):
        with TemporaryDirectory() as d:
            d.joinpath('script.r').write_text(script, encoding='utf8')
            subprocess.check_call([ensure_cmd('Rscript'), str(d / 'script.r')], cwd=d)
            return d.joinpath(output_fname).read_text(encoding='utf8')
