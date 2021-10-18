import copy
import gzip
import uuid
import shlex
import shutil
import pathlib
import tempfile
import subprocess
import xml.etree.cElementTree as ElementTree

import attr
import cldfbench
import nexus

__all__ = ['Dataset', 'Metadata']
SCALING = [
    'none',           # no branch lengths
    'change',         # parsimony steps
    'substitutions',  # change
    'years',          # years
    'centuries',      # centuries
    'millennia',      # millennia
]


def check_tree(tree, lids, log):
    lids = copy.copy(lids)
    for node in tree.newick_tree.walk():
        if node.name == 'root':
            continue
        if node.is_leaf:
            assert node.name
        if node.name:
            try:
                lids.remove(node.name)
            except KeyError:
                if node.is_leaf:
                    log.error('{} references undefined leaf {}'.format(tree.name, node.name))
                else:
                    log.warning(
                        '{} references undefined inner node {}'.format(tree.name, node.name))

    if lids:
        log.warning('extra taxa specified in LanguageTable: {}'.format(lids))


def format_tree(tree, default_label='tree'):
    rooting = '' if tree.rooted is None else '[&{}] '.format('R' if tree.rooted else 'U')
    return 'tree {} = {}{}'.format(tree.name or default_label, rooting, tree.newick_string)


class NexusFile:
    def __init__(self, path):
        self.path = path
        self._trees = []

    def append(self, tree):
        self._trees.append(tree)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        nex = nexus.NexusWriter()
        for i, tree in enumerate(self._trees, start=1):
            nex.trees.append(format_tree(tree, default_label='tree{}'.format(i)))
        nex.write_to_file(self.path)


@attr.s
class Metadata(cldfbench.Metadata):
    name = attr.ib(default=None)
    author = attr.ib(default=None)
    year = attr.ib(default=None)
    scaling = attr.ib(default=None, validator=attr.validators.in_(SCALING))
    analysis = attr.ib(default=None)
    family = attr.ib(default=None)
    cldf = attr.ib(default=None)
    data = attr.ib(default=None)
    missing = attr.ib(default=attr.Factory(dict))


class Dataset(cldfbench.Dataset):
    metadata_cls = Metadata

    def __init__(self):
        cldfbench.Dataset.__init__(self)
        self._lids = set()

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return super().cldf_specs()

    def cmd_download(self, args):
        pass

    def read_gzipped_text(self, p):
        with gzip.open(p) as fp:
            return fp.read().decode('utf8')

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

    def run_nexus(self, cmd, input):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            if isinstance(input, str):
                d.joinpath('in.nex').write_text(input, encoding='utf8')
            else:
                shutil.copy(input, d / 'in.nex')
            cmd = shlex.split(cmd)
            if cmd[0] != 'nexus':
                cmd = ['nexus'] + cmd
            fcmd = cmd + [str(d / 'in.nex'), '-o', str(d / 'out.nex')]
            try:
                subprocess.check_call(fcmd)
            except:
                i = '{}.nex'.format(uuid.uuid1())
                shutil.copy(d / 'in.nex', i)
                raise ValueError('Running "{} {}" failed'.format(' '.join(cmd), i))
            return d.joinpath('out.nex').read_text(encoding='utf8')

    def remove_burnin(self, input, amount):
        return self.run_nexus('--log-level WARNING trees -d 1-{}'.format(amount), input)

    def sample(self, input, seed=12345, detranslate=False):
        return self.run_nexus(
            'trees {} -n 1000 --random-seed {}'.format('-t' if detranslate else '', seed),
            input)

    def init(self, args):
        self.add_schema(args)
        self.add_taxa(args)
        if self.raw_dir.joinpath('source.bib').exists():
            args.writer.cldf.sources.add(
                self.raw_dir.joinpath('source.bib').read_text(encoding='utf8'))

    def add_schema(self, args):
        args.writer.cldf.add_component('LanguageTable')
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
        if self._lids:
            check_tree(tree, self._lids, args.log)
        nex.append(tree)
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
            scaling=self.metadata.scaling,
            Source=[source] if isinstance(source, str) else source,
        ))

    def add_data(self, args, input):
        nex = input if isinstance(input, (nexus.NexusReader, nexus.NexusWriter)) \
            else nexus.NexusReader(input)
        assert all(t in self._lids for t in nex.data.taxa)
        assert all(t in self._lids for t in nex.data.matrix)
        #
        # FIXME: more validation! E.g. whether number of charstatelabels matches number of sites in matrix.
        #
        nex.write_to_file(self.cldf_dir / 'data.nex')
        #
        # FIXME: handle the case when there already is a "dc:hasPart" property!
        #
        args.writer.cldf.properties['dc:hasPart'] = {
            'dc:relation': 'data.nex',
            'dc:description': 'The data underlying the analysis which created the phylogeny',
            'dc:format': 'https://en.wikipedia.org/wiki/Nexus_file',
        }

    def add_taxa(self, args):
        glangs = {lg.id: lg for lg in args.glottolog.api.languoids()}
        #
        # FIXME: add metadata from Glottolog, put in dplace-tree-specific Dataset base class.
        # FIXME: log warnings if taxa are mapped to bookkeeping languoids!
        #
        for row in self.etc_dir.read_csv('taxa.csv', dicts=True):
            self._lids.add(row['taxon'])
            glang = None
            if row['glottocode']:
                glang = glangs[row['glottocode']]
            args.writer.objects['LanguageTable'].append(dict(
                ID=row['taxon'],
                Name=row['taxon'],
                Glottocode=row['glottocode'] or None,
                Latitude=glang.latitude if glang else None,
                Longitude=glang.longitude if glang else None,
            ))


