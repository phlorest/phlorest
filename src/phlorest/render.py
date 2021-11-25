import copy
import pathlib
import xml.etree.cElementTree as ElementTree

import nexus
import newick
try:  # pragma: no cover
    import ete3
except ImportError:  # pragma: no cover
    ete3 = None


def render_tree(tree,
                output: pathlib.Path,
                scaling: str = None,
                gcodes: dict = None,
                legend: str = None,
                width: int = 1000,
                units: str = 'px',
                ete3_format: int = 0):
    if ete3 is None:  # pragma: no cover
        raise ValueError('This feature requires ete3. Install with "pip install phlorest[ete3]"')

    gcodes = gcodes or {}

    def rename(n):
        if n.name in gcodes:
            n.name = "{}--{}".format(n.name, gcodes[n.name][0])
        if not n.is_leaf:
            n.name = None

    ts = ete3.TreeStyle()
    ts.show_leaf_name = True
    # ts.show_branch_length = True

    if scaling == 'years':
        ts.scale = 0.025

    if legend:
        ts.legend.add_face(ete3.TextFace(legend), column=0)

    nwk = newick.loads(tree.newick_string, strip_comments=True)[0]
    nwk.visit(rename)
    tree = ete3.Tree(nwk.newick + ';', format=ete3_format)
    tree.render(str(output), w=width, units=units, tree_style=ts)
    add_glottolog_links(output, gcodes)


def add_glottolog_links(in_, gcodes, out=None):
    # Post-process the SVG to turn leaf names with Glottocodes into links:
    svg = ElementTree.fromstring(in_.read_text(encoding='utf8'))
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
    (out or in_).write_bytes(ElementTree.tostring(svg))


def nexus_tree_from_row(cldf, row):
    for tree in nexus.NexusReader(cldf.directory / row['Nexus_File']).trees:
        if tree.name == row['ID']:
            return tree


def render_summary_tree(cldf, output, width=1000, units='px', ete3_format=0):
    for row in cldf['trees.csv']:
        if row['type'] == 'summary':
            legend = "Summary tree"
            if cldf.properties.get('dc:subject', {}).get('analysis'):
                legend += ' of a {} analysis'.format(cldf.properties['dc:subject']['analysis'])
            if cldf.properties.get('dc:subject', {}).get('family'):
                legend += ' of the {} family'.format(cldf.properties['dc:subject']['family'])
            if row['scaling'] != 'none':
                legend += ' with {} as scale'.format(row['scaling'])
            render_tree(
                nexus_tree_from_row(cldf, row),
                output,
                gcodes={
                    r['ID']: (r['Glottocode'], r.get('Glottolog_Name'))
                    for r in cldf['LanguageTable'] if r['Glottocode']},
                scaling=row['scaling'],
                legend=legend,
                width=width,
                units=units,
                ete3_format=ete3_format,
            )
            return output
