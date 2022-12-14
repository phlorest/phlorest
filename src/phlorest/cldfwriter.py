import typing

import cldfbench

import tqdm
import nexus
from nexus.handlers.tree import Tree as NexusTree
from pycldf.terms import TERMS

from .metadata import Metadata
from .nexuslib import NexusFile
from .beast import BeastFile


class CLDFWriter(cldfbench.CLDFWriter):
    """
    A CLDF writer that knows how to add phylogentic data.
    """
    def __enter__(self):
        self._lids = set()
        self.summary = NexusFile(self.cldf_spec.dir / 'summary.trees')
        self.summary.__enter__()
        self.posterior = NexusFile(self.cldf_spec.dir / 'posterior.trees', zipped=True)
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
        self.cldf.add_component('TreeTable')
        self.cldf.add_component('MediaTable')

    def add_columns(self, table, obj, log, exclude=None):
        """
        Wraps `pycldf.Dataset.add_columns`, adding some checking.
        """
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

    def add_obj(self,
                table: str,
                d: dict,
                row: typing.Optional[dict] = None,
                rename: typing.Optional[typing.Dict[str, str]] = None):
        """
        Merge data from `row` into `d` and add the resulting `dict` to table `table`.
        """
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

        # Add media file only if necessary!
        mids = [m['ID'] for m in self.objects['MediaTable']]
        if nex.path.stem not in mids:
            self.objects['MediaTable'].append(dict(
                ID=nex.path.stem,
                Media_Type='text/plain',
                Download_URL='file:///{}{}'.format(
                    nex.path.name, '' if nex.path.stem == 'summary' else '.zip'),
                Path_In_Zip=None if nex.path.stem == 'summary' else 'posterior.trees',
            ))

        self.objects['TreeTable'].append(dict(
            ID=tid,
            Name=tid,
            Media_ID=nex.path.stem,
            Tree_Is_Rooted=tree.rooted,
            Tree_Type=type_,
            Description=metadata.analysis,
            Tree_Branch_Length_Unit=None if nex.scaling == 'none' else nex.scaling,
            Source=[source] if isinstance(source, str) else source,
        ))

    def add_summary(self,
                    tree: NexusTree,
                    metadata: Metadata,
                    log,
                    source=None):
        self.add_tree(tree, self.summary, 'summary', metadata, log, 'summary', source=source)
        log.info("added summary tree")

    def add_posterior(self,
                      trees: typing.List[NexusTree],
                      metadata: Metadata,
                      log,
                      source=None,
                      verbose=False):
        i = 0
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
        log.info("added posterior trees (n=%d)" % i)

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
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#mediaReference',
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
            d = dict(ID=site, Name=label, Nexus_File='data')
            self.add_obj('ParameterTable', d, md.get(site, {}), rename=dict(Label='Name'))
        self.add_obj(
            'MediaTable',
            dict(ID='data', Media_Type='text/plain', Download_URL='file:///data.nex'))

        missing = [t for t in nex.data.taxa if t not in self._lids]
        assert not len(missing), "Taxa in nexus not in taxa.csv: %r" % missing

        missing = [t for t in nex.data.matrix if t not in self._lids]
        assert not len(missing), "Taxa in nexus not in taxa.csv: %r" % missing

        nex.write_to_file(self.cldf_spec.dir / 'data.nex')
        self.cldf.add_provenance(
            wasDerivedFrom={
                "rdf:about": "data.nex",
                "rdf:type": "prov:Entity",
                'dc:description': 'The data underlying the analysis which created the phylogeny',
                'dc:format': 'https://en.wikipedia.org/wiki/Nexus_file',
            }
        )
        log.info("added data nexus (characters=%d)" % len(chars))

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
                except KeyError:  # pragma: no cover
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
        log.info("added taxa (taxa=%d)" % len(taxa))
