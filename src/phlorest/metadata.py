import collections
import urllib.parse
import dataclasses

import cldfbench

__all__ = ['SCALING', 'RESCALE_TO_YEARS', 'Metadata']

SCALING = [
    'none',  # no branch lengths
    'change',  # parsimony steps
    'arbitrary',  # meaningless -- arbitrary
    'substitutions',  # change
    'years',  # years
    'centuries',  # centuries
    'millennia',  # millennia
]
ANALYSES = [
    'bayesian',
    'parsimony',
    'likelihood',
    'distance',
    'network',
    'supertree',
    'other',
    'none',  # override.
]
RESCALE_TO_YEARS = {
    'centuries': 100,
    'millennia': 1000,
}


@dataclasses.dataclass
class Metadata(cldfbench.Metadata):
    name: str = dataclasses.field(default=None, metadata=dict(required=True))
    author: str = dataclasses.field(default=None, metadata=dict(required=True))
    year: str = None
    scaling: str = dataclasses.field(default='none', metadata=dict(required=True))
    analysis: str = dataclasses.field(default='none', metadata=dict(required=True))
    family: str = dataclasses.field(default=None, metadata=dict(required=True))
    cldf: str = None
    data: str = None
    artefacts: list = None
    missing: dict = dataclasses.field(default_factory=dict)
    zenodo_concept_doi: str = None

    def __post_init__(self):
        # Call a parent __post_init__ should a future cldfbench add one.
        parent_post_init = getattr(super(), '__post_init__', None)
        if parent_post_init:  # pragma: no cover
            parent_post_init()

        # Formerly attrs validators on the `scaling` and `analysis` fields.
        if self.scaling not in SCALING:
            raise ValueError(
                "'scaling' must be one of {} (got {!r})".format(SCALING, self.scaling))
        if self.analysis not in ANALYSES:
            raise ValueError(
                "'analysis' must be one of {} (got {!r})".format(ANALYSES, self.analysis))

        # Formerly an attrs converter on the `cldf` field.
        if self.cldf and self.cldf.startswith('github.com'):
            self.cldf = 'https://{}'.format(self.cldf)

        if self.url:
            u = urllib.parse.urlparse(self.url)
            if u.netloc == 'dx.doi.org':
                self.url = urllib.parse.urlunsplit(('https', 'doi.org', u.path, '', ''))

        ref = self.author or ''
        if self.year:
            ref += ' {}'.format(self.year)
        if self.name:
            ref += " '{}'".format(self.name.strip())
        if ref:
            ref = 'derived from {}'.format(ref)
        else:
            ref = self.id
        self.title = "Phlorest phylogeny {}".format(ref)

    def common_props(self):
        res = cldfbench.Metadata.common_props(self)
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
    def text_description(self):
        res = 'A [Phlorest phylogeny](https://github.com/phlorest)'
        if self.family:
            if self.family == 'Multiple':  # pragma: no cover
                res += ' of multiple language families'
            else:
                res += ' of the {} language family'.format(self.family)
        if self.analysis and self.analysis != 'none':
            res += ' computed from a {} analysis'.format(self.analysis)
        if self.scaling and self.scaling != 'none':
            res += ' scaled by {}'.format(self.scaling)
        return res + '.'
