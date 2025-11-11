# phlorest

A [cldfbench](https://github.com/cldf/cldfbench) plugin to curate language phylogenies.


## Install

```shell
pip install phlorest
```


## Usage

### Bootstrapping a `phlorest`-curated dataset

`phlorest` provides a `cldfbench` dataset template to create the skeleton of files and directories for a
`phlorest`-curated dataset, to be run with [cldfbench new](https://github.com/cldf/cldfbench/#creating-a-skeleton-for-a-new-dataset-directory).

Running

```shell
cldfbench new --template phlorest 
```

will create a dataset skeleton looking as follows
```shell
$ tree testtree/
testtree/
├── cldf
│   └── README.md
├── cldfbench_testtree.py
├── etc
│   ├── characters.csv
│   └── taxa.csv
├── metadata.json
├── raw
│   └── README.md
├── setup.cfg
├── setup.py
└── test.py
```


### Implementing CLDF creation

Implementing CLDF creation means - as for any other `cldfbench`-curated dataset - filling in the
`cmd_makecldf` method of the `Dataset` subclass in `cldfbench_<id>.py`.

The CLDF writer which can be accessed as `args.writer` within `cmd_makecldf` is an instance of
`phlorest.CLDFWriter`, which has convenience methods to add summary- or posterior trees to the CLDF
dataset. At least a summary is needed to make a dataset valid. Adding one looks as follows

```python
    args.writer.add_summary(
        self.raw_dir.read_tree(...),
        self.metadata,
        args.log)
```


### Running CLDF creation

With `cmd_makecldf` implemented, CLDF creation can be triggered running
```shell
cldfbench makecldf cldfbench_<id>.py
```

The resulting CLDF dataset can be validated running
```shell
pytest
```


### Release workflow

```shell
cldfbench makecldf --glottolog-version v5.2 --with-cldfreadme cldfbench_<id>.py
pytest
cldfbench zenodo --communities phlorest cldfbench_<id>.py
cldfbench readme cldfbench_<id>.py
phlorest check --with-R cldfbench_<id>.py
git commit -a -m"release vX.Y"
git push origin
phlorest release cldfbench_<id>.py vX.Y
```


## Dependencies

The `run_treeannotator` method of `Dataset` requires the `treeannotator` command from BEAST to be
installed. For details on how to install `treeannotator` (and `BEAST`), see https://beast.community/index.html
