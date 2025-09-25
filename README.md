# yaomem

[![License](https://img.shields.io/pypi/l/yaomem.svg?color=green)](https://github.com/tlambert03/yaomem/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/yaomem.svg?color=green)](https://pypi.org/project/yaomem)
[![Python
Version](https://img.shields.io/pypi/pyversions/yaomem.svg?color=green)](https://python.org)
[![CI](https://github.com/tlambert03/yaomem/actions/workflows/ci.yml/badge.svg)](https://github.com/tlambert03/yaomem/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tlambert03/yaomem/branch/main/graph/badge.svg)](https://codecov.io/gh/tlambert03/yaomem)

Yet another ome-zarr model.

## Oh no, not another one 🤦

First, let me apologize. The last thing the world needs is yet another ome-zarr
model. However, I was unable to find a *minimal* ome-zarr model that simply
represents the spec, without introducing additional I/O features or
dependencies.

You should first check these existing packages to see if they meet your needs:

- [ome-zarr-models-py](https://github.com/ome-zarr-models/ome-zarr-models-py).
  This is the one to check first. It has the most community attention, having
  resulted from the [2024 OME-NGFF workflows
  hackathon](https://osf.io/preprints/biohackrxiv/5uhwz_v2). It was specifically
  designed to reduce fragmentation.
  
   Unfortunately, for my use case, it makes assumptions about I/O (such as
  requiring `zarr`), in the interest of providing convenience methods such as
  `from_zarr()`.  I *simply* want classes that mirror the schema & specification
  without any additional dependencies or assumptions about how the data is
  stored or accessed.  There are issues & PRs to this effect:

  - <https://github.com/ome-zarr-models/ome-zarr-models-py/issues/161>
  - <https://github.com/ome-zarr-models/ome-zarr-models-py/pull/280>

  but since `ome-zarr-models-py` also depends on
  [`pydantic-zarr`](https://github.com/zarr-developers/pydantic-zarr), that
  library will *also* need to be modified to remove the `zarr` dependency.

  - <https://github.com/zarr-developers/pydantic-zarr/pull/112>

  It has also pinned itself to python 3.11, and I prefer to support the
  [official python EOL schedule](https://devguide.python.org/versions/), as
  opposed to the [numpy schedule](https://numpy.org/neps/nep-0029-deprecation_policy.html).
  
- [pydantic-ome-ngff](https://github.com/janeliascicomp/pydantic-ome-ngff).
  *Deprecated.*
- [ngff-zarr](https://github.com/fideus-labs/ngff-zarr).  This also contains
  models, but brings along [far more
  dependencies](https://github.com/fideus-labs/ngff-zarr/blob/baafd774993d4a1dcfe312cfcd626c06496bb69d/py/pyproject.toml#L31-L43)
  and assumptions (and functionality) than `ome-zarr-models-py`.

*In the meantime:*

This is an experimental package, where I can develop bare minimal models for my
applications.  The hope would be some future unification, provided the community
can agree on a common denominator of features.

## Installation

```bash
pip install git+https://github.com/tlambert03/yaomem
```
