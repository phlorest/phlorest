import re
import copy
import gzip
import shlex
import shutil
import pathlib
import zipfile
import tempfile
import subprocess
import xml.etree.cElementTree as ElementTree

import attr
import cldfbench
import nexus
import newick

from pycldf.terms import TERMS
from nexus.handlers.tree import Tree as NexusTree

try:
    import ete3
except ImportError:
    ete3 = None

__version__ = '0.1.0'
__all__ = ['Dataset', 'Metadata', 'NexusFile', 'BeastFile', 'render_summary_tree']
SCALING = [
    'none',  # no branch lengths
    'change',  # parsimony steps
    'substitutions',  # change
    'years',  # years
    'centuries',  # centuries
    'millennia',  # millennia
]


def render_summary_tree(cldf, output, w=183, units='mm'):
    if ete3 is None:
        raise ValueError('This feature requires ete3. Install with "pip install phlorest[ete3]"')
    gcodes = {r['ID']: (r['Glottocode'], r.get('Glottolog_Name'))
              for r in cldf['LanguageTable'] if r['Glottocode']}

    def rename(n):
        if n.name in gcodes:
            n.name = "{}--{}".format(n.name, gcodes[n.name][0])

    for row in cldf['trees.csv']:
        if row['type'] == 'summary':
            tree = nexus.NexusReader(cldf.directory / row['Nexus_File']).trees.trees[0]
            nwk = newick.loads(tree.newick_string, strip_comments=True)[0]
            nwk.visit(rename)
            tree = ete3.Tree(nwk.newick + ';')
            tree.render(str(output), w=w, units=units)
            svg = ElementTree.fromstring(output.read_text(encoding='utf8'))
            for t in svg.findall('.//{http://www.w3.org/2000/svg}text'):
                lid, _, gcode = t.text.strip().partition('--')
                if gcode:
                    se = ElementTree.SubElement(t, '{http://www.w3.org/2000/svg}text')
                    gname = gcodes[lid][1]
                    if gname:
                        se.text = '{} - {} [{}]'.format(lid, gname, gcode)
                    else:
                        se.text = '{} - [{}]'.format(lid, gcode)
                    se.attrib = copy.copy(t.attrib)
                    se.attrib['fill'] = '#0000ff'
                    t.tag = '{http://www.w3.org/2000/svg}a'
                    t.attrib = {
                        'href': 'https://glottolog.org/resource/languoid/id/{}'.format(gcode),
                        'title': 'The glottolog name',
                    }
                    t.text = None
            output.write_bytes(ElementTree.tostring(svg))


def add_columns(args, table, obj, exclude=None):
    existing = [c.name for c in args.writer.cldf[table].tableSchema.columns]
    exclude = exclude or []
    new = []
    for k in obj.keys():
        if k not in exclude:
            col = TERMS[k].to_column() if k in TERMS else k
            if getattr(col, 'name', k) in existing:
                args.log.error('Duplicate column name {} for {}'.format(k, table))
                continue
            new.append(col)

    args.writer.cldf.add_columns(table, *new)


def add_obj(args, table, d, row, rename=None):
    rename = rename or {}
    for k, v in (row or {}).items():
        k = rename.get(k, k)
        if k in TERMS:
            k = TERMS[k].to_column().name
        d[k] = v
    args.writer.objects[table].append(d)


def check_tree(tree: NexusTree, lids, log):
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


class BeastFile:
    def __init__(self, path, text=None):
        self.path = path
        self.text = text

    def nexus_and_characters(self):
        return beast_to_nexus(self.path or self.text)


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

    def _cmd_makecldf(self, args):
        cldfbench.Dataset._cmd_makecldf(self, args)
        render_summary_tree(self.cldf_reader(), self.dir / 'summary_tree.svg')

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

    def run_nexus(self, cmd, *inputs):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            ips = []
            for i, input in enumerate(inputs, start=1):
                ip = d / 'in{}.nex'.format(i)
                if isinstance(input, str):
                    ip.write_text(input, encoding='utf8')
                else:
                    shutil.copy(input, ip)
                ips.append(str(ip))

            cmd = shlex.split(cmd)
            if cmd[0] != 'nexus':
                cmd = ['nexus'] + cmd
            fcmd = cmd + ips + ['-o', str(d / 'out.nex')]
            try:
                subprocess.check_call(fcmd)
            except:  # noqa: E722
                raise ValueError('Running "{}" failed'.format(' '.join(cmd)))
            return d.joinpath('out.nex').read_text(encoding='utf8')

    def remove_burnin(self, input, amount):
        return self.run_nexus('--log-level WARNING trees -d 1-{}'.format(amount), input)

    def sample(self,
               input,
               seed=12345,
               detranslate=False,
               as_nexus=False,
               n=1000,
               strip_annotation=False):
        res = self.run_nexus(
            'trees {} {} -n {} --random-seed {}'.format(
                '-t' if detranslate else '',
                '-c' if strip_annotation else '',
                n,
                seed),
            input)
        return nexus.NexusReader.from_string(res) if as_nexus else res

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
            "The ParameterTable lists characters (a.k.a. sites), i.e. the (often binary) variables"\
            " used as data basis to compute the phylogeny from."
        if md:
            add_columns(args, 'ParameterTable', list(md.values())[0], exclude=['Label'])
        args.writer.cldf['ParameterTable', 'ID'].common_props['dc:description'] = \
            "Sequence index of the site in the corresponding Nexus file."
        for site, label in chars:
            d = dict(ID=site, Name=label, Nexus_File='data.nex')
            add_obj(args, 'ParameterTable', d, md.get(site, {}), rename=dict(Label='Name'))
        assert all(t in self._lids for t in nex.data.taxa)
        assert all(t in self._lids for t in nex.data.matrix)
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
        for i, row in enumerate(self.taxa):
            if i == 0:
                add_columns(
                    args,
                    'LanguageTable',
                    row,
                    exclude=['taxon', 'glottocode', 'soc_ids', 'xd_ids'])
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
            add_obj(args, 'LanguageTable', d, row)


def beast_to_nexus(filename, valid_states="01?"):
    nex = nexus.NexusWriter()
    if isinstance(filename, str):
        xml = ElementTree.fromstring(filename)
    else:
        xml = ElementTree.parse(str(filename))
    #
    # <sequence>
    # <taxon idref=""/>
    # 1111111
    # </sequence>
    #
    seq_found = False
    for seq in xml.findall('./data/sequence'):
        seq_found = True
        for i, state in enumerate([s for s in seq.get('value') if s != ' '], start=1):
            assert state in valid_states, 'Invalid State %s' % state
            nex.add(seq.get('taxon'), i, state)

    if not seq_found:
        for seq in xml.findall('.//sequence[taxon]'):
            data = (seq.text.strip() if seq.text else None) or seq.find('taxon').tail.strip()
            assert data, ElementTree.tostring(seq).decode('utf8').replace('\n', '')
            for i, state in enumerate(list(data), start=1):
                assert state in valid_states, 'Invalid State %s' % state
                nex.add(seq.find('taxon').get('idref'), i, state)

    try:
        chars = sorted(list(beast2chars(xml)))
    except (ValueError, KeyError):
        chars = None
    return nexus.NexusReader.from_string(nex.write()), chars


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
        res = xml.find(".//alignment[@id='%s']" % data_id)
        if res is None:
            raise ValueError(data_id)
        return res

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
