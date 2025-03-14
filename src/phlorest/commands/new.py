"""
Create a skeleton for a new dataset
"""
import pathlib
import collections

from phlorest.scaffold import PhlorestTemplate


def register(parser):  # pragma: no cover
    parser.add_argument(
        'out',
        help='Directory in which to create the skeleton',
        type=pathlib.Path,
        default=pathlib.Path('.'))


def run(args):
    tmpl = PhlorestTemplate()
    md = tmpl.metadata.elicit()
    tmpl.render(args.out, md)