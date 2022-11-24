import copy
import pathlib
import xml.etree.cElementTree as ElementTree

import newick
from pycldf.trees import TreeTable

import toytree
import toyplot.svg


def render_tree(nwk,
                output: pathlib.Path,
                scaling: str = None,
                gcodes: dict = None,
                legend: str = None,
                width: int = 1000):

    gcodes = gcodes or {}

    def rename(n):
        if n.name in gcodes:
            n.name = "{}--{}".format(n.name, gcodes[n.name][0])
        if not n.is_leaf:
            n.name = None

    nwk.visit(rename)
    ntaxa = sum(1 for n in nwk.walk() if n.is_leaf)
    tree = toytree.tree(nwk.newick + ";")
    canvas, axes, mark = tree.draw(
        width=width,
        height=ntaxa * 15 + 50,
        node_hover=True,
        tip_labels_align=True,
        tip_labels_style={
            "fill": "#262626",
            "font-size": "11px",
            "-toyplot-anchor-shift": "5px",
            "line-height": "14px",
        },
        scalebar=True
    )
    axes.label.text = legend
    toyplot.svg.render(canvas, str(output))
    add_glottolog_links(output, gcodes)


def add_glottolog_links(in_, gcodes, out=None):
    "Post-process the SVG to turn leaf names with Glottocodes into links"""
    ns = '{http://www.w3.org/2000/svg}'
    svg = ElementTree.fromstring(in_.read_text(encoding='utf8'))
    for t in svg.findall('*.//{0}g[@class="toytree-TipLabels"]/{0}g/{0}text'.format(ns)):
        lid, _, gcode = t.text.strip().partition('--')
        if gcode:
            se = ElementTree.SubElement(t, '{0}text'.format(ns))
            gname = gcodes[lid][1]
            if gname:
                se.text = '{} - {} [{}]'.format(lid, gname, gcode)
            else:
                se.text = '{} - [{}]'.format(lid, gcode)
            se.attrib = copy.copy(t.attrib)
            se.attrib['fill'] = '#0000ff'
            t.tag = '{0}a'.format(ns)
            t.attrib = {
                'href': 'https://glottolog.org/resource/languoid/id/{}'.format(gcode),
                'title': 'The glottolog name',
            }
            t.text = None
    (out or in_).write_bytes(ElementTree.tostring(svg))


def render_summary_tree(cldf, output, width=1000):
    for tree in TreeTable(cldf):
        if tree.tree_type == 'summary':
            legend = "Summary tree"
            if cldf.properties.get('dc:subject', {}).get('analysis'):
                title = cldf.properties['dc:subject']['analysis'].title()
                legend += ' of a {} analysis'.format(title)
            if cldf.properties.get('dc:subject', {}).get('family'):
                family = cldf.properties['dc:subject']['family']
                legend += ' of the {} family'.format(family)
            if tree.tree_branch_length_unit:
                legend += ' with branches in {}'.format(tree.tree_branch_length_unit)
            render_tree(
                tree.newick(strip_comments=True),
                output,
                gcodes={
                    r['ID']: (r['Glottocode'], r.get('Glottolog_Name'))
                    for r in cldf['LanguageTable'] if r['Glottocode']},
                scaling=tree.tree_branch_length_unit,
                legend=legend,
                width=width
            )
            return output
