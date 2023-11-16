import shutil
import logging
import argparse

from phlorest.commands import check, contrib
from phlorest.__main__ import main
from phlorest import Dataset


def test_check(dataset, caplog):
    check.run(argparse.Namespace(log=logging.getLogger(__name__), with_R=False), dataset)
    assert len(caplog.records) >= 4


def test_contrib(dataset, capsys):
    contrib.run(argparse.Namespace(log=logging.getLogger(__name__)), dataset)
    out, _ = capsys.readouterr()
    assert 'GitHub user' in out


def test_check_characters(tmp_repos):
    tmp_repos.joinpath('etc', 'characters.csv').write_text('a,b\n,', encoding='utf8')
    shutil.rmtree(tmp_repos / 'cldf')

    class DS(Dataset):
        dir = tmp_repos
        id = 'phy'

    check.run(argparse.Namespace(log=logging.getLogger(__name__), with_R=False), DS())


def test_main(dataset):
    main(parsed_args=argparse.Namespace(dataset=dataset))