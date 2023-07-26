"""
Checks datasets for compliance
"""
from termcolor import colored
from cldfbench.cli_util import add_dataset_spec, get_dataset

from phlorest.check import run_checks


def register(parser):  # pragma: no cover
    add_dataset_spec(parser)


def run(args, d=None):
    if d is None:  # pragma: no cover
        try:
            d = get_dataset(args)
        except Exception as e:
            args.log.error("Unable to load %s - %s" % (args.dataset, e))
            raise

    msg, color = ('PASS', 'green') if run_checks(d, args.log) else ('FAIL', 'red')
    print('{} {}'.format(colored(msg, color, attrs=['bold']), d.id))
