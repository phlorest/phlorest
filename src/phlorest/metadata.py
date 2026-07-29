"""
Phlorest-specific dataset metadata handling.
"""
import collections
import urllib.parse
import dataclasses
from typing import Literal, Any, Optional, get_args

import cldfbench

__all__ = ['SCALING', 'RESCALE_TO_YEARS', 'Metadata', 'YearMultiplesType', 'ScalingType']

ScalingType = Literal[
    'none',  # no branch lengths
    'change',  # parsimony steps
    'arbitrary',  # meaningless -- arbitrary
    'substitutions',  # change
    'years',  # years
    'centuries',  # centuries
    'millennia',  # millennia
]
SCALING = list(get_args(ScalingType))
AnalysesType = Literal[
    'bayesian',
    'parsimony',
    'likelihood',
    'distance',
    'network',
    'supertree',
    'other',
    'none',  # override.
]
ANALYSES = list(get_args(AnalysesType))
YearMultiplesType = Literal['centuries', 'millenia']
RESCALE_TO_YEARS = {
    'centuries': 100,
    'millennia': 1000,
}


@dataclasses.dataclass
class Metadata(cldfbench.Metadata):  # pylint: disable=R0902
    """Phlorest-specific metadata of a CLDF dataset."""
    name: Optional[str] = dataclasses.field(default=None, metadata={"required": True})
    author: Optional[str] = dataclasses.field(default=None, metadata={"required": True})
    year: Optional[str] = None
    scaling: ScalingType = dataclasses.field(default='none', metadata={"required": True})
    analysis: AnalysesType = dataclasses.field(default='none', metadata={"required": True})
    family: Optional[str] = dataclasses.field(default=None, metadata={"required": True})
    cldf: Optional[str] = None
    data: Optional[str] = None
    artefacts: Optional[list] = None
    missing: dict = dataclasses.field(default_factory=dict)
    zenodo_concept_doi: Optional[str] = None

    def __post_init__(self):
        # Call a parent __post_init__ should a future cldfbench add one.
        parent_post_init = getattr(super(), '__post_init__', None)
        if parent_post_init:  # pragma: no cover
            parent_post_init()

        if self.scaling not in SCALING:
            raise ValueError(f"'scaling' must be one of {SCALING} (got {self.scaling})")
        if self.analysis not in ANALYSES:
            raise ValueError(f"'analysis' must be one of {ANALYSES} (got {self.analysis})")

        if self.cldf and self.cldf.startswith('github.com'):
            self.cldf = f'https://{self.cldf}'

        if self.url:
            u = urllib.parse.urlparse(self.url)
            if u.netloc == 'dx.doi.org':
                self.url = urllib.parse.urlunsplit(('https', 'doi.org', u.path, '', ''))

        ref = self.author or ''
        if self.year:
            ref += f' {self.year}'
        if self.name:
            ref += f" '{self.name.strip()}'"
        if ref:
            ref = f'derived from {ref}'
        else:
            ref = self.id
        self.title = f"Phlorest phylogeny {ref}"

    def common_props(self):
        res: dict[str, Any] = cldfbench.Metadata.common_props(self)
        res['dc:subject'] = collections.OrderedDict()
        for k in ['family', 'analysis', 'scaling']:
            v = getattr(self, k)
            if v:
                res['dc:subject'][k] = v
        data = self.cldf or self.data
        if data:
            res['prov:wasDerivedFrom'] = [{
                "rdf:about": data,
                "rdf:type": "prov:Entity",
                "dc:description": "Dataset underlying the analysis"
            }]
        return res

    @property
    def text_description(self) -> str:
        """Metadata formatted in human-readable way."""
        res = 'A [Phlorest phylogeny](https://github.com/phlorest)'
        if self.family:
            if self.family == 'Multiple':  # pragma: no cover
                res += ' of multiple language families'
            else:
                res += f' of the {self.family} language family'
        if self.analysis and self.analysis != 'none':
            res += f' computed from a {self.analysis} analysis'
        if self.scaling and self.scaling != 'none':
            res += f' scaled by {self.scaling}'
        return res + '.'
