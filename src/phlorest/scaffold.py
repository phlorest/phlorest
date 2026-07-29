"""
Phlorest-specific template for cldfbench datasets.
"""
import pathlib

from cldfbench.scaffold import Template

import phlorest


class PhlorestTemplate(Template):  # pylint: disable=R0903
    """
    Phlorest-specific template for cldfbench datasets.

    Adds support for phlorest metadata.
    """
    package = 'phlorest'

    dirs = Template.dirs + [pathlib.Path(phlorest.__file__).parent / 'phlorest_template']
    metadata = phlorest.Metadata
