import collections
import urllib.parse

import attr
import cldfbench

__all__ = ['SCALING', 'RESCALE_TO_YEARS', 'Metadata']

SCALING = [
    'none',  # no branch lengths
    'change',  # parsimony steps
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
    'other',
    'none',  # override.
]
RESCALE_TO_YEARS = {
    'centuries': 100,
    'millennia': 1000,
}


@attr.s
class Metadata(cldfbench.Metadata):
    name = attr.ib(default=None)
    author = attr.ib(default=None)
    year = attr.ib(default=None)
    scaling = attr.ib(default='none', validator=attr.validators.in_(SCALING))
    analysis = attr.ib(default='none', validator=attr.validators.in_(ANALYSES))
    family = attr.ib(default=None)
    cldf = attr.ib(
        default=None,
        converter=lambda s: 'https://{}'.format(s) if s and s.startswith('github.com') else s)
    data = attr.ib(default=None)
    missing = attr.ib(default=attr.Factory(dict))

    def __attrs_post_init__(self):
        assert self.name and self.author and self.year
        if self.url:
            u = urllib.parse.urlparse(self.url)
            if u.netloc == 'dx.doi.org':
                self.url = urllib.parse.urlunsplit(('https', 'doi.org', u.path, '', ''))
        self.title = "Phlorest phylogeny derived from {0.author} {0.year} '{0.name}'".format(self)

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
