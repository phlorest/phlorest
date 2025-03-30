import collections
import urllib.parse

import attr
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
    'network',
    'supertree',
    'other',
    'none',  # override.
]
RESCALE_TO_YEARS = {
    'centuries': 100,
    'millennia': 1000,
}


@attr.s
class Metadata(cldfbench.Metadata):
    name = attr.ib(default=None, metadata=dict(required=True))
    author = attr.ib(default=None, metadata=dict(required=True))
    year = attr.ib(default=None)
    scaling = attr.ib(
        default='none',
        validator=attr.validators.in_(SCALING),
        metadata=dict(required=True))
    analysis = attr.ib(
        default='none',
        validator=attr.validators.in_(ANALYSES),
        metadata=dict(required=True))
    family = attr.ib(default=None, metadata=dict(required=True))
    cldf = attr.ib(
        default=None,
        converter=lambda s: 'https://{}'.format(s) if s and s.startswith('github.com') else s)
    data = attr.ib(default=None)
    artefacts = attr.ib(default=None)
    missing = attr.ib(default=attr.Factory(dict))
    zenodo_concept_doi = attr.ib(default=None)

    def __attrs_post_init__(self):
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
