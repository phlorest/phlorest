import xml.etree.cElementTree as ElementTree

import nexus

__all__ = ['BeastFile']


class BeastFile:
    def __init__(self, path, text=None):
        self.path = path
        self.text = text

    def nexus_and_characters(self):
        return beast_to_nexus(self.path or self.text)


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
