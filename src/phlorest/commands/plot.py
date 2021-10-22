"""

"""
import webbrowser

from clldutils.clilib import PathType
from cldfbench.cli_util import add_dataset_spec, get_dataset

import phlorest


def register(parser):
    add_dataset_spec(parser)
    parser.add_argument(
        'output',
        type=PathType(must_exist=False),
    )


def run(args):
    phlorest.render_summary_tree(get_dataset(args).cldf_reader(), args.output)
    webbrowser.open(args.output.resolve().as_uri())
