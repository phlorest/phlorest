# Releasing

- Install in editable mode:
  ```shell
  pip install -e .[test]
  ```
- Re-create the CLDF dataset with the latest Glottolog release:
  ```shell
  GLOTTOLOG=$(git ls-remote --tags --sort=-v:refname https://github.com/glottolog/glottolog 'v*' | head -1 | sed 's|.*/||; s|\^{}||')
  cldfbench makecldf --glottolog-version $GLOTTOLOG cldfbench_*.py --with-zenodo --with-cldfreadme
  ```
- Make sure the CLDF is valid:
  ```shell
  pytest
  ```
- Re-create the README:
  ```shell
  cldfbench readme cldfbench_*.py
  ```
- Run Phlorest-specific checks on the data:
  ```shell
  phlorest check --with-R cldfbench_*.py
  ```
- Check whether new files have been generated (and add them if so):
  ```shell
  git status
  ```
- Figure out the new release tag:
  ```shell
  git tag
  ```
- Commit and push the release-ready data:
  ```shell
  git commit -a -m"release vX.Y"
  git push origin
  ```
- Create the release instruction:
  ```shell
  phlorest release cldfbench_*.py vX.Y
  ```
- Make sure the repository is wired up with Zenodo, and if so run the `gh release` command as
  given in the output of `phlorest release`.
