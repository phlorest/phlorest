import logging

from phlorest.check import run_checks


def test_run_checks(dataset, caplog):
    assert run_checks(dataset.cldf_reader(), logging.getLogger(__name__)) is False
    assert len(caplog.records) == 5
