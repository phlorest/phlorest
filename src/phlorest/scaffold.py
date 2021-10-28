import pathlib

from cldfbench.scaffold import Template

import phlorest


class PhlorestTemplate(Template):
    package = 'phlorest'

    dirs = Template.dirs + [pathlib.Path(phlorest.__file__).parent / 'phlorest_template']
    metadata = phlorest.Metadata
