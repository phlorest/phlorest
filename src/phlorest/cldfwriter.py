import typing

import cldfbench

import tqdm
import nexus
from nexus.handlers.tree import Tree as NexusTree
from pycldf.terms import TERMS

from .metadata import SCALING, Metadata
from .nexuslib import NexusFile
from .beast import BeastFile


class CLDFWriter(cldfbench.CLDFWriter):
    def __enter__(self):
        self._lids = set()
        self.summary = NexusFile(self.cldf_spec.dir / 'summary.trees')
        self.summary.__enter__()
        self.posterior = NexusFile(self.cldf_spec.dir / 'posterior.trees')
        self.posterior.__enter__()
        res = cldfbench.CLDFWriter.__enter__(self)
        self.add_schema()
        return res

    def __exit__(self, *args):
        self.summary.__exit__(*args)
        self.posterior.__exit__(*args)
        return cldfbench.CLDFWriter.__exit__(self, *args)

    def add_schema(self):
        t = self.cldf.add_component('LanguageTable')
        t.common_props['dc:description'] = \
            "The LanguageTable lists the taxa, i.e. the leafs of the phylogeny, mapped to " \
            "languoids."
        self.cldf.add_table(
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

    def add_columns(self, table, obj, log, exclude=None):
        existing = [c.name for c in self.cldf[table].tableSchema.columns]
        exclude = exclude or []
        new = []
        for k in obj.keys():
            lname = 'concepticonReference' if k == 'Concepticon_ID' else k
            if k not in exclude:
                col = TERMS[lname].to_column() if lname in TERMS else k
                if getattr(col, 'name', k) in existing:
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

    def add_tree(self,
                 tree: NexusTree,
                 nex: NexusFile,
                 tid: str,
                 metadata: Metadata,
                 log,
                 type_,
                 source=None):
        nex.append(tree, tid, self._lids, metadata.scaling, log)
        if source is None:
            bibkeys = list(self.cldf.sources.keys())
            if len(bibkeys) == 1:
                source = bibkeys[0]

        self.objects['trees.csv'].append(dict(
            ID=tid,
            Name=tree.name,
            Nexus_File=nex.path.name,
            rooted=tree.rooted,
            type=type_,
            method=metadata.analysis,
            scaling=nex.scaling,
            Source=[source] if isinstance(source, str) else source,
        ))

    def add_summary(self,
                    tree: NexusTree,
                    metadata: Metadata,
                    log,
                    source=None):
        self.add_tree(tree, self.summary, 'summary', metadata, log, 'summary', source=source)

    def add_posterior(self,
                      trees: typing.List[NexusTree],
                      metadata: Metadata,
                      log,
                      source=None,
                      verbose=False):
        for i, tree in (
                tqdm.tqdm(enumerate(trees, start=1), total=len(trees))
                if verbose else enumerate(trees, start=1)):
            self.add_tree(
                tree,
                self.posterior,
                'posterior-{}'.format(i),
                metadata,
                log,
                'sample',
                source=source)

    def add_data(self, input, characters, log):
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

        md = {int(row.pop('Site')): row for row in characters}
        assert all(len(chars) == len(d) for d in nex.data.matrix.values()), str(len(chars))
        t = self.cldf.add_component(
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
            self.add_columns(
                'ParameterTable', list(md.values())[0], log, exclude=['Label'])
        self.cldf['ParameterTable', 'ID'].common_props['dc:description'] = \
            "Sequence index of the site in the corresponding Nexus file."
        for site, label in chars:
            d = dict(ID=site, Name=label, Nexus_File='data.nex')
            self.add_obj('ParameterTable', d, md.get(site, {}), rename=dict(Label='Name'))
        assert all(t in self._lids for t in nex.data.taxa)
        assert all(t in self._lids for t in nex.data.matrix)
        nex.write_to_file(self.cldf_spec.dir / 'data.nex')
        self.cldf.add_provenance(
            wasDerivedFrom={
                "rdf:about": "data.nex",
                "rdf:type": "prov:Entity",
                'dc:description': 'The data underlying the analysis which created the phylogeny',
                'dc:format': 'https://en.wikipedia.org/wiki/Nexus_file',
            }
        )

    def add_taxa(self, taxa, glottolog, log):
        glangs = {lg.id: lg for lg in glottolog.languoids()}
        #
        # FIXME: add metadata from Glottolog, put in dplace-tree-specific Dataset base class.
        # FIXME: log warnings if taxa are mapped to bookkeeping languoids!
        #
        for i, row in enumerate(taxa):
            if i == 0:
                self.add_columns(
                    'LanguageTable',
                    row,
                    log,
                    exclude=['taxon', 'glottocode', 'soc_ids', 'xd_ids'])
                self.cldf.add_columns('LanguageTable', 'Glottolog_Name')
            self._lids.add(row['taxon'])
            glang = None
            if row['glottocode']:
                try:
                    glang = glangs[row['glottocode']]
                except KeyError:
                    log.error('Invalid glottocode in taxa.csv: {}'.format(row['glottocode']))
            d = dict(
                ID=row['taxon'],
                Name=row['taxon'],
                Glottocode=row['glottocode'] or None,
                Glottolog_Name=glang.name if glang else None,
                Latitude=glang.latitude if glang else None,
                Longitude=glang.longitude if glang else None,
            )
            self.add_obj('LanguageTable', d, row)
