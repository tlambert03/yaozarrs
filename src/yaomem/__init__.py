"""Yet another ome-zarr model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yaomem")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "uninstalled"

from . import v05
from ._ome_zarr import OMEZarr
from ._validate import validate_ome_node

__all__ = ["OMEZarr", "v05", "validate_ome_node"]
