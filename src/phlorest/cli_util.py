"""
Functionality for phlorest commands.
"""
from cldfbench.cli_util import get_dataset as base_get_dataset

__all__ = ['get_dataset']


def get_dataset(args):
    """Get a dataset with some information on failure."""
    try:
        return base_get_dataset(args)
    except Exception as e:
        args.log.error("Unable to load %s - %s", args.dataset, e)
        raise
