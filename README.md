# yaomem

[![License](https://img.shields.io/pypi/l/yaomem.svg?color=green)](https://github.com/tlambert03/yaomem/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/yaomem.svg?color=green)](https://pypi.org/project/yaomem)
[![Python Version](https://img.shields.io/pypi/pyversions/yaomem.svg?color=green)](https://python.org)
[![CI](https://github.com/tlambert03/yaomem/actions/workflows/ci.yml/badge.svg)](https://github.com/tlambert03/yaomem/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tlambert03/yaomem/branch/main/graph/badge.svg)](https://codecov.io/gh/tlambert03/yaomem)

Yet another ome-zarr model.

## Development

The easiest way to get started is to use the [github cli](https://cli.github.com)
and [uv](https://docs.astral.sh/uv/getting-started/installation/):

```sh
gh repo fork tlambert03/yaomem --clone
# or just
# gh repo clone tlambert03/yaomem
cd yaomem
uv sync
```

Run tests:

```sh
uv run pytest
```

Lint files:

```sh
uv run pre-commit run --all-files
```
