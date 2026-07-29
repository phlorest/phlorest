"""
The `phlorest` package provides functionality to curate Phlorest phylogenies.
"""
from .dataset import Dataset
from .cldfwriter import CLDFWriter
from .metadata import Metadata
from .beast import BeastFile
from .nexuslib import NexusFile
from . import commands

__version__ = '2.0.0'
__all__ = ['Dataset', 'Metadata', 'BeastFile', 'NexusFile', 'CLDFWriter']

assert commands
