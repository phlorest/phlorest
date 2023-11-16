import logging
import pathlib

import phlorest
from phlorest.check import run_checks


def test_run_checks(dataset, caplog):
    assert run_checks(dataset.cldf_reader(), logging.getLogger(__name__)) is False
    assert len(caplog.records) == 5
    assert pathlib.Path(phlorest.__file__).parent.joinpath('check.R').exists()
