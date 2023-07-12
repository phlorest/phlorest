import typing
import pathlib
import collections
import xml.etree.cElementTree as ElementTree

from commonnexus import Nexus
from commonnexus.blocks import Characters

__all__ = ['BeastFile']


class BeastFile:
    def __init__(self, path: typing.Union[str, pathlib.Path], text: typing.Optional[str] = None):
        self.path = path
        self.text = text
        if self.text:
            self.xml = ElementTree.fromstring(self.text)
        else:
            self.xml = ElementTree.parse(str(self.path))

    def nexus(self, valid_states: str = '01?') -> Nexus:
        """
        Read the character data used in a BEAST file and format it as NEXUS file.

        :param valid_states: String listing one-character state labels.
        :return: A Nexus instance with a CHARACTERS block encoding the data from the BEAST file as \
        MATRIX.
        """
        try:  # Read the character labels.
            chars = dict(self.iter_characters())
        except (ValueError, KeyError):  # pragma: no cover
            chars = {}  # No character labels.

        matrix = collections.OrderedDict()

        def add_row(taxon, seq):
            matrix[taxon] = collections.OrderedDict()
            for i, state in enumerate([s for s in seq if s != ' '], start=1):
                assert state in valid_states, 'Invalid State %s' % state
                matrix[taxon][chars.get(i, str(i))] = None if state == '?' else state

        for seq in self.xml.findall('./data/sequence'):
            add_row(seq.get('taxon'), seq.get('value'))

        if not matrix:
            for seq in self.xml.findall('.//sequence[taxon]'):
                data = (seq.text.strip() if seq.text else None) or seq.find('taxon').tail.strip()
                assert data, ElementTree.tostring(seq).decode('utf8').replace('\n', '')
                add_row(seq.find('taxon').attrib['idref'], data)

        return Nexus.from_blocks(Characters.from_data(matrix))

    def iter_characters(self):
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
            res = self.xml.find(".//alignment[@id='%s']" % data_id)
            if res is None:  # pragma: no cover
                raise ValueError(data_id)
            return res

        for treelh in self.xml.findall(".//distribution[@spec='TreeLikelihood']"):
            if treelh.get('data'):
                data = get_by_id(treelh.get('data'))
                ascertained = data.get('ascertained') == 'true'
                yield from printchar(*get_partition(data.find('./data')), ascertained=ascertained)
            else:
                data = treelh.find('./data')
                ascertained = data.get('ascertained') == 'true'
                dd = get_by_id(data.get('data')) if data.get('data') else treelh.find('./data/data')
                yield from printchar(*get_partition(dd), ascertained=ascertained)
