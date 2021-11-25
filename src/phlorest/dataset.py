import re
import gzip
import shlex
import random
import shutil
import pathlib
import zipfile
import tempfile
import subprocess

import nexus
import cldfbench

from nexus.handlers.tree import Tree as NexusTree
from nexus.tools import delete_trees, sample_trees, strip_comments_in_trees
from pycldf.terms import TERMS
from pyglottolog.languoids import Glottocode

from .metadata import Metadata, SCALING
from .render import render_summary_tree
from .nexuslib import NexusFile
from .beast import BeastFile


class CLDFWriter(cldfbench.CLDFWriter):
    def add_columns(self, table, obj, exclude=None, log=None):
        existing = [c.name for c in self.cldf[table].tableSchema.columns]
        exclude = exclude or []
        new = []
        for k in obj.keys():
            lname = 'concepticonReference' if k == 'Concepticon_ID' else k
            if k not in exclude:
                col = TERMS[lname].to_column() if lname in TERMS else k
                if getattr(col, 'name', k) in existing:
                    if log:
                        log.error('Duplicate column name {} for {}'.format(k, table))
                    continue
                new.append(col)

        self.cldf.add_columns(table, *new)

    def add_obj(self, table, d, row, rename=None):
        rename = rename or {}
        for k, v in (row or {}).items():
            k = rename.get(k, k)
            if k in TERMS:
                k = TERMS[k].to_column().name
            d[k] = v
        self.objects[table].append(d)


