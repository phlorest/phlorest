"""
Enhanced cldfbench.CLDFWriter
"""
import logging
import pathlib
from typing import Optional, Union, Any
from collections.abc import Iterable, Container

import cldfbench
import tqdm
from pycldf.terms import TERMS
from pycldf.dataset import TableType
from commonnexus import Nexus
from commonnexus.tools.normalise import normalise
from commonnexus.tools.matrix import CharacterMatrix
from commonnexus.blocks.characters import Characters
from pyglottolog import Glottolog

from .beast import BeastFile
from .metadata import Metadata
from .nexuslib import NexusFile, norm_taxon_name, TreeType


class CLDFWriter(cldfbench.CLDFWriter):
    """
    A CLDF writer that knows how to add phylogentic data.
    """
    summary: NexusFile
    posterior: NexusFile
    _lids: set

    def __enter__(self):
        self._lids = set()
        self.summary: NexusFile = NexusFile(self.cldf_spec.dir / 'summary.trees')
        self.summary.__enter__()
        self.posterior: NexusFile = NexusFile(self.cldf_spec.dir / 'posterior.trees', zipped=True)
        self.posterior.__enter__()
        res = cldfbench.CLDFWriter.__enter__(self)
        self.add_schema()
        return res

    def __exit__(self, *args):
        if self.dataset:
            if self.dataset.metadata.cldf:
                self.cldf.add_provenance(
                    wasDerivedFrom={
                        "rdf:about": self.dataset.metadata.cldf,
                        "rdf:type": "prov:Entity",
                        'dc:description': 'The CLDF dataset from which the data underlying the '
                                          'analysis was derived',
                        'dc:format': 'https://cldf.clld.org',
                    }
                )
            if self.dataset.metadata.data and self.dataset.metadata.data.startswith('http'):
                self.cldf.add_provenance(
                    wasDerivedFrom={
                        "rdf:about": self.dataset.metadata.data,
                        "rdf:type": "prov:Entity",
                        'dc:description': 'The dataset from which the data underlying the '
                                          'analysis was derived',
                    }
                )

        self.summary.__exit__(*args)
        self.posterior.__exit__(*args)
        return cldfbench.CLDFWriter.__exit__(self, *args)

    def add_schema(self):
        """Add phlorest-specifies."""
        t = self.cldf.add_component(
            'LanguageTable',
            {
                'name': "xd_ids",
                'separator': ' ',
                'datatype': {'base': 'string', 'format': 'xd[0-9]+'},
                'dc:description':
                    'D-PLACE “cross-data-set” identifier, used to link societies present in '
                    'different datasets, if they share a focal location. Note: If this field is '
                    'empty, other fields such as Name, Glottocode or location may be used to '
                    'identify languoids/societies across datasets if appropriate.',
            },
        )
        t.common_props['dc:description'] = \
            "The LanguageTable lists the taxa, i.e. the leafs of the phylogeny, mapped to " \
            "languoids."
        self.cldf.add_component('TreeTable')
        self.cldf.add_component('MediaTable')

    def add_columns(
            self,
            table: TableType,
            obj: dict[str, Any],
            log: logging.Logger,
            exclude: Optional[Container[str]] = None,
    ):
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
                    log.error('Duplicate column name %s for %s', k, table)
                    continue
                new.append(col)

        self.cldf.add_columns(table, *new)

    def add_obj(
            self,
            table: str,
            d: dict[str, Any],
            row: Optional[dict[str, Any]] = None,
            rename: Optional[dict[str, str]] = None,
    ):
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

    def add_tree(  # pylint: disable=R0913,R0917
            self,
            tree: TreeType,
            nex: NexusFile,
            tid: str,
            metadata: Metadata,
            log: logging.Logger,
            type_: str,
            source: Optional[str] = None,
            rooted: Optional[bool] = None,
    ):
        """Add a tree to a NexusFile and record it in MediaTable and TreeTable."""
        nex.append(tree, tid, self._lids, metadata.scaling, log, rooted=rooted)
        if source is None:
            bibkeys = list(self.cldf.sources.keys())
            if len(bibkeys) == 1:
                source = bibkeys[0]

        # Add media file only if necessary!
        mids = [m['ID'] for m in self.objects['MediaTable']]
        if nex.path.stem not in mids:
            is_summary = nex.path.stem == 'summary'
            self.objects['MediaTable'].append(dict(  # pylint: disable=R1735
                ID=nex.path.stem,
                Media_Type='text/plain',
                Download_URL=f"file:///{nex.path.name}{'' if is_summary else '.zip'}",
                Path_In_Zip=None if is_summary else 'posterior.trees',
            ))

        self.objects['TreeTable'].append(dict(  # pylint: disable=R1735
            ID=tid,
            Name=tid,
            Media_ID=nex.path.stem,
            Tree_Is_Rooted=rooted,
            Tree_Type=type_,
            Description=metadata.analysis,
            Tree_Branch_Length_Unit=None if nex.scaling in {'none', 'arbitrary'} else nex.scaling,
            Source=[source] if isinstance(source, str) else source,
        ))

    def add_summary(
            self,
            tree: TreeType,
            metadata: Metadata,
            log: logging.Logger,
            source: Optional[str] = None,
            rooted: Optional[bool] = None,
    ):
        """
        Add `tree` as summary tree to the dataset.
        """
        self.add_tree(
            tree, self.summary, 'summary', metadata, log, 'summary', source=source, rooted=rooted)
        log.info("added summary tree")

    def add_posterior(  # pylint: disable=R0913,R0917
            self,
            trees: list[TreeType],
            metadata: Metadata,
            log: logging.Logger,
            source: Optional[str] = None,
            verbose: bool = False,
            rooted: Optional[bool] = None,
    ):
        """
        Add `trees` as posterior sample of trees to the dataset.
        """
        i = 0
        for i, tree in (
                tqdm.tqdm(enumerate(trees, start=1), total=len(trees))
                if verbose else enumerate(trees, start=1)):
            self.add_tree(
                tree,
                self.posterior,
                # We use a name format that works with the `tracerer` package for R:
                f'STATE_{i}',
                metadata,
                log,
                'sample',
                source=source,
                rooted=rooted)
        log.info("added posterior trees (n=%d)", i)

    def add_data(
            self,
            input_: Union[BeastFile, pathlib.Path, str, Nexus],
            characters: Iterable[dict[str, str]],
            log,
            binarise: bool = False,
    ):
        """
        Add character data from which the tree(s) in the dataset were computed.

        :param input_: Character data can be read from BEAST files and NEXUS files.
        :param characters: Character metadata, per site.
        :param log:
        """
        if isinstance(input_, BeastFile):
            nex = input_.nexus()
        elif isinstance(input_, pathlib.Path):
            nex = Nexus.from_file(input_)
        elif isinstance(input_, str):
            nex = Nexus(input_)
        else:
            nex = input_
        assert isinstance(nex, Nexus)
        charlabels, _ = nex.characters.get_charstatelabels()

        md = {int(row.pop('Site')): row for row in characters}
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
        for site, label in charlabels.items():
            d = {'ID': site, 'Name': label, 'Nexus_File': 'data'}
            self.add_obj('ParameterTable', d, md.get(site, {}), rename={'Label': 'Name'})
        self.add_obj(
            'MediaTable',
            {'ID': 'data', 'Media_Type': 'text/plain', 'Download_URL': 'file:///data.nex'})

        if binarise:
            _, statelabels = nex.characters.get_charstatelabels()
            new = CharacterMatrix.binarised(nex.characters.get_matrix(), statelabels=statelabels)
            nex.replace_block(nex.characters, Characters.from_data(new))

        nex = normalise(nex, rename_taxa=lambda t: t.replace('-', '_'))
        assert all(t in self._lids for t in nex.taxa), \
            f"Taxa in nexus not in taxa.csv: {[t for t in nex.taxa if t not in self._lids]}"
        nex.to_file(self.cldf_spec.dir / 'data.nex')
        self.cldf.add_provenance(
            wasDerivedFrom={
                "rdf:about": "data.nex",
                "rdf:type": "prov:Entity",
                'dc:description': 'The data underlying the analysis which created the phylogeny',
                'dc:format': 'https://en.wikipedia.org/wiki/Nexus_file',
            }
        )
        log.info("added data nexus (characters=%d)", len(charlabels))

    def add_taxa(
            self,
            taxa: list[dict[str, str]],
            glottolog: Glottolog,
            log: logging.Logger,
    ):
        """Add taxa, i.e. rows of LanguageTable."""
        glangs = {lg.id: lg for lg in glottolog.languoids()}
        #
        # log warnings if taxa are mapped to bookkeeping languoids!?
        #
        for i, row in enumerate(taxa):
            if i == 0:
                self.add_columns(
                    'LanguageTable',
                    row,
                    log,
                    exclude=['taxon', 'glottocode', 'soc_ids', 'xd_ids'])
                self.cldf.add_columns('LanguageTable', 'Glottolog_Name')
            lid = norm_taxon_name(row['taxon'])
            self._lids.add(lid)
            glang = None
            if row['glottocode']:
                try:
                    glang = glangs[row['glottocode']]
                except KeyError:  # pragma: no cover
                    log.error('Invalid glottocode in taxa.csv: %s', row['glottocode'])
            d = dict(  # pylint: disable=R1735
                ID=lid,
                Name=row['taxon'],
                Glottocode=row['glottocode'] or None,
                Glottolog_Name=glang.name if glang else None,
                Latitude=glang.latitude if glang else None,
                Longitude=glang.longitude if glang else None,
                xd_ids=[x.strip() for x in (row.get('xd_ids') or '').split(',') if x.strip()],
            )
            if 'xd_ids' in row:
                del row['xd_ids']
            self.add_obj('LanguageTable', d, row)
        log.info("added taxa (taxa=%d)", len(taxa))
