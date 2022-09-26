"""
Plots a phylogeny to SVG
"""
import webbrowser

from clldutils.clilib import PathType
from cldfbench.cli_util import add_dataset_spec, get_dataset

from phlorest.render import render_summary_tree


def register(parser):  # pragma: no cover
    add_dataset_spec(parser)
    parser.add_argument(
        'output',
        type=PathType(must_exist=False),
    )


def run(args):  # pragma: no cover
    render_summary_tree(get_dataset(args).cldf_reader(), args.output)
    webbrowser.open(args.output.resolve().as_uri())