def beast_to_nexus(filename, valid_states="01?"):
    nex = nexus.NexusWriter()
    xml = ElementTree.parse(str(filename))
    for seq in xml.findall('./data/sequence'):
        for i, state in enumerate([s for s in seq.get('value') if s != ' '], start=1):
            assert state in valid_states, 'Invalid State %s' % state
            nex.add(seq.get('taxon'), i, state)
    #
    # Now serialze and hack in the charstatelabel block!
    #
    new = []
    for line in nex.write().split('\n'):
        if line.strip().lower() == 'matrix':
            # here's where we should put the charstatelabels!
            chars = sorted(list(beast2chars(xml)))
            if chars:
                new.append('\tcharstatelabels')
                for i, (n, label) in enumerate(chars, start=1):
                    new.append('\t\t{} {}{}'.format(n, label, ',' if i != len(chars) else ''))
                new.append('\t;')
        new.append(line)
    return nexus.NexusReader.from_string('\n'.join(new))


def beast2chars(xml):
    def find_filter(node):  # note recursive
        for child in node:
            find_filter(child)
            (p, x, y) = get_partition(node)
            if p and x and y:
                return (p, x, y)

    def get_partition(p):
        x, y = [int(_) for _ in p.get('filter').split("-")]
        return (p.get('id'), x, y)

    def printchar(p, x, y, ascertained=False):
        n = 1
        for i in range(x, y + 1):
            label = "%s-%s" % (p, 'ascertained' if n == 1 and ascertained else str(n))
            yield i, label
            n += 1

    def get_by_id(data_id):
        if data_id.startswith("@"):
            data_id = data_id.lstrip("@")
        return xml.find(".//alignment[@id='%s']" % data_id)

    for treelh in xml.findall(".//distribution[@spec='TreeLikelihood']"):
        if treelh.get('data'):
            data = get_by_id(treelh.get('data'))
            ascertained = data.get('ascertained') == 'true'
            yield from printchar(*get_partition(data.find('./data')), ascertained=ascertained)
        else:
            data = treelh.find('./data')
            ascertained = data.get('ascertained') == 'true'
            if data.get('data'):
                datadata = get_by_id(data.get('data'))
            else:
                datadata = treelh.find('./data/data')
            yield from printchar(*get_partition(datadata), ascertained=ascertained)
