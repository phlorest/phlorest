"""
Checks datasets for compliance
"""
import argparse
import shutil
import pathlib
import zipfile
import subprocess
from typing import Optional

from clldutils.path import TemporaryDirectory, ensure_cmd
from termcolor import colored
from cldfbench.cli_util import add_dataset_spec
from commonnexus import Nexus

from phlorest.cli_util import get_dataset
from phlorest.dataset import Dataset
from phlorest.check import run_checks


def register(parser):  # pragma: no cover  # pylint: disable=C0116
    add_dataset_spec(parser)
    parser.add_argument(
        '--with-R',
        action='store_true',
        help="Make sure the NEXUS files of the dataset can be read with commonly used R packages."
             "\nNOTE: This requires the Rscript command and an R installation with the relevant "
             "packages.",
        default=False)


def run(args: argparse.Namespace, d: Optional[Dataset] = None):  # pylint: disable=C0116
    if d is None:  # pragma: no cover
        d = get_dataset(args)

    success = True
    if args.with_R:  # pragma: no cover
        for fname in ['summary.trees', 'posterior.trees.zip']:
            if d.cldf_dir.joinpath(fname).exists():
                p = d.cldf_dir / fname
                with TemporaryDirectory() as tmp:
                    if fname.endswith('.zip'):
                        with zipfile.ZipFile(p) as zipf:
                            zipf.extract(zipf.infolist()[0], tmp)
                            assert tmp.joinpath(p.stem).exists()
                            p = tmp / p.stem
                    else:
                        shutil.copy(p, tmp / p.name)
                        p = tmp / p.name
                    ntrees = len(Nexus.from_file(p).TREES.commands['TREE'])
                    res = subprocess.call([
                        ensure_cmd('Rscript'),
                        str(pathlib.Path(__file__).parent.parent / 'check.R'),
                        str(p),
                        str(ntrees),
                    ])
                    if res:
                        success = False

    msg, color = ('PASS', 'green') if run_checks(d, args.log) and success else ('FAIL', 'red')
    print(f"{colored(msg, color, attrs=['bold'])} {d.id}")
