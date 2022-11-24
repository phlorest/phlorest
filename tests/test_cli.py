import logging
import argparse

from phlorest.commands import check


def test_check(dataset, caplog):
    check.run(argparse.Namespace(log=logging.getLogger(__name__)), dataset)
    assert len(caplog.records) >= 4
