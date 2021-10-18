import shutil
import pathlib
import argparse

import pytest
from cldfbench import CLDFWriter

from phlorest import *


@pytest.fixture
def dataset(tmp_path):
    shutil.copytree(pathlib.Path(__file__).parent / 'repos', tmp_path / 'repos')

    class DS(Dataset):
        dir = tmp_path / 'repos'
        id = 'phy'

    return DS()


def test_Dataset(dataset):
    dataset.init(argparse.Namespace(writer=dataset.cldf_writer(argparse.Namespace())))
