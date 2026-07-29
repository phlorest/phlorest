"""
A phlorest-specific cldfbench.Dataset implementation.
"""
import bz2
import gzip
import shlex
import shutil
import random
import argparse
import subprocess
from typing import Optional, Callable, Union

import cldfbench
from cldfbench.datadir import DataDir
from pyglottolog.languoids import Glottocode
from clldutils.path import TemporaryDirectory, ensure_cmd
from pycldf.trees import TreeTable
from cldfviz.tree import render
from commonnexus import Nexus
from commonnexus.tools.normalise import normalise as nexus_norm

from .nexuslib import Tree, PathType
from .metadata import Metadata
from .cldfwriter import CLDFWriter

CsvRowType = dict[str, str]


class PhlorestDir(DataDir):
    """
    Enhanced `DataDir`, adding methods to access phylogenetic data.
    """
    def read_nexus(
            self,
            path: Optional[PathType] = None,
            text: Optional[str] = None,
            encoding: str = 'utf-8-sig',
            normalise: bool = False,
            preprocessor: Callable[[str], str] = lambda s: s,
    ) -> Nexus:
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

    def read_trees(  # pylint: disable=R0913,R0917
            self,
            path: Optional[PathType] = None,
            text: Optional[str] = None,
            detranslate: bool = False,
            burnin: int = 0,
            sample: int = 0,
            strip_annotation: bool = False,
            seed: int = 12345,
            preprocessor: Callable[[str], str] = lambda s: s,
    ) -> list[Tree]:
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

    def read_tree(  # pylint: disable=R0913,R0917
            self,
            path: Optional[PathType] = None,
            text: Optional[str] = None,
            detranslate: bool = False,
            burnin: int = 0,
            sample: int = 0,
            strip_annotation: bool = False,
            seed: int = 12345,
            preprocessor: Callable[[str], str] = lambda s: s,
    ) -> Tree:
        """Read the first tree."""
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

    def cldf_specs(self) -> cldfbench.CLDFSpec:
        """Phlorest phylogenies typically just contain one CLDF dataset."""
        return cldfbench.CLDFSpec(dir=self.cldf_dir, writer_cls=CLDFWriter)

    def cmd_download(self, args: argparse.Namespace):  # pragma: no cover
        """Overwrite the behaviour of cldfbench.Dataset.cmd_download."""

    def _cmd_makecldf(self, args: argparse.Namespace) -> Optional[PathType]:
        """
        Writes a summary tree to the dataset's directory after regular CLDF creation.
        """
        if self.metadata.family and Glottocode.pattern.match(self.metadata.family):
            glang = args.glottolog.api.languoid(self.metadata.family)
            self.metadata.family = f'{glang.name} [{glang.id}]'
        # Call default CLDF creation.
        cldfbench.Dataset._cmd_makecldf(self, args)  # pylint: disable=W0212

        cldf = self.cldf_reader()
        for tree in TreeTable(cldf):  # See, if we can find a summary tree.
            if tree.tree_type == 'summary':
                legend = "Summary tree"
                if cldf.properties.get('dc:subject', {}).get('analysis'):
                    title = cldf.properties['dc:subject']['analysis'].title()
                    legend += f' of a {title} analysis'
                if cldf.properties.get('dc:subject', {}).get('family'):
                    family = cldf.properties['dc:subject']['family']
                    legend += f' of the {family} family'
                if tree.tree_branch_length_unit:
                    legend += f' with branches in {tree.tree_branch_length_unit}'

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
        return None  # pragma: no cover

    def init(self, args: argparse.Namespace):
        """
        Create rows in LanguageTable according to `etc/taxa.csv` and add sources from
        `raw/sources.bib`.
        """
        args.writer.add_taxa(self.taxa, args.glottolog.api, args.log)
        if self.raw_dir.joinpath('sources.bib').exists():
            args.writer.cldf.sources.add(
                self.raw_dir.joinpath('sources.bib').read_text(encoding='utf8'))

    def _cmd_readme(self, args: argparse.Namespace):
        """
        Enhance the dataset's README, e.g. by including the summary tree.

        Prints out commands using the `gh` utility to set metadata on the corresponding GitHub repo.
        These must be run by a user with suitable privileges on the repo to take effect.
        """
        cldfbench.Dataset._cmd_readme(self, args)  # pylint: disable=W0212
        text = self.dir.joinpath('README.md').read_text(encoding='utf8')
        text = text.replace('Available online', 'Source available online')
        pre, header, post = text.partition('## Description')
        text = pre + header + '\n\n' + self.metadata.text_description + post

        lines = []
        for line in text.split('\n'):  # pragma: no cover
            lines.append(line)
            if line.startswith('[![CLDF validation]') and self.metadata.zenodo_concept_doi:
                badge_url = f'https://zenodo.org/badge/DOI/{self.metadata.zenodo_concept_doi}.svg'
                doi_url = f'https://doi.org/{self.metadata.zenodo_concept_doi}'
                lines.append(f'[![DOI]({badge_url})]({doi_url})')

        if self.dir.joinpath('summary_tree.svg').exists():
            gh_url = f'https://raw.githubusercontent.com/phlorest/{self.id}'
            lines.extend([
                "\n## Summary Tree\n",
                f"![summary]({gh_url}/main/summary_tree.svg)\n",
                "[Summary tree visualized with IcyTree]"
                f"(https://icytree.org/?url={gh_url}/refs/heads/main/cldf/summary.trees)\n",
            ])

        self.dir.joinpath('README.md').write_text('\n'.join(lines), encoding='utf8')
        print(f'gh repo edit --description "{self.metadata.title}" --add-topic "phylogeny"')
        if self.metadata.family:
            print(f'gh repo edit --add-topic '
                  f'"language-family-{self.metadata.family.lower().replace(" ", "")}"')
        if self.metadata.url:  # pragma: no cover
            print(f'gh repo edit --homepage "{self.metadata.url}"')

    def _read_from_etc(self, name: str) -> list[CsvRowType]:
        if (self.etc_dir / name).exists():
            return list(self.etc_dir.read_csv(name, dicts=True))
        return []

    @property
    def taxa(self) -> list[CsvRowType]:
        """Metadata about taxa in a phylogeny."""
        return self._read_from_etc('taxa.csv')

    @property
    def characters(self) -> list[CsvRowType]:
        """Metadata about characters (aka sites) in a phylogeny."""
        return self._read_from_etc('characters.csv')

    @staticmethod
    def run_treeannotator(cmd: str, input_: Union[str, PathType]) -> Nexus:
        """Run a treeannotator command on the Nexus string or file specified as `input_`."""
        with TemporaryDirectory() as d:
            in_ = d / 'in.nex'
            if isinstance(input_, str):
                in_.write_text(input_, encoding='utf8')
            else:
                shutil.copy(input_, in_)
            out = d / 'out.nex'
            subprocess.check_call(
                [ensure_cmd('treeannotator')] + shlex.split(cmd) + [str(in_), str(out)],
                stderr=subprocess.DEVNULL,
            )
            return Nexus(out.read_text(encoding='utf8'))

    @staticmethod
    def run_rscript(script: str, output_fname: str) -> str:
        """
        Run an R script and return whatever it has written to `output_fname` as string.
        """
        with TemporaryDirectory() as d:
            d.joinpath('script.r').write_text(script, encoding='utf8')
            subprocess.check_call([ensure_cmd('Rscript'), str(d / 'script.r')], cwd=d)
            return d.joinpath(output_fname).read_text(encoding='utf8')