class Dataset(cldfbench.Dataset):
    metadata_cls = Metadata
    __ete3_newick_format__ = 0

    def __init__(self):
        cldfbench.Dataset.__init__(self)
        self._lids = set()

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return cldfbench.CLDFSpec(dir=self.cldf_dir, writer_cls=CLDFWriter)

    def cmd_download(self, args):
        pass

    def _cmd_makecldf(self, args):
        if self.metadata.family and Glottocode.pattern.match(self.metadata.family):
            glang = args.glottolog.api.languoid(self.metadata.family)
            self.metadata.family = '{} [{}]'.format(glang.name, glang.id)
        cldfbench.Dataset._cmd_makecldf(self, args)
        render_summary_tree(
            self.cldf_reader(),
            self.dir / 'summary_tree.svg',
            ete3_format=self.__ete3_newick_format__)

    def _cmd_readme(self, args):
        cldfbench.Dataset._cmd_readme(self, args)
        if self.dir.joinpath('summary_tree.svg').exists():
            text = self.dir.joinpath('README.md').read_text(encoding='utf8')
            text += '\n\n## Summary Tree\n\n![summary](./summary_tree.svg)'
            self.dir.joinpath('README.md').write_text(text, encoding='utf8')

    def read_gzipped_text(self, p, name=None):
        if p.suffix == '.zip':
            zip = zipfile.ZipFile(str(p))
            return zip.read(name or zip.namelist()[0]).decode('utf8')
        with gzip.open(p) as fp:
            return fp.read().decode('utf8')

    def _read_from_etc(self, name):
        if (self.etc_dir / name).exists():
            return list(self.etc_dir.read_csv(name, dicts=True))
        return []

    @property
    def taxa(self):
        return self._read_from_etc('taxa.csv')

    @property
    def characters(self):
        return self._read_from_etc('characters.csv')

    def read_nexus(self, p, remove_rate=False):
        """
        :param p:
        :param remove_rate: Some trees have annotations before *and* after the colon, separating \
        the branch length. The newick package can't handle these. So we can remove the simpler \
        annotation after the ":".
        :return:
        """
        text = p if isinstance(p, str) else p.read_text(encoding='utf8')
        if remove_rate:
            text = re.sub(r':\[&rate=[0-9]*\.?[0-9]*]', ':', text)
        return nexus.NexusReader.from_string(text)

    def read_trees(self, p, detranslate=False):
        nex = nexus.NexusReader(p)
        if detranslate:
            nex.trees.detranslate()
        return nex.trees.trees

    def read_tree(self, p, detranslate=False):
        return self.read_trees(p, detranslate=detranslate)[0]

    def nexus_summary(self):
        return NexusFile(self.cldf_dir / 'summary.trees')

    def nexus_posterior(self):
        return NexusFile(self.cldf_dir / 'posterior.trees')

    def run_treeannotator(self, cmd, input):
        if shutil.which('treeannotator') is None:
            raise ValueError('The treeannotator executable must be installed and in PATH')
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            in_ = d / 'in.nex'
            if isinstance(input, str):
                in_.write_text(input, encoding='utf8')
            else:
                shutil.copy(input, in_)
            out = d / 'out.nex'
            subprocess.check_call(
                ['treeannotator'] + shlex.split(cmd) + [str(in_), str(out)],
                stderr=subprocess.DEVNULL,
            )
            return nexus.NexusReader.from_string(out.read_text(encoding='utf8'))

    def run_rscript(self, script, output_fname):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            d.joinpath('script.r').write_text(script, encoding='utf8')
            subprocess.check_call(['Rscript', str(d / 'script.r')], cwd=d)
            return d.joinpath(output_fname).read_text(encoding='utf8')

    def remove_burnin(self, input, amount):
        return delete_trees(input, list(range(amount + 1))).write()

    def sample(self,
               input,
               seed=12345,
               detranslate=False,
               as_nexus=False,
               n=1000,
               strip_annotation=False):
        random.seed(seed)
        res = sample_trees(input, n)
        if strip_annotation:
            res = strip_comments_in_trees(res)
        if detranslate:
            res.trees.detranslate()
        return res if as_nexus else res.write()

    def init(self, args):
        self.add_schema(args)
        self.add_taxa(args)
        if self.raw_dir.joinpath('source.bib').exists():
            args.writer.cldf.sources.add(
                self.raw_dir.joinpath('source.bib').read_text(encoding='utf8'))

    def add_schema(self, args):
        t = args.writer.cldf.add_component('LanguageTable')
        t.common_props['dc:description'] = \
            "The LanguageTable lists the taxa, i.e. the leafs of the phylogeny, mapped to " \
            "languoids."
        args.writer.cldf.add_table(
            'trees.csv',
            {
                'name': 'ID',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id',
            },
            {
                'name': 'Name',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name',
            },
            {
                'name': 'Nexus_File',
                'dc:description': 'The newick representation of the tree, labeled with identifiers '
                                  'as described in LanguageTable, is stored in the TREES '
                                  'block of the Nexus file specified here. '
                                  '(See https://en.wikipedia.org/wiki/Nexus_file)',
                'propertyUrl': 'http://purl.org/dc/terms/relation',
            },
            {
                'name': 'rooted',  # bool or None
                'datatype': 'boolean',
                'dc:description': "Whether the tree is rooted (true) or unrooted (false) (or no "
                                  "info is available (null))"
            },
            {
                'name': 'type',  # summary or sample
                'datatype': {'base': 'string', 'format': 'summary|sample'},
                'dc:description': "Whether the tree is a summary (or consensus) tree, i.e. can be "
                                  "analysed in isolation, or whether it is a sample, resulting "
                                  "from a method that creates multiple trees",
            },
            {
                'name': 'method',
                'dc:description': 'Specifies the method that was used to create the tree'
            },
            {
                'name': 'scaling',
                'datatype': {'base': 'string', 'format': '|'.join(SCALING)},
            },
            {
                'name': 'Source',
                'separator': ';',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
            },
        )

    def add_tree(self, args, tree, nex, tid, type_=None, source=None):
        nex.append(tree, tid, self._lids, self.metadata.scaling, args.log)
        if type_ is None:
            if nex.path.stem == 'summary':
                type_ = 'summary'
            elif nex.path.stem == 'posterior':
                type_ = 'sample'

        if source is None:
            bibkeys = list(args.writer.cldf.sources.keys())
            if len(bibkeys) == 1:
                source = bibkeys[0]

        args.writer.objects['trees.csv'].append(dict(
            ID=tid,
            Name=tree.name,
            Nexus_File=nex.path.name,
            rooted=tree.rooted,
            type=type_,
            method=self.metadata.analysis,
            scaling=nex.scaling,
            Source=[source] if isinstance(source, str) else source,
        ))

    def add_tree_from_nexus(
            self, args, in_nex, out_nex, tid, type_=None, source=None, detranslate=False):
        if not isinstance(in_nex, nexus.NexusReader):
            in_nex = nexus.NexusReader(in_nex)
        if detranslate:
            in_nex.trees.detranslate()
        self.add_tree(args, in_nex.trees.trees[0], out_nex, tid, type_=type_, source=source)

    def add_tree_from_newick(self, args, nwk, nex, tid, type_=None, source=None):
        if isinstance(nwk, pathlib.Path):
            nwk = nwk.read_text(encoding='utf8')
        self.add_tree(
            args, NexusTree('tree = {}'.format(nwk)), nex, tid, type_=type_, source=source)

    def add_data(self, args, input):
        if isinstance(input, BeastFile):
            nex, chars = input.nexus_and_characters()
        else:
            nex = input if isinstance(input, (nexus.NexusReader, nexus.NexusWriter)) \
                else nexus.NexusReader(input)
            chars = sorted(nex.data.charlabels.items())
        if not chars:
            chars = [
                (i + 1, 'Site {}'.format(i + 1))
                for i, _ in enumerate(list(nex.data.matrix.values())[0])]

        if chars[0][0] == 0:
            # A zero-based index. Switch to 1-based:
            chars = [(k + 1, v) for k, v in chars]

        md = {int(row.pop('Site')): row for row in self.characters}
        assert all(len(chars) == len(d) for d in nex.data.matrix.values()), str(len(chars))
        t = args.writer.cldf.add_component(
            'ParameterTable',
            {
                'name': 'Nexus_File',
                'dc:description':
                    'The data for this parameter is stored at 1-based index {ID} '
                    'of the sequences in the DATA block of the Nexus file specified here. '
                    '(See https://en.wikipedia.org/wiki/Nexus_file)',
                'propertyUrl': 'http://purl.org/dc/terms/relation',
            },
        )
        t.common_props['dc:description'] = \
            "The ParameterTable lists characters (a.k.a. sites), i.e. the (often binary) " \
            "variables used as data basis to compute the phylogeny from."
        if md:
            args.writer.add_columns(
                'ParameterTable', list(md.values())[0], exclude=['Label'], log=args.log)
        args.writer.cldf['ParameterTable', 'ID'].common_props['dc:description'] = \
            "Sequence index of the site in the corresponding Nexus file."
        for site, label in chars:
            d = dict(ID=site, Name=label, Nexus_File='data.nex')
            args.writer.add_obj('ParameterTable', d, md.get(site, {}), rename=dict(Label='Name'))
        assert all(t in self._lids for t in nex.data.taxa)
        assert all(t in self._lids for t in nex.data.matrix)
        nex.write_to_file(self.cldf_dir / 'data.nex')
        args.writer.cldf.add_provenance(
            wasDerivedFrom={
                "rdf:about": "data.nex",
                "rdf:type": "prov:Entity",
                'dc:description': 'The data underlying the analysis which created the phylogeny',
                'dc:format': 'https://en.wikipedia.org/wiki/Nexus_file',
            }
        )

    def add_taxa(self, args):
        glangs = {lg.id: lg for lg in args.glottolog.api.languoids()}
        #
        # FIXME: add metadata from Glottolog, put in dplace-tree-specific Dataset base class.
        # FIXME: log warnings if taxa are mapped to bookkeeping languoids!
        #
        for i, row in enumerate(self.taxa):
            if i == 0:
                args.writer.add_columns(
                    'LanguageTable',
                    row,
                    exclude=['taxon', 'glottocode', 'soc_ids', 'xd_ids'],
                    log=args.log)
                args.writer.cldf.add_columns('LanguageTable', 'Glottolog_Name')
            self._lids.add(row['taxon'])
            glang = None
            if row['glottocode']:
                try:
                    glang = glangs[row['glottocode']]
                except KeyError:
                    args.log.error('Invalid glottocode in taxa.csv: {}'.format(row['glottocode']))
            d = dict(
                ID=row['taxon'],
                Name=row['taxon'],
                Glottocode=row['glottocode'] or None,
                Glottolog_Name=glang.name if glang else None,
                Latitude=glang.latitude if glang else None,
                Longitude=glang.longitude if glang else None,
            )
            args.writer.add_obj('LanguageTable', d, row)
