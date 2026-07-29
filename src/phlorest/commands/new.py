"""
Create a skeleton for a new dataset
"""
import pathlib

from phlorest.scaffold import PhlorestTemplate


def register(parser):  # pragma: no cover  # pylint: disable=C0116
    parser.add_argument(
        'out',
        help='Directory in which to create the skeleton',
        type=pathlib.Path,
        default=pathlib.Path('.'))


def run(args):  # pragma: no cover  # pylint: disable=C0116
    tmpl = PhlorestTemplate()
    tmpl.render(args.out, tmpl.metadata.elicit())
