import pathlib

import pytest


@pytest.fixture
def repos():
    return pathlib.Path(__file__).parent / 'repos'
