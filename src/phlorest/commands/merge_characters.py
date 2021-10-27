"""

"""
import collections

from csvw.dsv import reader, UnicodeWriter
from clldutils.clilib import PathType
from cldfbench.cli_util import add_catalog_spec, add_dataset_spec, get_dataset


def register(parser):
    add_catalog_spec(parser, 'concepticon')
    add_dataset_spec(parser)
    parser.add_argument('mapping', type=PathType(type='file'))


def run(args):
    ds = get_dataset(args)

    conceptsets = {cs.gloss: cs for cs in args.concepticon.api.conceptsets.values()}

    chars = collections.OrderedDict([(c['Site'], c) for c in ds.characters])
    for mapping in reader(args.mapping, dicts=True):
        if mapping['Site'] not in chars:
            args.log.info('adding {}'.format(mapping))
            chars[mapping['Site']] = collections.OrderedDict(
                [('Site', mapping['Site']), ('Label', mapping['Label'])])
        else:
            if 'Label' in mapping and 'Label' in chars[mapping['Site']]:
                assert mapping['Label'] == chars[mapping['Site']]['Label']

        assert mapping['Word'] in conceptsets
        chars[mapping['Site']]['concepticonReference'] = conceptsets[mapping['Word']].id
        chars[mapping['Site']]['Concepticon_Gloss'] = mapping['Word']

    with UnicodeWriter(ds.etc_dir / 'characters.csv') as w:
        for i, char in enumerate(chars.values()):
            if i == 0:
                cols = list(char.keys())
                if 'concepticonReference' not in cols:
                    cols.append('concepticonReference')
                if 'Concepticon_Gloss' not in cols:
                    cols.append('Concepticon_Gloss')
                w.writerow(cols)
            w.writerow([char.get(col, '') for col in cols])
